@echo off
setlocal EnableDelayedExpansion

echo.
echo  ██████╗ ███████╗███████╗██████╗      ██████╗ ██████╗ ██████╗ ███████╗
echo  ██╔══██╗██╔════╝██╔════╝██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝
echo  ██║  ██║█████╗  █████╗  ██████╔╝    ██║     ██║   ██║██║  ██║█████╗
echo  ██║  ██║██╔══╝  ██╔══╝  ██╔═══╝     ██║     ██║   ██║██║  ██║██╔══╝
echo  ██████╔╝███████╗███████╗██║         ╚██████╗╚██████╔╝██████╔╝███████╗
echo  ╚═════╝ ╚══════╝╚══════╝╚═╝          ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
echo.
echo  DeepCode v2 Installer
echo  ─────────────────────────────────────────
echo.

:: Check for admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Run this as Administrator for automatic PATH setup.
    echo      Or manually copy deepcode.exe to a folder in your PATH.
    echo.
    pause
    exit /b 1
)

:: Install dir
set "INSTALL_DIR=C:\Program Files\DeepCode"
echo  Installing to: %INSTALL_DIR%
mkdir "%INSTALL_DIR%" 2>nul
copy /y "deepcode.exe" "%INSTALL_DIR%\deepcode.exe" >nul

:: Add to system PATH if not already there
echo %PATH% | findstr /i /c:"%INSTALL_DIR%" >nul
if %errorlevel% neq 0 (
    for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSPATH=%%b"
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path /t REG_EXPAND_SZ /d "!SYSPATH!;%INSTALL_DIR%" /f >nul
    echo  PATH updated. Restart your terminal after install.
) else (
    echo  Already in PATH.
)

echo.
echo  ✓ DeepCode installed successfully!
echo  ✓ Open a NEW terminal and type: deepcode
echo.
pause
