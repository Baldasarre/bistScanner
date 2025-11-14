"""
Database manager for CRUD operations
"""

from database.models import db, Zone, ScoreHistory, ScanLog
from datetime import datetime, timedelta, date
import logging
import numpy as np

logger = logging.getLogger(__name__)


def convert_numpy_types(value):
    """Convert numpy types to Python native types"""
    if isinstance(value, (np.integer, np.floating)):
        return float(value)
    return value


class DatabaseManager:
    """Manages database operations for zones and scan logs"""

    @staticmethod
    def save_zone(zone_obj):
        """
        Save or update an accumulation zone

        Args:
            zone_obj: AccumulationZone object from detector

        Returns:
            Zone model instance
        """
        try:
            # Check if zone already exists (same ticker and overlapping dates)
            existing = Zone.query.filter_by(
                ticker=zone_obj.ticker,
                start_date=zone_obj.start_date.date() if isinstance(zone_obj.start_date, datetime) else zone_obj.start_date,
                status='active'
            ).first()

            if existing:
                # Update existing zone
                existing.end_date = zone_obj.end_date.date() if isinstance(zone_obj.end_date, datetime) else zone_obj.end_date
                existing.candle_count = zone_obj.candle_count
                existing.score = convert_numpy_types(zone_obj.score)
                existing.total_diff_percent = convert_numpy_types(zone_obj.total_diff_percent)
                existing.avg_rsi = convert_numpy_types(zone_obj.avg_rsi)
                existing.highest_body = convert_numpy_types(zone_obj.highest_body)
                existing.lowest_body = convert_numpy_types(zone_obj.lowest_body)
                existing.status = zone_obj.status
                existing.last_updated = datetime.utcnow()

                # Add score history
                DatabaseManager._add_score_history(existing)

                db.session.commit()
                logger.info(f"Updated zone: {existing}")
                return existing
            else:
                # Create new zone
                new_zone = Zone(
                    ticker=zone_obj.ticker,
                    start_date=zone_obj.start_date.date() if isinstance(zone_obj.start_date, datetime) else zone_obj.start_date,
                    end_date=zone_obj.end_date.date() if isinstance(zone_obj.end_date, datetime) else zone_obj.end_date,
                    candle_count=zone_obj.candle_count,
                    score=convert_numpy_types(zone_obj.score),
                    total_diff_percent=convert_numpy_types(zone_obj.total_diff_percent),
                    avg_rsi=convert_numpy_types(zone_obj.avg_rsi),
                    highest_body=convert_numpy_types(zone_obj.highest_body),
                    lowest_body=convert_numpy_types(zone_obj.lowest_body),
                    status=zone_obj.status
                )
                db.session.add(new_zone)
                db.session.commit()

                # Add initial score history
                DatabaseManager._add_score_history(new_zone)

                logger.info(f"Created new zone: {new_zone}")
                return new_zone

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving zone: {str(e)}")
            return None

    @staticmethod
    def _add_score_history(zone):
        """Add score history entry for a zone"""
        try:
            today = date.today()

            # Check if already recorded today
            existing_history = ScoreHistory.query.filter_by(
                zone_id=zone.id,
                date=today
            ).first()

            if existing_history:
                # Update existing
                old_score = existing_history.score
                existing_history.score = zone.score
                existing_history.score_change = zone.score - old_score
                existing_history.candle_count = zone.candle_count
            else:
                # Get yesterday's score for change calculation
                yesterday_history = ScoreHistory.query.filter_by(
                    zone_id=zone.id
                ).order_by(ScoreHistory.date.desc()).first()

                score_change = 0
                if yesterday_history:
                    score_change = zone.score - yesterday_history.score

                # Create new history entry
                history = ScoreHistory(
                    zone_id=zone.id,
                    date=today,
                    score=zone.score,
                    score_change=score_change,
                    candle_count=zone.candle_count
                )
                db.session.add(history)

            db.session.commit()

        except Exception as e:
            logger.error(f"Error adding score history: {str(e)}")

    @staticmethod
    def get_active_zones():
        """Get all active zones"""
        return Zone.query.filter_by(status='active').order_by(Zone.score.desc()).all()

    @staticmethod
    def get_completed_zones(days=21):
        """
        Get completed zones from the last N days (default: 3 weeks)
        Only returns zones with score >= 50

        Args:
            days: Number of days to look back (default: 21)

        Returns:
            List of Zone objects
        """
        cutoff_date = date.today() - timedelta(days=days)
        return Zone.query.filter(
            Zone.status.in_(['completed', 'broken']),
            Zone.end_date >= cutoff_date,
            Zone.score >= 50
        ).order_by(Zone.end_date.desc()).all()

    @staticmethod
    def get_zone_with_history(zone_id):
        """Get a zone with its score history"""
        zone = Zone.query.get(zone_id)
        if zone:
            history = ScoreHistory.query.filter_by(zone_id=zone_id).order_by(ScoreHistory.date).all()
            return zone, history
        return None, []

    @staticmethod
    def mark_zones_as_broken(ticker):
        """
        Mark active zones for a ticker as broken if no longer detected

        Args:
            ticker: Stock symbol
        """
        try:
            active_zones = Zone.query.filter_by(ticker=ticker, status='active').all()

            for zone in active_zones:
                zone.status = 'broken'
                zone.last_updated = datetime.utcnow()

            db.session.commit()
            logger.info(f"Marked {len(active_zones)} zones as broken for {ticker}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking zones as broken: {str(e)}")

    @staticmethod
    def cleanup_old_zones(days=7):
        """
        Delete completed/broken zones older than N days

        Args:
            days: Retention period in days
        """
        try:
            cutoff_date = date.today() - timedelta(days=days)

            deleted = Zone.query.filter(
                Zone.status.in_(['completed', 'broken']),
                Zone.end_date < cutoff_date
            ).delete()

            db.session.commit()
            logger.info(f"Deleted {deleted} old zones")
            return deleted

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cleaning up old zones: {str(e)}")
            return 0

    @staticmethod
    def save_scan_log(total_tickers, active_zones, completed_zones, errors, duration):
        """
        Save scan execution log

        Args:
            total_tickers: Total number of tickers scanned
            active_zones: Number of active zones found
            completed_zones: Number of completed zones
            errors: Error messages (string)
            duration: Scan duration in seconds
        """
        try:
            log = ScanLog(
                total_tickers=total_tickers,
                active_zones_found=active_zones,
                completed_zones=completed_zones,
                errors=errors,
                duration_seconds=duration
            )
            db.session.add(log)
            db.session.commit()
            logger.info(f"Saved scan log: {log}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving scan log: {str(e)}")

    @staticmethod
    def get_latest_scan_log():
        """Get the most recent scan log"""
        return ScanLog.query.order_by(ScanLog.scan_date.desc()).first()

    @staticmethod
    def get_zone_score_change(zone_id):
        """Get latest score change for a zone"""
        latest = ScoreHistory.query.filter_by(zone_id=zone_id).order_by(
            ScoreHistory.date.desc()
        ).first()

        return latest.score_change if latest else 0
