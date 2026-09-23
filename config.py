# Configuración del bot de paper trading

# 16 criptomonedas (igual que el vídeo)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
    "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT",
    "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
]

TIMEFRAME = "1h"          # temporalidad de las velas
CANDLES = 200             # velas a descargar para indicadores

# Cuenta simulada (paper trading, SIN dinero real)
INITIAL_BALANCE = 1000.0  # dólares simulados
FEES = 0.001              # 0.1% comisión taker por operación (ida y vuelta)

# Motor de riesgo
AGGRESSION = 5            # 1-10, como en el vídeo. Más agresivo = más riesgo/rentabilidad
RISK_BASE = 0.005         # riesgo base por operación (0.5% del equity a agresión 5)
MAX_POSITIONS = 5         # posiciones abiertas simultáneas
MAX_POSITION_PCT = 0.15   # máximo 15% del equity en una sola posición
MIN_SCORE = 1             # puntuación mínima del estratega para operar (de -4 a 4)

# Filtros
MIN_24H_VOLUME = 20_000_000   # volumen mínimo 24h en USD
MAX_ATR_PCT = 6.0             # no entrar si ATR% > 6% (mercado demsiado loco)
MIN_ATR_PCT = 0.15            # no entrar si ATR% < 0.15% (mercado muerto)

# Analista IA (Ollama local, gratis — sin Claude)
AI_ENABLED = True
AI_URL = "http://localhost:11434/api/generate"
AI_MODEL = "qwen3:8b"
AI_MAX_CANDIDATES = 4     # máximo llamadas a la IA por ciclo
AI_TIMEOUT = 120          # segundos

# Salidas
STOP_ATR_MULT = 1.5       # stop loss = 1.5 * ATR
TAKE_PROFIT_ATR = 3.0     # take profit = 3.0 * ATR (ratio R:R 1:2)

# Persistencia
STATE_FILE = "state.json"
TRADES_FILE = "trades.jsonl"
LESSONS_FILE = "APRENDIDO.md"
