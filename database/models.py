"""
Database models for the BIST scanner application
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication"""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'


class Zone(db.Model):
    """Accumulation zone model"""

    __tablename__ = 'zones'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    candle_count = db.Column(db.Integer)
    score = db.Column(db.Float)
    highest_body = db.Column(db.Float)
    lowest_body = db.Column(db.Float)
    total_diff_percent = db.Column(db.Float)
    avg_rsi = db.Column(db.Float)
    status = db.Column(db.String(20), index=True)  # 'active', 'completed', 'broken'
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    score_history = db.relationship('ScoreHistory', backref='zone', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('ZoneComment', backref='zone', lazy=True, cascade='all, delete-orphan', order_by='ZoneComment.created_at.desc()')
    is_flagged = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Convert zone to dictionary"""
        return {
            'id': self.id,
            'ticker': self.ticker,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'candle_count': self.candle_count,
            'score': self.score,
            'highest_body': self.highest_body,
            'lowest_body': self.lowest_body,
            'total_diff_percent': self.total_diff_percent,
            'avg_rsi': self.avg_rsi,
            'status': self.status,
            'is_flagged': self.is_flagged,
            'comment_count': len(self.comments) if self.comments else 0,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Zone {self.ticker} {self.start_date} score={self.score}>'


class ZoneComment(db.Model):
    """Comments on zones"""

    __tablename__ = 'zone_comments'

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to user
    user = db.relationship('User', backref='comments')

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'zone_id': self.zone_id,
            'username': self.user.username if self.user else 'Unknown',
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ZoneComment zone={self.zone_id} user={self.user_id}>'


class ScoreHistory(db.Model):
    """Score change history for zones"""

    __tablename__ = 'score_history'

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    score = db.Column(db.Float)
    score_change = db.Column(db.Float)  # Change from previous day
    candle_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'zone_id': self.zone_id,
            'date': self.date.isoformat() if self.date else None,
            'score': self.score,
            'score_change': self.score_change,
            'candle_count': self.candle_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ScoreHistory zone={self.zone_id} date={self.date} score={self.score}>'


class ScanLog(db.Model):
    """Scan execution log"""

    __tablename__ = 'scan_logs'

    id = db.Column(db.Integer, primary_key=True)
    scan_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_tickers = db.Column(db.Integer)
    active_zones_found = db.Column(db.Integer)
    completed_zones = db.Column(db.Integer)
    errors = db.Column(db.Text)
    duration_seconds = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'scan_date': self.scan_date.isoformat() if self.scan_date else None,
            'total_tickers': self.total_tickers,
            'active_zones_found': self.active_zones_found,
            'completed_zones': self.completed_zones,
            'errors': self.errors,
            'duration_seconds': self.duration_seconds,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ScanLog {self.scan_date} tickers={self.total_tickers}>'


# Future: Institutional data (Phase 2)
class InstitutionalData(db.Model):
    """Broker/institutional trading data (for future use)"""

    __tablename__ = 'institutional_data'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    broker_name = db.Column(db.String(100))
    net_lot = db.Column(db.Integer)
    net_percent = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<InstitutionalData {self.ticker} {self.date}>'
