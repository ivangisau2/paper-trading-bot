#!/usr/bin/env bash
# Entrada del contenedor HF Space: restaura estado, arranca bucle + dashboard.
set -eo pipefail
cd /app

echo "[entrypoint] Restaurando estado (si hay HF_TOKEN + BOT_STATE_REPO)..."
python3 -c "import storage; storage.restore()" || echo "[entrypoint] Sin respaldo previo (normal en el primer despliegue)"

echo "[entrypoint] Arrancando bucle del bot (cada 15 min)..."
python3 bot.py loop 15 >> bot.log 2>&1 &

echo "[entrypoint] Dashboard en :7860"
HOST=0.0.0.0 exec python3 web.py 7860
