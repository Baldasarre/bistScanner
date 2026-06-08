"""
Flask routes for the BIST scanner application
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from database.db_manager import DatabaseManager
from database.models import db, Zone, ZoneComment
from web.auth import authenticate_user
import logging
import json
import yfinance as yf
import numpy as np
import pandas as pd
import threading
import os
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('main', __name__)

def _deduplicate_zones(zones, active_only=False):
    """Helper to remove duplicate zones with same ticker and timeframe"""
    if not zones:
        return []
        
    # En yeni kaydı (en yüksek ID) en üste al.
    # Bu sayede süzgeç her zaman en son taranan veriyi seçer.
    zones.sort(key=lambda x: x.id if hasattr(x, 'id') else 0, reverse=True)

    seen = set()
    unique_zones = []
    initial_count = len(zones)
    
    for zone in zones:
        # Tarih formatı ne gelirse gelsin (string veya datetime), sadece YYYY-MM-DD kısmını al
        # split(' ')[0] ile saat kısmını, [:10] ile de olası uzun formatları temizliyoruz
        raw_s = str(zone.start_date).split(' ')[0]
        raw_e = str(zone.end_date).split(' ')[0]
        s_date = raw_s[:10]
        e_date = raw_e[:10]
        
        # Ticker'ı temizle: .IS kısmını at, $ işaretini sil, büyük harfe çevir
        clean_ticker = zone.ticker.split('.')[0].replace('$', '').strip().upper()
        
        # Aktif bloklarda sadece hisse koduna bak (1 hisse 1 aktif blok)
        if active_only:
            identifier = clean_ticker
        else:
            identifier = (clean_ticker, s_date, e_date)
        
        if identifier not in seen:
            seen.add(identifier)
            unique_zones.append(zone)
            
    if initial_count > len(unique_zones):
        logger.info(f"Deduplication: {initial_count} kayıttan {initial_count - len(unique_zones)} tanesi mükerrer olduğu için elendi.")
        
    return unique_zones

@bp.route('/')
@login_required
def index():
    """Dashboard - main page"""
    return render_template('dashboard.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = authenticate_user(username, password)

        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Kullanıcı adı veya şifre hatalı', 'error')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    return redirect(url_for('main.login'))


@bp.route('/api/active-zones')
@login_required
def api_active_zones():
    """API endpoint for active zones"""
    try:
        # SQL session verilerini tazele (stale data önleme)
        db.session.expire_all()
        
        zones = DatabaseManager.get_active_zones()
        
        # Aktif bloklar için sadece hisse koduna göre tekilleştir (En günceli kalır)
        unique_zones = _deduplicate_zones(zones, active_only=True)

        # Add score change and last comment to each zone
        zones_data = []
        for zone in unique_zones:
            zone_dict = zone.to_dict()
            zone_dict['score_change'] = DatabaseManager.get_zone_score_change(zone.id)
            # Add last comment preview
            if zone.comments:
                last_comment = zone.comments[0]  # Already ordered by created_at desc
                zone_dict['last_comment'] = f"{last_comment.user.username}: {last_comment.comment[:50]}{'...' if len(last_comment.comment) > 50 else ''}"
            else:
                zone_dict['last_comment'] = None
            zones_data.append(zone_dict)

        return jsonify({
            'success': True,
            'zones': zones_data
        })

    except Exception as e:
        logger.error(f"Error fetching active zones: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/completed-zones')
@login_required
def api_completed_zones():
    """API endpoint for completed zones (last 3 weeks)"""
    try:
        # SQL session verilerini tazele
        db.session.expire_all()
        
        days = request.args.get('days', 21, type=int)
        zones = DatabaseManager.get_completed_zones(days=days)

        # Tekilleştirme işlemini yardımcı fonksiyonla yap
        unique_zones = _deduplicate_zones(zones)

        # Add last comment to each zone
        zones_data = []
        for zone in unique_zones:
            zone_dict = zone.to_dict()
            # Add last comment preview
            if zone.comments:
                last_comment = zone.comments[0]  # Already ordered by created_at desc
                zone_dict['last_comment'] = f"{last_comment.user.username}: {last_comment.comment[:50]}{'...' if len(last_comment.comment) > 50 else ''}"
            else:
                zone_dict['last_comment'] = None
            zones_data.append(zone_dict)

        return jsonify({
            'success': True,
            'zones': zones_data
        })

    except Exception as e:
        logger.error(f"Error fetching completed zones: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/moved-zones')
@login_required
def api_moved_zones():
    """TSHEB - Tamamlanma sonrasi %10 hareket etmis bloklar"""
    try:
        # SQL session verilerini tazele
        db.session.expire_all()
        
        # Bakış penceresini 60 güne çıkaralım
        zones = DatabaseManager.get_completed_zones(days=60)
        if not zones:
            logger.info("TSHEB: Veritabaninda tamamlanmis/kuraldisi blok bulunamadi.")
            return jsonify({'success': True, 'zones': []})

        # Tekilleştirme işlemini yardımcı fonksiyonla yap
        unique_zones = _deduplicate_zones(zones)
        logger.info(f"TSHEB: {len(unique_zones)} benzersiz blok icin fiyat kontrolu basliyor...")

        # Yahoo Finance hatasini onlemek icin .IS eki kontrolu
        tickers_map = {z.ticker: (z.ticker if z.ticker.endswith('.IS') else f"{z.ticker}.IS") for z in unique_zones}
        yf_tickers = list(set(tickers_map.values()))
        
        # Hafta sonu/tatil riskine karsı 7 gunluk veri cekiyoruz
        data = yf.download(yf_tickers, period='7d', interval='1d', group_by='ticker', progress=False)
        
        moved_zones = []
        for zone in unique_zones:
            try:
                yf_ticker = tickers_map[zone.ticker]
                ticker_data = None

                # yfinance yapısı tekli vs çoklu sonuçta farklıdır
                if isinstance(data.columns, pd.MultiIndex):
                    if yf_ticker in data.columns.levels[0]:
                        ticker_data = data[yf_ticker]
                else:
                    ticker_data = data

                if ticker_data is None or ticker_data.empty:
                    continue

                # Fiyat verisini güvenli bir şekilde al
                # dropna() kullanarak son satırdaki olası NaN değerlerini atlıyoruz
                valid_closes = ticker_data['Close'].dropna()
                if valid_closes.empty:
                    continue
                
                current_price = valid_closes.iloc[-1]

                if current_price is None or np.isnan(current_price):
                    continue

                base_price = (zone.highest_body + zone.lowest_body) / 2
                diff_pct = (current_price - base_price) / base_price
                
                if abs(diff_pct) >= 0.10:
                    zone_dict = zone.to_dict()
                    zone_dict['current_price'] = round(float(current_price), 2)
                    zone_dict['move_percent'] = round(float(diff_pct * 100), 1)
                    moved_zones.append(zone_dict)
            except Exception:
                continue

        moved_zones.sort(key=lambda x: abs(x['move_percent']), reverse=True)
        return jsonify({'success': True, 'zones': moved_zones})
    except Exception as e:
        logger.error(f"TSHEB hatasi: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/zone/<int:zone_id>')
@login_required
def api_zone_detail(zone_id):
    """API endpoint for zone details with history"""
    try:
        zone, history = DatabaseManager.get_zone_with_history(zone_id)

        if not zone:
            return jsonify({
                'success': False,
                'error': 'Zone not found'
            }), 404

        return jsonify({
            'success': True,
            'zone': zone.to_dict(),
            'history': [h.to_dict() for h in history]
        })

    except Exception as e:
        logger.error(f"Error fetching zone detail: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/scan-status')
@login_required
def api_scan_status():
    """API endpoint for latest scan status"""
    try:
        scan_log = DatabaseManager.get_latest_scan_log()

        if not scan_log:
            return jsonify({
                'success': True,
                'scan_log': None
            })

        # Tarihi ISO 8601 formatında ve UTC (Z) belirteciyle gönder
        log_data = scan_log.to_dict()
        if scan_log.scan_date:
            log_data['scan_date'] = scan_log.scan_date.strftime('%Y-%m-%dT%H:%M:%SZ')

        return jsonify({
            'success': True,
            'scan_log': log_data
        })

    except Exception as e:
        logger.error(f"Error fetching scan status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/zone/<int:zone_id>/comments', methods=['GET'])
@login_required
def api_get_comments(zone_id):
    """Get comments for a zone"""
    try:
        zone = Zone.query.get_or_404(zone_id)
        comments = []
        for comment in zone.comments:
            comment_dict = comment.to_dict()
            comment_dict['can_delete'] = (comment.user_id == current_user.id)
            comments.append(comment_dict)

        return jsonify({
            'success': True,
            'comments': comments
        })
    except Exception as e:
        logger.error(f"Error fetching comments: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/zone/<int:zone_id>/comments', methods=['POST'])
@login_required
def api_add_comment(zone_id):
    """Add a comment to a zone"""
    try:
        data = request.get_json()
        comment_text = data.get('comment', '').strip()

        if not comment_text:
            return jsonify({
                'success': False,
                'error': 'Yorum boş olamaz'
            }), 400

        # Create comment
        comment = ZoneComment(
            zone_id=zone_id,
            user_id=current_user.id,
            comment=comment_text
        )

        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': comment.to_dict()
        })
    except Exception as e:
        logger.error(f"Error adding comment: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/comment/<int:comment_id>', methods=['DELETE'])
@login_required
def api_delete_comment(comment_id):
    """Delete a comment"""
    try:
        comment = ZoneComment.query.get_or_404(comment_id)

        # Check if user owns the comment
        if comment.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Bu yorumu silme yetkiniz yok'
            }), 403

        db.session.delete(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Yorum silindi'
        })
    except Exception as e:
        logger.error(f"Error deleting comment: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/zone/<int:zone_id>/flag', methods=['POST'])
@login_required
def api_toggle_flag(zone_id):
    """Toggle flag on a zone"""
    try:
        zone = Zone.query.get_or_404(zone_id)
        zone.is_flagged = not zone.is_flagged
        db.session.commit()

        return jsonify({
            'success': True,
            'is_flagged': zone.is_flagged
        })
    except Exception as e:
        logger.error(f"Error toggling flag: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/trigger-scan', methods=['POST'])
@login_required
def api_trigger_scan():
    """Start a manual scan in the background"""
    try:
        if not hasattr(current_app, 'scheduler'):
            return jsonify({'success': False, 'error': 'Zamanlayıcı aktif değil.'}), 500
            
        scheduler = current_app.scheduler
        if scheduler.progress["status"] == "running":
            return jsonify({'success': False, 'error': 'Tarama zaten devam ediyor.'}), 400

        # Durumu hemen güncelleyerek frontend'in progress barı başlatmasını sağlıyoruz
        scheduler.progress.update({
            "status": "running",
            "percent": 0,
            "current": 0,
            "total": 0
        })
        
        # Ana uygulama nesnesini thread içine güvenli bir şekilde aktarıyoruz
        app = current_app._get_current_object()
        
        def run_async(app_instance):
            with app_instance.app_context():
                try:
                    app_instance.scheduler.run_scan()
                except Exception as e:
                    logger.error(f"Async scan crash: {e}")
                    app_instance.scheduler.progress["status"] = "idle"

        thread = threading.Thread(target=run_async, args=(app,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Tarama başlatıldı.'})
    except Exception as e:
        logger.error(f"Manual scan trigger failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/scan-progress')
@login_required
def api_scan_progress():
    """Get current scan progress"""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    progress_file = os.path.join(root_dir, 'data', 'scan_progress.json')
    
    # Varsayılan olarak scheduler'ın bellekteki durumunu kullan (uygulama yeni başladıysa veya dosya yoksa)
    data = current_app.scheduler.progress.copy() 

    # Dosyadan okumayı dene (worker'lar arası senkronizasyon için)
    # Atomik yazma sırasında dosya geçici olarak bozuk olabilir, bu yüzden birkaç kez dene
    for _ in range(3): # 3 deneme hakkı ver
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r') as f:
                    file_data = json.load(f)
                    # Sadece dosyadaki veri daha güncelse veya tarama çalışıyorsa kullan
                    if file_data.get('status') == 'running' or \
                       (file_data.get('updated_at') and file_data.get('updated_at') > data.get('updated_at', '')):
                        data = file_data
                    break # Başarılı okuma, döngüden çık
            except json.JSONDecodeError:
                # Dosya bozuk veya yazılıyor olabilir, kısa bekle ve tekrar dene
                time.sleep(0.05) 
            except Exception as e:
                logger.error(f"Progress dosyasini okurken hata olustu: {e}")
                break # Diğer hatalarda tekrar deneme
        else:
            break # Dosya yoksa, bellekteki varsayılanı kullan

    data['pid'] = os.getpid()
    
    logger.debug(f"[PID:{data['pid']}] Progress sorgulandi: {data['status']}")
    return jsonify({
        'success': True,
        'progress': data
    })

@bp.route('/api/keepalive')
def api_keepalive():
    """Health check endpoint for the application"""
    scheduler_active = hasattr(current_app, 'scheduler') and current_app.scheduler.running
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'scheduler_running': scheduler_active,
        'message': 'System operational'
    })


@bp.route('/api/chart/<path:ticker>')
@login_required
def api_chart_data(ticker):
    """Get chart data for a ticker"""
    try:
        logger.info(f"Fetching chart data for ticker: {ticker}")

        # Ensure .IS extension exists
        if not ticker.endswith('.IS'):
            ticker = ticker + '.IS'
            logger.info(f"Added .IS extension: {ticker}")

        # Fetch last 60 days of data
        stock = yf.Ticker(ticker)
        hist = stock.history(period='60d', interval='1d')

        logger.info(f"Fetched {len(hist)} rows for {ticker}")

        if hist.empty:
            logger.warning(f"No data available for {ticker}")
            return jsonify({
                'success': False,
                'error': f'No data available for {ticker}'
            }), 404

        # Format data for frontend
        prices = []
        for date, row in hist.iterrows():
            prices.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        logger.info(f"Successfully formatted {len(prices)} price points for {ticker}")

        return jsonify({
            'success': True,
            'ticker': ticker,
            'prices': prices
        })

    except Exception as e:
        logger.error(f"Error fetching chart data for {ticker}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
