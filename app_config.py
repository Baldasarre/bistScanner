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
from sqlalchemy import text

logger = logging.getLogger(__name__)

def run_migrations():
    """Run database migrations for PostgreSQL"""

    try:
        # Check if we're using PostgreSQL
        # Using engine.name is more reliable than parsing the URL drivername
        driver_name = db.engine.name
        if 'postgresql' not in driver_name and 'postgres' not in driver_name:
            logger.info(f"Database engine is {driver_name}, skipping PostgreSQL specific migrations")
            return

        logger.info("Running PostgreSQL migrations...")

        # Add is_flagged column if it doesn't exist
        try:
            db.session.execute(text("ALTER TABLE zones ADD COLUMN is_flagged BOOLEAN DEFAULT FALSE"))
            db.session.commit()
            logger.info("[Migration] Added is_flagged column to zones table")
        except Exception as e:
            db.session.rollback()
            if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                logger.info("[Migration] is_flagged column already exists")
            else:
                logger.error(f"[Migration] Error adding is_flagged column: {e}")

        # Create zone_comments table if it doesn't exist
        try:
            db.session.execute(text("""
                CREATE TABLE zone_comments (
                    id SERIAL PRIMARY KEY,
                    zone_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """))
            db.session.commit()
            logger.info("[Migration] Created zone_comments table")
        except Exception as e:
            db.session.rollback()
            if 'already exists' in str(e).lower():
                logger.info("[Migration] zone_comments table already exists")
            else:
                logger.error(f"[Migration] Error creating zone_comments table: {e}")

        logger.info("[Migration] Migrations completed successfully")

    except Exception as e:
        logger.error(f"[Migration] Fatal error during migrations: {e}")
        db.session.rollback()


def create_app(config=None):
    """
    Application factory

    Args:
        config: Configuration dictionary (optional)

    Returns:
        Flask application instance
    """
    # Initialize logging if in production/gunicorn context
    setup_logging()
    
    app = Flask(__name__)

    # Default configuration
    # Production should use a persistent SECRET_KEY to keep user sessions alive after restarts
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key and not app.debug:
        logger.warning("No SECRET_KEY set in production! Sessions will not persist.")
    app.config['SECRET_KEY'] = secret_key or os.urandom(24).hex()
    
    # Compatibility fix for various PostgreSQL providers
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or \
        f"sqlite:///{os.path.join(os.path.dirname(__file__), 'data', 'bist_scanner.db')}"
        
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

        # Run migrations if using PostgreSQL
        run_migrations()

        # Create sample users config if doesn't exist
        create_sample_users_config()

        # Load users from config
        load_users_from_config()

    # Initialize and start scheduler
    should_start = any([
        os.environ.get('START_SCHEDULER', 'true').lower() == 'true',
        not app.debug
    ])

    if should_start:
        logger.info("Initializing APScheduler for background scans...")
        scheduler = ScanScheduler(app)
        scheduler.start()

        # Store scheduler in app for cleanup
        app.scheduler = scheduler

    return app


def setup_logging():
    """Setup logging configuration"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logging.getLogger().hasHandlers():
        return

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'scanner.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Gunicorn loglarını Flask logger'a aktar (Production ortamı için)
    if 'gunicorn' in os.environ.get('SERVER_SOFTWARE', ''):
        gunicorn_logger = logging.getLogger('gunicorn.error')
        logging.getLogger('flask.app').handlers = gunicorn_logger.handlers
        logging.getLogger('flask.app').setLevel(logging.INFO)

    # Set yfinance logging to WARNING to reduce noise
    logging.getLogger('yfinance').setLevel(logging.WARNING)
