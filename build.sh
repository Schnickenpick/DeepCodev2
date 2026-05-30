#!/usr/bin/env bash
set -e

echo "Building DeepCode v2..."

# 1. venv anlegen/aktivieren
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate

# 2. Requirements + PyInstaller installieren
pip install --upgrade pip
pip install pyinstaller httpx rich prompt_toolkit

# 3. Mit Spec für beide Plattformen bauen
pyinstaller deepcode.spec --clean

echo
echo "Done! Executable at: dist/deepcode"

deactivate