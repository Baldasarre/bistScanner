"""
Main application entry point
Run this file to start the BIST Scanner web application
"""

from app_config import create_app, setup_logging

# Setup logging
setup_logging()

# Create Flask app
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)
