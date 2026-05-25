@echo off
echo Building DeepCode v2...
pip install pyinstaller httpx rich prompt_toolkit -q
pyinstaller deepcode.spec --clean
echo.
echo Done! Executable at: dist\deepcode.exe
pause
