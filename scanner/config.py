"""
Scanner configuration parameters
Matches the Pine Script indicator settings
"""


class ScannerConfig:
    """Configuration for accumulation zone detection"""

    # Filter parameters (from Pine Script)
    MAX_LINK_DIFF = 3.0  # Maximum % difference between consecutive closes
    MAX_BODY_DIFF = 4.0  # Maximum % candle body size
    MAX_TOTAL_ZONE_DIFF = 6.0  # Maximum % total zone width
    MIN_CANDLE_COUNT = 4  # Minimum candles required for a zone

    # RSI parameters
    RSI_LENGTH = 14  # RSI period
    RSI_MAX_LIMIT = 100.0  # Maximum RSI during zone formation

    # Scoring parameters
    SCORE_DIFF_MIN = 2.0  # Zone width % for full compression score
    SCORE_RSI_MIN = 30.0  # RSI for full oversold score
    SCORE_RSI_MAX = 70.0  # RSI for zero oversold score
    SCORE_CANDLE_MAX = 20  # Candle count for full duration score
    MIN_SCORE_TO_SAVE = 30  # Minimum score threshold

    # Data fetching
    DATA_PERIOD = "30d"  # How much historical data to fetch
    DATA_INTERVAL = "1d"  # Daily candles

    # Scan timing - default values (can be overridden by SCAN_HOUR and SCAN_MINUTE env vars in scheduler)
    SCAN_HOUR = 18  # 18:30 (after market close)
    SCAN_MINUTE = 30

    # Database retention
    COMPLETED_ZONE_RETENTION_DAYS = 21  # Keep completed zones for 3 weeks (21 days)

    @classmethod
    def to_dict(cls):
        """Return config as dictionary"""
        return {
            'max_link_diff': cls.MAX_LINK_DIFF,
            'max_body_diff': cls.MAX_BODY_DIFF,
            'max_total_zone_diff': cls.MAX_TOTAL_ZONE_DIFF,
            'min_candle_count': cls.MIN_CANDLE_COUNT,
            'rsi_length': cls.RSI_LENGTH,
            'rsi_max_limit': cls.RSI_MAX_LIMIT,
            'score_diff_min': cls.SCORE_DIFF_MIN,
            'score_rsi_min': cls.SCORE_RSI_MIN,
            'score_rsi_max': cls.SCORE_RSI_MAX,
            'score_candle_max': cls.SCORE_CANDLE_MAX,
            'min_score': cls.MIN_SCORE_TO_SAVE
        }
