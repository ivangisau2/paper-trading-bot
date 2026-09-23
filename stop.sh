#!/usr/bin/env bash
# Para bot y dashboard.
cd "$(dirname "$0")"
pkill -f "python3 bot.py loop"
pkill -f "python3 web.py"
echo "🛑 Bot y dashboard detenidos. Estado guardado (state.json)."
