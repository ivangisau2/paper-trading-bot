"""Motor de datos: descarga de precios, velas y volumen desde Binance (API pública, sin key)."""
import time
import requests
import numpy as np

BASE = "https://api.binance.com"
_session = requests.Session()
_session.headers.update({"User-Agent": "paper-bot/1.0"})


def _get(path: str, params: dict, retries: int = 3) -> dict | list:
    for i in range(retries):
        try:
            r = _session.get(BASE + path, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1 + i)


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 200) -> dict:
    """Descarga velas y devuelve arrays numpy: open, high, low, close, volume."""
    raw = _get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    arr = np.array(raw, dtype=object)
    return {
        "open": np.array([float(x) for x in arr[:, 1]]),
        "high": np.array([float(x) for x in arr[:, 2]]),
        "low": np.array([float(x) for x in arr[:, 3]]),
        "close": np.array([float(x) for x in arr[:, 4]]),
        "volume": np.array([float(x) for x in arr[:, 5]]),
        "close_time": np.array([int(x) for x in arr[:, 6]]),
    }


def fetch_24h_tickers(symbols: list[str]) -> dict:
    """Precios actuales + volumen 24h de los símbolos indicados."""
    raw = _get("/api/v3/ticker/24hr", {})
    wanted = set(symbols)
    raw = [t for t in raw if t["symbol"] in wanted]
    return {
        t["symbol"]: {
            "price": float(t["lastPrice"]),
            "volume_usd": float(t["quoteVolume"]),
            "change_pct": float(t["priceChangePercent"]),
            "high": float(t["highPrice"]),
            "low": float(t["lowPrice"]),
        }
        for t in raw
    }
