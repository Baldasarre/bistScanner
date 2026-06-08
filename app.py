"""
Main application entry point
Run this file to start the BIST Scanner web application
"""

import sys
import os
from app_config import create_app, setup_logging

# Setup logging
setup_logging()

# Create Flask app
app = create_app()

if __name__ == '__main__':
    # Get port from argument or environment
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 5000))
    
    # Development server
    app.run(host='0.0.0.0', port=port, debug=True)
