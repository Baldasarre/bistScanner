"""
Test scanner - runs a quick scan with limited tickers
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app_config import create_app, setup_logging
from scanner.data_fetcher import DataFetcher
from scanner.accumulation_detector import AccumulationDetector
from scanner.config import ScannerConfig
from database.db_manager import DatabaseManager
import logging
import time
logger = logging.getLogger(__name__)

def run_test_scan():
    """Run a test scan with limited tickers"""
    setup_logging()
    app = create_app()

    with app.app_context():
        logger.info("=" * 60)
        logger.info("STARTING TEST SCAN (20 hisse)")
        logger.info("=" * 60)

        start_time = time.time()

        # Load test tickers
        tickers = DataFetcher.load_tickers_from_file('tickers.txt')
        logger.info(f"Loaded {len(tickers)} tickers")

        # Fetch data
        logger.info("Fetching market data...")
        ticker_data = DataFetcher.fetch_multiple_tickers(
            tickers,
            period=ScannerConfig.DATA_PERIOD,
            interval=ScannerConfig.DATA_INTERVAL,
            chunk_size=5
        )

        if not ticker_data:
            logger.error("❌ Veri çekilemedi. İnternet bağlantınızı veya tickers.txt dosyasını kontrol edin.")
            return

        # Initialize detector
        detector = AccumulationDetector(ScannerConfig.to_dict())

        # Scan each ticker
        active_zones = 0
        completed_zones = 0
        processed_count = 0

        for ticker, df in ticker_data.items():
            if df is None or df.empty:
                logger.warning(f"⚠️ {ticker} için veri boş, atlanıyor.")
                continue
                
            processed_count += 1
            logger.info(f"🔍 Analyzing {ticker} ({processed_count}/{len(ticker_data)})...")
            zones = detector.detect_zones(ticker, df)

            for zone in zones:
                saved = DatabaseManager.save_zone(zone)
                if saved:
                    if zone.status == 'active':
                        active_zones += 1
                    else:
                        completed_zones += 1

        duration = time.time() - start_time

        # Save scan log
        DatabaseManager.save_scan_log(
            total_tickers=len(tickers),
            active_zones=active_zones,
            completed_zones=completed_zones,
            errors=None,
            duration=duration
        )

        logger.info("=" * 60)
        logger.info(f"TEST SCAN COMPLETED in {duration:.2f} seconds")
        logger.info(f"Active zones: {active_zones}")
        logger.info(f"Completed zones: {completed_zones}")
        logger.info("=" * 60)

if __name__ == '__main__':
    run_test_scan()
