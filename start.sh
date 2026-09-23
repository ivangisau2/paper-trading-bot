#!/usr/bin/env bash
# Arranca bot + dashboard. Úsalo tras reiniciar el ordenador.
#   ./start.sh
cd "$(dirname "$0")"

if pgrep -f "python3 web.py" > /dev/null; then
  echo "🌐 Dashboard ya corriendo"
else
  PYTHONUNBUFFERED=1 nohup python3 web.py 8787 >> web.log 2>&1 &
  echo "🌐 Dashboard: http://localhost:8787"
fi

if pgrep -f "python3 bot.py loop" > /dev/null; then
  echo "🤖 Bot ya corriendo"
else
  PYTHONUNBUFFERED=1 nohup python3 bot.py loop 15 >> bot.log 2>&1 &
  echo "🤖 Bot: ciclo cada 15 min"
fi

echo "Para parar: ./stop.sh"
