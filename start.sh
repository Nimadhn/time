#!/bin/bash
# Launcher for ubi-bot — exists because systemd ExecStart cannot handle
# spaces in paths. Adjust paths below to match your deployment directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/bot.py"
