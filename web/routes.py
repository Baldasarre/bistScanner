"""
Flask routes for the BIST scanner application
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from database.db_manager import DatabaseManager
from database.models import db, Zone, ZoneComment
from web.auth import authenticate_user
import logging

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('main', __name__)


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
        zones = DatabaseManager.get_active_zones()

        # Add score change and last comment to each zone
        zones_data = []
        for zone in zones:
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
        days = request.args.get('days', 21, type=int)
        zones = DatabaseManager.get_completed_zones(days=days)

        # Add last comment to each zone
        zones_data = []
        for zone in zones:
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

        return jsonify({
            'success': True,
            'scan_log': scan_log.to_dict()
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


@bp.route('/api/keepalive')
def api_keepalive():
    """Keep the service awake - called by cron jobs before scheduled scans"""
    from datetime import datetime
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Service is running'
    })


