"""Indicadores técnicos (numpy puro, sin pandas)."""
import numpy as np


def ema(close: np.ndarray, period: int) -> np.ndarray:
    if len(close) < period:
        return np.full_like(close, np.nan)
    out = np.full(len(close), np.nan)
    k = 2 / (period + 1)
    out[period - 1] = close[:period].mean()
    for i in range(period, len(close)):
        out[i] = close[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(close: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def macd(close: np.ndarray) -> tuple[float, float, float]:
    """Devuelve (macd_line, signal_line, histogram)."""
    ema12 = ema(close, 12)
    ema26 = ema(close, 26)
    line = ema12 - ema26
    signal = ema(line[~np.isnan(line)], 9) if np.any(~np.isnan(line)) else np.array([np.nan])
    valid = ~np.isnan(line)
    hist = line[valid] - signal
    return float(line[-1]), float(signal[-1]), float(hist[-1])


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return float("nan")
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])),
    )
    val = tr[:period].mean()
    for i in range(period, len(tr)):
        val = (val * (period - 1) + tr[i]) / period
    return float(val)


def bollinger(close: np.ndarray, period: int = 20, mult: float = 2.0):
    window = close[-period:]
    mid = window.mean()
    std = window.std()
    return float(mid - mult * std), float(mid), float(mid + mult * std)


def compute_all(k: dict) -> dict:
    """Calcula el paquete completo de indicadores para una vela actual."""
    close = k["close"]
    price = float(close[-1])
    atr_val = atr(k["high"], k["low"], close)
    macd_line, macd_sig, macd_hist = macd(close)
    bb_lower, bb_mid, bb_upper = bollinger(close)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    vol_sma20 = float(k["volume"][-20:].mean())
    return {
        "price": price,
        "rsi": rsi(close),
        "macd": macd_line,
        "macd_signal": macd_sig,
        "macd_hist": macd_hist,
        "atr": atr_val,
        "atr_pct": (atr_val / price * 100) if price else 0.0,
        "bb_lower": bb_lower,
        "bb_mid": bb_mid,
        "bb_upper": bb_upper,
        "ema50": float(ema50[-1]) if not np.isnan(ema50[-1]) else price,
        "ema200": float(ema200[-1]) if not np.isnan(ema200[-1]) else price,
        "volume_ratio": float(k["volume"][-1] / vol_sma20) if vol_sma20 else 1.0,
        "change_24closes_pct": (price / float(close[-25]) - 1) * 100 if len(close) > 25 else 0.0,
    }
