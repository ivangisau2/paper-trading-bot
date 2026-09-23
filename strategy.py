"""Filtro y controles: puntuación de señal + filtros de calidad."""
from config import MIN_24H_VOLUME, MAX_ATR_PCT, MIN_ATR_PCT, MIN_SCORE


def score_signal(ind: dict) -> dict:
    """Puntúa la señal de -4 a +4 (positivo = long, negativo = short).

    Componentes: tendencia, momentum (RSI), MACD, posición en Bollinger, volumen.
    """
    parts = {}

    # Tendencia (±1): EMA50 vs EMA200
    parts["trend"] = 1 if ind["ema50"] > ind["ema200"] else -1

    # Momentum RSI (±1): sobrecompra → corto, sobreventa → largo
    if ind["rsi"] < 35:
        parts["rsi"] = 1
    elif ind["rsi"] > 65:
        parts["rsi"] = -1
    else:
        parts["rsi"] = 0

    # MACD histograma (±1)
    parts["macd"] = 1 if ind["macd_hist"] > 0 else -1

    # Bollinger: precio tocando banda (±1) — reversión a la media
    if ind["price"] <= ind["bb_lower"] * 1.002:
        parts["bb"] = 1
    elif ind["price"] >= ind["bb_upper"] * 0.998:
        parts["bb"] = -1
    else:
        parts["bb"] = 0

    # Volumen (0 o ±1): solo confirmación si hay volumen alto
    if ind["volume_ratio"] > 1.5:
        parts["volume"] = 1 if ind["macd_hist"] > 0 else -1
    else:
        parts["volume"] = 0

    total = sum(parts.values())
    side = "long" if total > 0 else "short" if total < 0 else "none"
    return {"score": total, "side": side, "parts": parts}


def passes_filters(ind: dict, ticker: dict, has_position: bool) -> tuple[bool, str]:
    """Filtro y controles: ¿tiene sentido operar este activo ahora?"""
    if has_position:
        return False, "posición abierta"
    if ticker["volume_usd"] < MIN_24H_VOLUME:
        return False, f"volumen 24h bajo ({ticker['volume_usd']/1e6:.0f}M < {MIN_24H_VOLUME/1e6:.0f}M)"
    if ind["atr_pct"] > MAX_ATR_PCT:
        return False, f"volatilidad extrema (ATR {ind['atr_pct']:.1f}%)"
    if ind["atr_pct"] < MIN_ATR_PCT:
        return False, f"mercado muerto (ATR {ind['atr_pct']:.2f}%)"
    if abs(ind["price"] / ind["ema200"] - 1) > 0.25:
        return False, "precio muy lejos de EMA200 (mercado extremo)"
    return True, "ok"


def is_tradeable(signal: dict) -> bool:
    return abs(signal["score"]) >= MIN_SCORE and signal["side"] != "none"
