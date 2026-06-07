@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   AI Simultaneous Interpretation - Build
echo ========================================
echo.

REM -- Use npmmirror for Electron download (China) --
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

REM -- Skip code signing (avoid symlink permission issue) --
set CSC_IDENTITY_AUTO_DISCOVERY=false

REM -- Fix working directory for admin mode --
cd /d "%~dp0"

REM -- Check Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

REM -- Check Node.js --
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

REM ===== Step 1: Build Python Backend =====
echo.
echo [1/3] Building Python backend with PyInstaller...
echo.

cd /d "%~dp0backend"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

pip install pyinstaller --quiet

if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

pyinstaller ai-translate-backend.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

echo [OK] Backend built: backend\dist\ai-translate-backend.exe

REM ===== Step 2: Build Frontend =====
echo.
echo [2/3] Building frontend with Electron...
echo.

cd /d "%~dp0frontend"

call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)

call npm run electron:build
if errorlevel 1 (
    echo [ERROR] electron-builder failed
    pause
    exit /b 1
)

echo [OK] Frontend built

REM ===== Done =====
echo.
echo ========================================
echo   Build complete!
echo ========================================
echo.
echo Output: frontend\release\
echo.
dir /b "%~dp0frontend\release\*.exe" 2>nul
dir /b "%~dp0frontend\release\*.dmg" 2>nul
echo.
pause
