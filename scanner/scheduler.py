"""
Scheduler for automatic daily scans
Uses APScheduler to run scans at specified times
"""

from apscheduler.schedulers.background import BackgroundScheduler
from scanner.config import ScannerConfig
from scanner.data_fetcher import DataFetcher
from scanner.accumulation_detector import AccumulationDetector
from database.db_manager import DatabaseManager
from database.models import db
import logging
import time
import json
from datetime import datetime
import os
import gc
import os as sys_os

logger = logging.getLogger(__name__)


class ScanScheduler:
    """Manages scheduled scans"""

    def __init__(self, app=None):
        """
        Initialize scheduler

        Args:
            app: Flask application instance (optional)
        """
        self.scheduler = BackgroundScheduler(timezone='Europe/Istanbul')
        self.app = app
        self.progress = {"current": 0, "total": 0, "status": "idle", "percent": 0}
        # Dosya yolunu mutlak yol (absolute path) yaparak tüm workerlar için aynı olmasını sağlıyoruz
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.progress_file = os.path.join(root_dir, 'data', 'scan_progress.json')
        # Uygulama başladığında progress dosyasının var olduğundan ve boş olmadığından emin ol
        if not os.path.exists(self.progress_file):
            self._persist_progress() # Başlangıçta idle durumunu dosyaya yaz


    def _persist_progress(self):
        """Save progress to a file so all workers can see it"""
        try:
            data = self.progress.copy()
            data['worker_pid'] = sys_os.getpid()
            data['updated_at'] = datetime.now().isoformat()
            
            # Atomic write: Önce geçici dosyaya yaz, sonra üzerine taşı. 
            # Bu sayede diğer worker'lar asla boş dosya okumaz.
            temp_file = self.progress_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(data, f)
            os.replace(temp_file, self.progress_file)
        except Exception as e:
            logger.error(f"Error persisting progress: {e}")

    def start(self):
        """Start the scheduler with 3 daily scans"""

        # Afternoon scan - 14:00 (mid-day)
        self.scheduler.add_job(
            func=self.run_scan,
            trigger='cron',
            hour=14,
            minute=0,
            day_of_week='mon-fri',
            id='afternoon_scan',
            name='Afternoon BIST Scan (14:00)',
            replace_existing=True
        )

        # End of day scan - 18:30 (after market close)
        self.scheduler.add_job(
            func=self.run_scan,
            trigger='cron',
            hour=18,
            minute=30,
            day_of_week='mon-fri',
            id='eod_scan',
            name='End of Day BIST Scan (18:30)',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started - Daily scans at 14:00 and 18:30")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    def run_scan(self):
        """Execute a full scan of all tickers"""
        if self.app:
            with self.app.app_context():
                self._execute_scan()
        else:
            self._execute_scan()

    def _execute_scan(self):
        """Internal scan execution"""
        # Eğer bir tarama zaten aktif olarak veri işliyorsa, yeni bir taramayı engelle
        if self.progress.get("status") == "running" and self.progress.get("total", 0) > 0:
            logger.warning(f"[PID:{sys_os.getpid()}] Bir tarama zaten devam ediyor. Yeni talep reddedildi.")
            return

        logger.info("=" * 60)
        logger.info(f"[PID:{sys_os.getpid()}] BIST Tarama islemi baslatiliyor...")
        logger.info("=" * 60)

        self.progress.update({"current": 0, "total": 0, "status": "running", "percent": 0})
        self._persist_progress()
        start_time = time.time()
        errors = []

        try:
            # Initialize detector
            detector = AccumulationDetector(ScannerConfig.to_dict())
            
            # Get tickers file path
            tickers_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'tickers.txt'
            )

            # Load tickers
            tickers = DataFetcher.load_tickers_from_file(tickers_path)
            self.progress["total"] = len(tickers)
            self._persist_progress() # Toplam sayiyi aninda dosyaya yaz

            if not tickers:
                error_msg = "No tickers loaded from file"
                logger.error(error_msg)
                errors.append(error_msg)
                DatabaseManager.save_scan_log(
                    total_tickers=0,
                    active_zones=0,
                    completed_zones=0,
                    errors=error_msg,
                    duration=time.time() - start_time
                )
                self.progress["status"] = "idle"
                return

            logger.info(f"Loaded {len(tickers)} tickers")

            # Scan each ticker
            active_zones_count = 0
            completed_zones_count = 0

            logger.info(f"{len(tickers)} hisse icin analiz basladi.")
            for i, ticker in enumerate(tickers):
                try:
                    # BIST formatını (.IS) her işlem öncesi garanti et
                    formatted_ticker = ticker if ticker.endswith('.IS') else f"{ticker}.IS"
                    
                    # Update progress
                    self.progress.update({
                        "current": i + 1,
                        "percent": int(((i + 1) / len(tickers)) * 100)
                    })
                    self._persist_progress() # İlerlemeyi her hissede dosyaya yaz
                    
                    logger.info(f"[{self.progress['percent']}%] Analyzing {formatted_ticker}...")

                    # Fetch individual ticker data
                    df = DataFetcher.fetch_ticker_data(
                        formatted_ticker, 
                        period=ScannerConfig.DATA_PERIOD, 
                        interval=ScannerConfig.DATA_INTERVAL
                    )
                    
                    if df is None or df.empty:
                        continue

                    # Detect zones
                    zones = detector.detect_zones(formatted_ticker, df)

                    # ÖNEMLİ: Yeni sonuçları kaydetmeden önce bu hissenin TÜM eski aktif bloklarını 'broken' yapalım.
                    # Eğer save_zone içinde bu blok hala bulunursa tekrar 'active' yapılacaktır.
                    DatabaseManager.mark_zones_as_broken(formatted_ticker)

                    if zones:
                        # Save detected zones
                        for zone in zones:
                            saved_zone = DatabaseManager.save_zone(zone)

                            if saved_zone:
                                if zone.status == 'active':
                                    active_zones_count += 1
                                else:
                                    completed_zones_count += 1
                    else:
                        # No zones found - mark existing as broken
                        DatabaseManager.mark_zones_as_broken(formatted_ticker)

                except Exception as e:
                    error_msg = f"Hata: {ticker} analizi sirasinda hata: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                finally:
                    # Bellek yönetimi: Büyük veri çerçevesini temizle
                    if 'df' in locals():
                        del df
                
                # Her 20 hissede bir agresif bellek temizliği
                if i % 20 == 0:
                    gc.collect()

            # Eski verileri temizle
            try:
                deleted_count = DatabaseManager.cleanup_old_zones(days=ScannerConfig.COMPLETED_ZONE_RETENTION_DAYS)
                logger.info(f"Eski veriler temizlendi: {deleted_count} kayit.")
            except Exception as e:
                logger.error(f"Temizlik sirasinda hata: {e}")

            # Save scan log
            duration = time.time() - start_time
            DatabaseManager.save_scan_log(
                total_tickers=len(tickers),
                active_zones=active_zones_count,
                completed_zones=completed_zones_count,
                errors='\n'.join(errors) if errors else None,
                duration=duration
            )

            logger.info("=" * 60)
            logger.info(f"Scan completed in {duration:.2f} seconds")
            logger.info(f"Active zones: {active_zones_count}")
            logger.info(f"Completed zones: {completed_zones_count}")
            logger.info(f"Errors: {len(errors)}")
            logger.info("=" * 60)

            self.progress.update({"status": "idle"})
            self._persist_progress()

        except Exception as e:
            error_msg = f"KRITIK HATA: {str(e)}"
            logger.error(error_msg)
            self.progress.update({"status": "idle"})
            self._persist_progress()
            try:
                DatabaseManager.save_scan_log(
                    total_tickers=len(tickers) if 'tickers' in locals() else 0,
                    active_zones=active_zones_count if 'active_zones_count' in locals() else 0,
                    completed_zones=completed_zones_count if 'completed_zones_count' in locals() else 0,
                    errors=error_msg,
                    duration=time.time() - start_time
                )
            except:
                pass


def run_manual_scan():
    """Run a manual scan (for testing)"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from app_config import create_app

    app = create_app()

    with app.app_context():
        scheduler = ScanScheduler(app)
        scheduler.run_scan()


if __name__ == '__main__':
    # Allow manual execution for testing
    run_manual_scan()
