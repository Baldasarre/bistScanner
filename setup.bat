@echo off
echo ========================================
echo BIST Akumulasyon Tarayici - Kurulum
echo ========================================
echo.

:: Virtual environment olustur
echo [1/4] Virtual environment olusturuluyor...
python -m venv venv
if errorlevel 1 (
    echo HATA: Virtual environment olusturulamadi!
    pause
    exit /b 1
)
echo Virtual environment olusturuldu.
echo.

:: Virtual environment aktif et
echo [2/4] Virtual environment aktif ediliyor...
call venv\Scripts\activate.bat
echo.

:: Bagimliliklari yukle
echo [3/4] Bagimliliklari yukleniyor...
pip install -r requirements.txt
if errorlevel 1 (
    echo HATA: Bagimliliklar yuklenemedi!
    pause
    exit /b 1
)
echo Bagimliliklar yuklendi.
echo.

:: .env dosyasi olustur
echo [4/4] Konfigurasyonlar hazirlaniyor...
if not exist .env (
    copy .env.example .env
    echo .env dosyasi olusturuldu.
) else (
    echo .env dosyasi zaten mevcut.
)
echo.

echo ========================================
echo Kurulum tamamlandi!
echo ========================================
echo.
echo Uygulamayi baslatmak icin:
echo   1. venv\Scripts\activate
echo   2. python app.py
echo.
echo Veya direkt: run.bat
echo.
pause
