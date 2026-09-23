"""Motor de datos: descarga de precios, velas y volumen desde Binance (API pública, sin key)."""
import os
import time
import requests
import numpy as np

BASE = "https://api.binance.com"
KRAKEN = "https://api.kraken.com"
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
    if _exchange() == "kraken":
        return _kraken_klines(symbol, interval, limit)
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
    if _exchange() == "kraken":
        return _kraken_tickers(symbols)
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


# ---------------------------------------------------------------------------
# Backend Kraken (principal: legal en EE.UU., sin key — los runners de GitHub
# Actions están en EE.UU. y Binance les devuelve HTTP 451)
# ---------------------------------------------------------------------------

_INTERVAL_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
_pair_cache: dict | None = None


def _exchange() -> str:
    return os.environ.get("EXCHANGE", "kraken")


def _kraken_get(path: str, params: dict, retries: int = 4) -> dict:
    """GET a Kraken con manejo de rate limit (ECallLimit) y reintentos."""
    last_err = None
    for i in range(retries):
        try:
            r = _session.get(KRAKEN + path, params=params, timeout=15)
            r.raise_for_status()
            body = r.json()
            errors = body.get("error") or []
            if errors:
                code = str(errors[0])
                if "ECallLimit" in code or "ERate" in code:
                    time.sleep(20)  # ventana de rate limit: esperamos y reintentamos
                    last_err = code
                    continue
                raise RuntimeError(f"Kraken {path}: {errors}")
            return body.get("result", {})
        except Exception as e:
            last_err = e
            if i == retries - 1:
                raise
            time.sleep(2 + i)
    raise RuntimeError(f"Kraken {path}: agotados reintentos ({last_err})")


def _resolve_pairs() -> dict:
    """symbol (BTCUSDT) → {"alias": "XBTUSD", "canonical": "XXBTZUSD"}.

    Kraken usa sinónimos históricos (BTC→XBT, DOGE→XDG...). Se resuelve con
    una cadena: coin → alias histórico → código canónico de /0/public/Assets
    → par USD de /0/public/AssetPairs. Cacheado por proceso.
    """
    global _pair_cache
    if _pair_cache is not None:
        return _pair_cache

    # Sinónimos históricos en Kraken (por si el Assets no trae el alias "BTC")
    coin_alias = {"BTC": "XBT", "DOGE": "XDG"}

    from config import SYMBOLS
    assets = _kraken_get("/0/public/Assets", {})
    alt_to_code = {rec.get("altname"): code for code, rec in assets.items() if rec.get("altname")}

    pairs = _kraken_get("/0/public/AssetPairs", {})
    want: dict = {}  # código base → pares spot en USD online
    for code, rec in pairs.items():
        if not str(rec.get("wsname", "")).endswith("/USD"):
            continue
        if rec.get("status") != "online" or code.endswith((".d", ".w")):
            continue
        want.setdefault(rec.get("base"), []).append((code, rec))

    _pair_cache = {}
    for sym in SYMBOLS:
        coin = sym.removesuffix("USDT")
        lookups = [coin]
        if coin in coin_alias:
            lookups.append(coin_alias[coin])
        for lk in list(lookups):
            if lk in alt_to_code:
                lookups.append(alt_to_code[lk])
        cands = []
        for lk in lookups:
            if lk in want:
                cands = want[lk]
                break
        if not cands:
            raise RuntimeError(f"Kraken: no existe par USD para {coin} (probado: {lookups})")
        code, rec = cands[0]
        _pair_cache[sym] = {"alias": rec.get("altname") or code, "canonical": code}
    return _pair_cache


def _kraken_klines(symbol: str, interval: str, limit: int) -> dict:
    alias = _resolve_pairs()[symbol]["alias"]
    res = _kraken_get("/0/public/OHLC", {"pair": alias, "interval": _INTERVAL_MIN.get(interval, 60)})
    rows = [v for k, v in res.items() if k != "last"][0][-limit:]
    to_f = lambda i: np.array([float(r[i]) for r in rows])
    return {"open": to_f(1), "high": to_f(2), "low": to_f(3), "close": to_f(4),
            "volume": to_f(6), "close_time": np.array([int(float(r[0])) * 1000 for r in rows])}


def _kraken_tickers(symbols: list[str]) -> dict:
    pmap = _resolve_pairs()
    out = {}
    for sym in symbols:
        info = pmap.get(sym)
        if not info:
            continue
        try:
            res = _kraken_get("/0/public/Ticker", {"pair": info["alias"]})
        except Exception as e:
            print(f"  [datos] ticker Kraken {sym}: {e}")
            continue
        if not res:
            continue
        t = list(res.values())[0]
        last = float(t["c"][0])
        open_today = float(t["o"])  # apertura de hoy 00:00 UTC
        vol24 = float(t["v"][1])  # volumen 24h en unidades base
        out[sym] = {
            "price": last,
            "volume_usd": vol24 * last,
            "change_pct": (last / open_today - 1) * 100 if open_today else 0.0,
            "high": float(t["h"][1]),
            "low": float(t["l"][1]),
        }
        time.sleep(0.25)  # respeto del rate limit público de Kraken
    return out
