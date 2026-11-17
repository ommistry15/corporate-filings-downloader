#!/usr/bin/env bash
# Builds "Corporate Filings Downloader.app" for macOS and packages a zip.
#
#   ./build_release_mac.sh                 # version 1.1.0
#   ./build_release_mac.sh 1.2.0           # custom version label
#   ./build_release_mac.sh 1.1.0 --install # also copy the app into /Applications
#
# Needs Python 3.10+ with Tk (python.org installer, Homebrew python-tk, or
# `uv`). The .app is built for the CPU of the Mac you build on (Apple Silicon
# -> arm64, Intel -> x86_64).
set -euo pipefail

VERSION="${1:-1.1.0}"
INSTALL="${2:-}"
APP="Corporate Filings Downloader.app"
cd "$(dirname "$0")"

pick_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

if [ ! -x .venv/bin/python ]; then
  echo "Creating .venv ..."
  if PY="$(pick_python)"; then
    "$PY" -m venv .venv
  elif command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv
  else
    echo "Need Python 3.10+ with Tkinter. Install it from https://www.python.org/downloads/macos/" >&2
    exit 1
  fi
fi
PY=.venv/bin/python
"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true

echo "Installing build requirements ..."
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements-build.txt

echo "Running PyInstaller ..."
"$PY" -m PyInstaller --noconfirm --clean --log-level WARN CorporateFilingsDownloader-mac.spec

[ -d "dist/$APP" ] || { echo "dist/$APP was not produced" >&2; exit 1; }

ARCH="$(uname -m)"; [ "$ARCH" = "x86_64" ] || ARCH="arm64"
NAME="CorporateFilingsDownloader-v$VERSION"
STAGE="release/$NAME-macos"
ZIP="release/$NAME-macos-$ARCH.zip"
rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"
cp -R "dist/$APP" "$STAGE/"
cp HOW_TO_INSTALL_ON_MAC.txt LICENSE "$STAGE/"
# ditto keeps the bundle's symlinks, permissions and code signature intact.
ditto -c -k --keepParent "$STAGE" "$ZIP"
( cd release && shasum -a 256 "$(basename "$ZIP")" > "SHA256SUMS-macos-$ARCH.txt" )

if [ "$INSTALL" = "--install" ]; then
  echo "Installing to /Applications ..."
  rm -rf "/Applications/$APP"
  ditto "dist/$APP" "/Applications/$APP"
fi

echo
echo "Done."
echo "  app : dist/$APP"
echo "  zip : $ZIP"
cat "release/SHA256SUMS-macos-$ARCH.txt"
