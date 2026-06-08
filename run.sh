#!/bin/bash
echo "========================================"
echo "BIST Akumulasyon Tarayici (macOS)"
echo "========================================"
echo "Uygulama baslatiliyor: http://localhost:5001"
echo ""
source venv/bin/activate
# FLASK_RUN_PORT degiskeni bazi konfigurasyonlarda otomatik algilanir
export FLASK_RUN_PORT=5001
python app.py 5001