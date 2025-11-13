"""
Accumulation Zone Detector
Translates Pine Script logic to Python for detecting consolidation/accumulation zones
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_rsi(series, period=14):
    """
    Calculate RSI (Relative Strength Index)

    Args:
        series: pandas Series of prices
        period: RSI period (default 14)

    Returns:
        pandas Series of RSI values
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


class AccumulationZone:
    """Represents a single accumulation zone"""

    def __init__(self, ticker, start_date, end_date, candle_count, score,
                 total_diff_percent, avg_rsi, highest_body, lowest_body, status='active'):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.candle_count = candle_count
        self.score = score
        self.total_diff_percent = total_diff_percent
        self.avg_rsi = avg_rsi
        self.highest_body = highest_body
        self.lowest_body = lowest_body
        self.status = status  # 'active', 'completed', 'broken'

    def to_dict(self):
        """Convert zone to dictionary"""
        return {
            'ticker': self.ticker,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'candle_count': self.candle_count,
            'score': self.score,
            'total_diff_percent': self.total_diff_percent,
            'avg_rsi': self.avg_rsi,
            'highest_body': self.highest_body,
            'lowest_body': self.lowest_body,
            'status': self.status
        }

    def __repr__(self):
        return (f"AccumulationZone({self.ticker}, {self.start_date} to {self.end_date}, "
                f"score={self.score:.1f}, candles={self.candle_count}, status={self.status})")


