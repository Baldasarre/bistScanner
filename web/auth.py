"""
Authentication module
Handles user login and session management
"""

import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
from database.models import db, User
import logging

logger = logging.getLogger(__name__)

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))


def init_auth(app):
    """
    Initialize authentication system

    Args:
        app: Flask application instance
    """
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = None


def load_users_from_config():
    """
    Load users from config/users.json and sync with database

    Returns:
        Number of users loaded
    """
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'users.json')

        if not os.path.exists(config_path):
            logger.warning(f"users.json not found at {config_path}")
            return 0

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        users = data.get('users', [])

        for user_data in users:
            username = user_data.get('username')
            password = user_data.get('password')

            if not username or not password:
                logger.warning(f"Invalid user data: {user_data}")
                continue

            # Check if user exists
            existing_user = User.query.filter_by(username=username).first()

            if existing_user:
                # Update password if changed
                if not check_password_hash(existing_user.password_hash, password):
                    existing_user.password_hash = generate_password_hash(password)
                    logger.info(f"Updated password for user: {username}")
            else:
                # Create new user
                new_user = User(
                    username=username,
                    password_hash=generate_password_hash(password)
                )
                db.session.add(new_user)
                logger.info(f"Created new user: {username}")

        db.session.commit()
        logger.info(f"Loaded {len(users)} users from config")
        return len(users)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error loading users from config: {str(e)}")
        return 0


def create_sample_users_config():
    """
    Create a sample users.json file if it doesn't exist

    Returns:
        Path to the created file
    """
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
    config_path = os.path.join(config_dir, 'users.json')

    if os.path.exists(config_path):
        return config_path

    os.makedirs(config_dir, exist_ok=True)

    sample_data = {
        "users": [
            {
                "username": "admin",
                "password": "admin123"
            }
        ]
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Created sample users.json at {config_path}")
    return config_path


def authenticate_user(username, password):
    """
    Authenticate a user

    Args:
        username: Username
        password: Password

    Returns:
        User object if authentication successful, None otherwise
    """
    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, password):
        logger.info(f"User authenticated: {username}")
        return user

    logger.warning(f"Authentication failed for: {username}")
    return None
