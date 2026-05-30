#!/usr/bin/env bash
set -e

BINARY="dist/deepcode"
INSTALL_DIR="$HOME/.local/bin"

echo "Installing DeepCode to: $INSTALL_DIR"

if [ ! -f "$BINARY" ]; then
  echo "[!] $BINARY not found. Run ./build.sh first."
  exit 1
fi

mkdir -p "$INSTALL_DIR"

cp "$BINARY" "$INSTALL_DIR/deepcode"
chmod +x "$INSTALL_DIR/deepcode"

echo
echo "✓ Installed. Make sure $HOME/.local/bin is in your PATH."
echo "   Then you can run: deepcode"