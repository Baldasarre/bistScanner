#!/bin/bash
echo "========================================"
echo "BIST Tarayici Manuel Test Baslatiliyor"
echo "========================================"
source venv/bin/activate
python test_scan.py
echo "Islem tamamlandi."