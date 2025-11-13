"""
Data fetching module using yfinance
Fetches BIST stock data for analysis
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches stock data from Yahoo Finance"""

    @staticmethod
    def fetch_ticker_data(ticker, period="30d", interval="1d"):
        """
        Fetch historical data for a single ticker

        Args:
            ticker: Stock symbol (e.g., 'THYAO')
            period: Data period (default: 30d)
            interval: Data interval (default: 1d for daily)

        Returns:
            pandas DataFrame with OHLCV data or None if error
        """
        try:
            # Convert BIST ticker to Yahoo Finance format
            yahoo_ticker = f"{ticker}.IS" if not ticker.endswith('.IS') else ticker

            logger.info(f"Fetching data for {yahoo_ticker}")

            # Download data
            stock = yf.Ticker(yahoo_ticker)
            df = stock.history(period=period, interval=interval)

            if df.empty:
                logger.warning(f"No data found for {yahoo_ticker}")
                return None

            # Reset index to make Date a column
            df = df.reset_index()

            # Keep only necessary columns
            required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df = df[required_columns]

            # Remove timezone info from Date column if present
            if df['Date'].dt.tz is not None:
                df['Date'] = df['Date'].dt.tz_localize(None)

            logger.info(f"Successfully fetched {len(df)} rows for {yahoo_ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return None

    @staticmethod
    def fetch_multiple_tickers(tickers, period="30d", interval="1d", chunk_size=10):
        """
        Fetch data for multiple tickers in chunks

        Args:
            tickers: List of stock symbols
            period: Data period
            interval: Data interval
            chunk_size: Number of tickers to process at once

        Returns:
            Dictionary {ticker: DataFrame}
        """
        results = {}
        total = len(tickers)

        for i in range(0, total, chunk_size):
            chunk = tickers[i:i + chunk_size]
            logger.info(f"Processing chunk {i//chunk_size + 1} ({i+1}-{min(i+chunk_size, total)} of {total})")

            for ticker in chunk:
                df = DataFetcher.fetch_ticker_data(ticker, period, interval)
                if df is not None:
                    results[ticker] = df

        logger.info(f"Successfully fetched data for {len(results)}/{total} tickers")
        return results

    @staticmethod
    def load_tickers_from_file(filepath):
        """
        Load ticker symbols from text file

        Args:
            filepath: Path to tickers.txt file

        Returns:
            List of ticker symbols
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tickers = [line.strip() for line in f if line.strip()]

            logger.info(f"Loaded {len(tickers)} tickers from {filepath}")
            return tickers

        except Exception as e:
            logger.error(f"Error loading tickers from {filepath}: {str(e)}")
            return []
