"""
Flask application configuration and factory
"""

import os
from flask import Flask
from database.models import db
from web.auth import init_auth, load_users_from_config, create_sample_users_config
from web.routes import bp
from scanner.scheduler import ScanScheduler
import logging


def create_app(config=None):
    """
    Application factory

    Args:
        config: Configuration dictionary (optional)

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Default configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(os.path.dirname(__file__), 'data', 'bist_scanner.db')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Override with custom config if provided
    if config:
        app.config.update(config)

    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)

    # Initialize database
    db.init_app(app)

    # Initialize authentication
    init_auth(app)

    # Register blueprints
    app.register_blueprint(bp)

    # Create database tables
    with app.app_context():
        db.create_all()

        # Create sample users config if doesn't exist
        create_sample_users_config()

        # Load users from config
        load_users_from_config()

    # Initialize and start scheduler
    if os.environ.get('FLASK_ENV') != 'development' or os.environ.get('START_SCHEDULER', 'true').lower() == 'true':
        scheduler = ScanScheduler(app)
        scheduler.start()

        # Store scheduler in app for cleanup
        app.scheduler = scheduler

    return app


def setup_logging():
    """Setup logging configuration"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'scanner.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Set yfinance logging to WARNING to reduce noise
    logging.getLogger('yfinance').setLevel(logging.WARNING)