class AccumulationDetector:
    """Detects accumulation zones using Pine Script algorithm"""

    def __init__(self, config):
        """
        Initialize detector with configuration

        Args:
            config: Dictionary with detection parameters
        """
        self.max_link_diff = config['max_link_diff']
        self.max_body_diff = config['max_body_diff']
        self.max_total_zone_diff = config['max_total_zone_diff']
        self.min_candle_count = config['min_candle_count']
        self.rsi_length = config['rsi_length']
        self.rsi_max_limit = config['rsi_max_limit']
        self.score_diff_min = config['score_diff_min']
        self.score_rsi_min = config['score_rsi_min']
        self.score_rsi_max = config['score_rsi_max']
        self.score_candle_max = config['score_candle_max']
        self.min_score = config['min_score']

    def detect_zones(self, ticker, df):
        """
        Detect accumulation zones in price data

        Args:
            ticker: Stock symbol
            df: pandas DataFrame with columns: Date, Open, High, Low, Close, Volume

        Returns:
            List of AccumulationZone objects
        """
        if df is None or len(df) < self.min_candle_count + 1:
            logger.warning(f"{ticker}: Insufficient data for analysis")
            return []

        # Make a copy to avoid modifying original
        df = df.copy()

        # Calculate RSI
        df['RSI'] = calculate_rsi(df['Close'], period=self.rsi_length)

        # Calculate candle bodies
        df['BodyLow'] = df[['Open', 'Close']].min(axis=1)
        df['BodyHigh'] = df[['Open', 'Close']].max(axis=1)

        # Drop NaN rows (from RSI calculation)
        df = df.dropna()

        if len(df) < self.min_candle_count + 1:
            logger.warning(f"{ticker}: Insufficient data after RSI calculation")
            return []

        # Reset index after dropping NaN
        df = df.reset_index(drop=True)

        # Scan for zones
        zones = []
        in_zone = False
        zone_data = None

        for i in range(1, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i - 1]

            # Calculate body difference (%)
            body_diff = abs(current['BodyHigh'] - current['BodyLow'])
            body_diff_percent = (body_diff / current['Open']) * 100 if current['Open'] != 0 else 0

            # Calculate link difference (%)
            link_diff = abs(current['Close'] - prev['Close'])
            link_diff_percent = (link_diff / prev['Close']) * 100 if prev['Close'] != 0 else 0

            # Check filters
            rsi_ok = current['RSI'] <= self.rsi_max_limit
            body_ok = body_diff_percent <= self.max_body_diff
            link_ok = link_diff_percent <= self.max_link_diff

            if not in_zone:
                # Try to start a new zone
                if body_ok and rsi_ok:
                    in_zone = True
                    zone_data = {
                        'start_idx': i,
                        'candles': [i],
                        'highest_body': current['BodyHigh'],
                        'lowest_body': current['BodyLow'],
                        'rsi_values': [current['RSI']]
                    }
                    logger.debug(f"{ticker}: Zone started at index {i} ({current['Date'].date()})")
            else:
                # Zone is active - check if it continues
                # Calculate POTENTIAL new boundaries (Pine Script satır 113-118)
                temp_highest = max(zone_data['highest_body'], current['BodyHigh'])
                temp_lowest = min(zone_data['lowest_body'], current['BodyLow'])

                total_diff = temp_highest - temp_lowest
                total_diff_percent = (total_diff / temp_lowest) * 100 if temp_lowest != 0 else 0

                zone_ok = (body_ok and link_ok and rsi_ok and
                          total_diff_percent <= self.max_total_zone_diff)

                if zone_ok:
                    # Zone continues - update with temp values
                    zone_data['candles'].append(i)
                    zone_data['highest_body'] = temp_highest
                    zone_data['lowest_body'] = temp_lowest
                    zone_data['rsi_values'].append(current['RSI'])
                else:
                    # Zone ended
                    zone = self._finalize_zone(ticker, zone_data, df, status='completed')
                    if zone and zone.score >= self.min_score:
                        zones.append(zone)
                        logger.info(f"{ticker}: {zone}")

                    # Pine Script satır 129-138: Zone bittikten sonra YENİ zone başlat mı?
                    if body_ok and rsi_ok:
                        # Yeni zone başlat (mevcut mum ile)
                        in_zone = True
                        zone_data = {
                            'start_idx': i,
                            'candles': [i],
                            'highest_body': current['BodyHigh'],
                            'lowest_body': current['BodyLow'],
                            'rsi_values': [current['RSI']]
                        }
                        logger.debug(f"{ticker}: New zone started immediately at index {i}")
                    else:
                        in_zone = False
                        zone_data = None

        # Finalize active zone at the end (if any)
        if in_zone and zone_data:
            zone = self._finalize_zone(ticker, zone_data, df, status='active')
            if zone and zone.score >= self.min_score:
                zones.append(zone)
                logger.info(f"{ticker}: {zone} (ACTIVE)")

        logger.info(f"{ticker}: Found {len(zones)} zones")
        return zones

    def _finalize_zone(self, ticker, zone_data, df, status='completed'):
        """
        Calculate zone score and create AccumulationZone object

        Args:
            ticker: Stock symbol
            zone_data: Dictionary with zone information
            df: Price data DataFrame
            status: Zone status ('active' or 'completed')

        Returns:
            AccumulationZone object or None if doesn't meet minimum requirements
        """
        candle_count = len(zone_data['candles'])

        # Pine Script satır 79: Minimum mum sayısı kontrolü
        if candle_count < self.min_candle_count:
            return None

        # Calculate total zone width
        total_diff = zone_data['highest_body'] - zone_data['lowest_body']
        total_diff_percent = (total_diff / zone_data['lowest_body']) * 100 if zone_data['lowest_body'] != 0 else 0

        # Calculate average RSI
        avg_rsi = sum(zone_data['rsi_values']) / len(zone_data['rsi_values'])

        # --- SCORING (Pine Script exact logic) ---

        # 1. Compression Score (0-33.33 points)
        # Tighter zones get higher scores
        compression_score = 33.33 * (
            (self.max_total_zone_diff - total_diff_percent) /
            (self.max_total_zone_diff - self.score_diff_min)
        )
        compression_score = max(0, min(33.33, compression_score))

        # 2. RSI Score (0-33.33 points)
        # Lower RSI (more oversold) gets higher scores
        rsi_score = 33.33 * (
            (self.score_rsi_max - avg_rsi) /
            (self.score_rsi_max - self.score_rsi_min)
        )
        rsi_score = max(0, min(33.33, rsi_score))

        # 3. Duration Score (0-33.33 points)
        # More candles get higher scores
        duration_score = 33.33 * (
            (candle_count - self.min_candle_count) /
            (self.score_candle_max - self.min_candle_count)
        )
        duration_score = max(0, min(33.33, duration_score))

        # Total score
        total_score = compression_score + rsi_score + duration_score

        # Get dates
        start_idx = zone_data['start_idx']
        end_idx = zone_data['candles'][-1]
        start_date = df.iloc[start_idx]['Date']
        end_date = df.iloc[end_idx]['Date']

        return AccumulationZone(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            candle_count=candle_count,
            score=round(total_score, 1),
            total_diff_percent=round(total_diff_percent, 2),
            avg_rsi=round(avg_rsi, 1),
            highest_body=zone_data['highest_body'],
            lowest_body=zone_data['lowest_body'],
            status=status
        )
