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
from datetime import datetime
import os

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

    def start(self):
        """Start the scheduler"""
        # Schedule daily scan
        scan_hour = ScannerConfig.get_scan_hour()
        scan_minute = ScannerConfig.get_scan_minute()

        self.scheduler.add_job(
            func=self.run_scan,
            trigger='cron',
            hour=scan_hour,
            minute=scan_minute,
            id='daily_scan',
            name='Daily BIST Scan',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f"Scheduler started - Daily scan at {scan_hour}:{scan_minute:02d}")

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
        logger.info("=" * 60)
        logger.info("Starting scheduled scan")
        logger.info("=" * 60)

        start_time = time.time()
        errors = []

        try:
            # Get tickers file path
            tickers_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'tickers.txt'
            )

            # Load tickers
            tickers = DataFetcher.load_tickers_from_file(tickers_path)

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
                return

            logger.info(f"Loaded {len(tickers)} tickers")

            # Fetch data for all tickers
            logger.info("Fetching market data...")
            ticker_data = DataFetcher.fetch_multiple_tickers(
                tickers,
                period=ScannerConfig.DATA_PERIOD,
                interval=ScannerConfig.DATA_INTERVAL
            )

            # Initialize detector
            detector = AccumulationDetector(ScannerConfig.to_dict())

            # Scan each ticker
            active_zones_count = 0
            completed_zones_count = 0

            for ticker, df in ticker_data.items():
                try:
                    logger.info(f"Analyzing {ticker}...")

                    # Detect zones
                    zones = detector.detect_zones(ticker, df)

                    if zones:
                        # Mark old active zones as broken if not in new results
                        existing_actives = [z for z in zones if z.status == 'active']

                        if not existing_actives:
                            # No active zones found - mark existing as broken
                            DatabaseManager.mark_zones_as_broken(ticker)

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
                        DatabaseManager.mark_zones_as_broken(ticker)

                except Exception as e:
                    error_msg = f"Error analyzing {ticker}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Cleanup old zones
            deleted_count = DatabaseManager.cleanup_old_zones(
                days=ScannerConfig.COMPLETED_ZONE_RETENTION_DAYS
            )
            logger.info(f"Cleaned up {deleted_count} old zones")

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

        except Exception as e:
            error_msg = f"Fatal error during scan: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            DatabaseManager.save_scan_log(
                total_tickers=len(tickers) if 'tickers' in locals() else 0,
                active_zones=active_zones_count if 'active_zones_count' in locals() else 0,
                completed_zones=completed_zones_count if 'completed_zones_count' in locals() else 0,
                errors='\n'.join(errors),
                duration=time.time() - start_time
            )


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
