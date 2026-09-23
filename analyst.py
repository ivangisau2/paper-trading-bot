"""Analista IA con múltiples proveedores (sin Claude de pago).

Seleccionable con la variable de entorno AI_PROVIDER:
  - "groq"    → API gratis de Groq (Llama 3.3 70B)  → necesita GROQ_API_KEY
  - "gemini"  → API gratis de Google Gemini Flash    → necesita GEMINI_API_KEY
  - "ollama"  → Ollama local (futuro Raspberry Pi)   → OLLAMA_URL opcional
  - "none"    → sin IA: el bot opera solo con la estrategia técnica

Si AI_PROVIDER no está definido, se deduce de las claves presentes.
Si la IA falla o se queda sin tokens, devuelve None y el bot SIGUE
funcionando solo con la estrategia (nunca se para por la IA).
"""
import json
import os
import re
import requests

from config import AI_URL as DEFAULT_OLLAMA_URL, AI_MODEL as DEFAULT_OLLAMA_MODEL, AI_TIMEOUT

PROMPT = """Eres un analista de trading cripto disciplinado. Evalúa SI la operación propuesta tiene sentido.
Responde SOLO con JSON: {{"verdict": "LONG"|"SHORT"|"FLAT", "confidence": 0-100, "reason": "máx 15 palabras"}}

Activo: {symbol}
Señal propuesta: {side} (puntuación {score}/4)
Precio: {price} | Cambio 24h: {change:.2f}%
RSI(14): {rsi:.1f} | ATR%: {atr_pct:.2f}% | Volumen vs media: {vr:.2f}x
MACD hist: {macd_hist:.6f} | Tendencia EMA50/200: {trend_str}
Bollinger: banda inferior {bb_lower:.6g}, media {bb_mid:.6g}, superior {bb_upper:.6g}
Volumen 24h: {volume_m:.0f}M USD
Reglas: solo aprueba si el contexto confirma la señal. Ante duda razonable, FLAT."""


def provider() -> str:
    p = os.environ.get("AI_PROVIDER", "").strip().lower()
    if p:
        return p
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OLLAMA_URL"):
        return "ollama"
    return "none"


def _extract_json(text: str) -> dict | None:
    """Parsea JSON aunque venga con ```json u otro ruido alrededor."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _ask_groq(prompt: str) -> dict | None:
    key = os.environ["GROQ_API_KEY"]
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Respondes SOLO con JSON válido, sin nada más."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )
    r.raise_for_status()
    return _extract_json(r.json()["choices"][0]["message"]["content"])


def _ask_gemini(prompt: str) -> dict | None:
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = requests.post(
        url,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    r.raise_for_status()
    return _extract_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def _ask_ollama(prompt: str) -> dict | None:
    r = requests.post(
        os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        json={
            "model": os.environ.get("AI_MODEL", DEFAULT_OLLAMA_MODEL),
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        },
        timeout=AI_TIMEOUT,
    )
    r.raise_for_status()
    return _extract_json(r.json()["response"])


_PROVIDERS = {"groq": _ask_groq, "gemini": _ask_gemini, "ollama": _ask_ollama}


def judge(symbol: str, ind: dict, signal: dict, ticker: dict) -> dict | None:
    prov = provider()
    if prov not in _PROVIDERS:
        print("  [analista] IA deshabilitada — decisión solo con estrategia técnica")
        return None

    prompt = PROMPT.format(
        symbol=symbol,
        side=signal["side"].upper(),
        score=signal["score"],
        price=ind["price"],
        change=ticker["change_pct"],
        rsi=ind["rsi"],
        atr_pct=ind["atr_pct"],
        vr=ind["volume_ratio"],
        macd_hist=ind["macd_hist"],
        trend_str="alcista" if ind["ema50"] > ind["ema200"] else "bajista",
        bb_lower=ind["bb_lower"],
        bb_mid=ind["bb_mid"],
        bb_upper=ind["bb_upper"],
        volume_m=ticker["volume_usd"] / 1e6,
    )
    try:
        data = _PROVIDERS[prov](prompt)
        if not isinstance(data, dict):
            raise ValueError("la IA no devolvió JSON válido")
        verdict = str(data.get("verdict", "FLAT")).upper()
        if verdict not in ("LONG", "SHORT", "FLAT"):
            verdict = "FLAT"
        return {
            "verdict": verdict,
            "confidence": int(data.get("confidence", 50)),
            "reason": str(data.get("reason", ""))[:120],
            "provider": prov,
        }
    except Exception as e:
        # Sin tokens / red caída / error → el bot sigue con la estrategia
        print(f"  [analista] IA ({prov}) no disponible: {e} — se omite veredicto")
        return None
