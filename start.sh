#!/usr/bin/env bash
# Arranca SOLO el dashboard local. El bot corre en GitHub Actions (cada 15 min).
# No arranques el bucle local: el estado vive en los commits del repo.
#   ./start.sh          → dashboard local
#   git pull            → sincronizar estado con la nube
cd "$(dirname "$0")"

git pull -q origin main 2>/dev/null || true

if pgrep -f "python3 web.py" > /dev/null; then
  echo "🌐 Dashboard ya corriendo"
else
  PYTHONUNBUFFERED=1 nohup python3 web.py 8787 >> web.log 2>&1 &
  echo "🌐 Dashboard: http://localhost:8787"
fi

echo "🤖 El bot lo ejecuta GitHub Actions (cron cada 15 min)."
echo "   Ver ciclos: https://github.com/ivangisau2/paper-trading-bot/actions"
echo "   Ver estado local: git pull (tras cada ciclo remoto)"
echo "Para parar: ./stop.sh"
