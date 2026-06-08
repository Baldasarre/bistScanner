#!/bin/bash

# BIST Scanner Environment Setup Script
echo "🚀 Starting environment setup for BIST Scanner..."

# 1. Create virtual environment
python3 -m venv venv
echo "✅ Virtual environment 'venv' created."

# 2. Activate environment and install dependencies
source venv/bin/activate
echo "📦 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "------------------------------------------------"
echo "✨ Setup complete! To start developing, run:"
echo "   source venv/bin/activate"
echo "------------------------------------------------"