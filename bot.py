#!/usr/bin/env python3
"""Bot de paper trading con analista IA local (Ollama).

Pipeline (igual que el vídeo):
  datos → motor de datos → indicadores → filtro y controles →
  analista IA → motor de riesgo → ejecución (simulada) → posición

Uso:
  python3 bot.py cycle         # un ciclo completo
  python3 bot.py loop [min]    # bucle continuo (por defecto cada 15 min)
  python3 bot.py report        # estado y resultados
  python3 bot.py closeall      # cerrar todo (modo solo cierre)
  python3 bot.py reflect       # la IA revisa trades y escribe lecciones
"""
import json
import sys
import time
from datetime import datetime, timezone

import data
import indicators
import strategy
import analyst
import storage
from engine import PaperEngine
from config import (
    SYMBOLS, TIMEFRAME, CANDLES, AI_ENABLED, AI_MAX_CANDIDATES,
    LESSONS_FILE, STATE_FILE,
)

EQUITY_FILE = "equity.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def log_equity(engine: "PaperEngine", tickers: dict):
    """Guarda una foto del equity para la gráfica del dashboard web."""
    import os
    first = not os.path.exists(EQUITY_FILE)
    if first:
        init = {
            "ts": engine.state.get("started", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            "equity": engine.state.get("initial_balance", 0),
            "cash": engine.state.get("initial_balance", 0),
            "positions": 0,
        }
        with open(EQUITY_FILE, "a") as f:
            f.write(json.dumps(init) + "\n")
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "equity": round(engine.equity(tickers), 2),
        "cash": round(engine.state["balance"], 2),
        "positions": len(engine.state["positions"]),
    }
    with open(EQUITY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_cycle() -> dict:
    print(f"\n{'='*60}\n⏰ Ciclo — {now()}\n{'='*60}")
    engine = PaperEngine()
    tickers = data.fetch_24h_tickers(SYMBOLS)

    # 1. Vigilar posiciones abiertas (SL/TP)
    engine.check_exits(tickers)

    # 2. Analizar cada cripto sin posición
    candidates = []
    for symbol in SYMBOLS:
        try:
            k = data.fetch_klines(symbol, TIMEFRAME, CANDLES)
            ind = indicators.compute_all(k)
        except Exception as e:
            print(f"  [datos] Error con {symbol}: {e}")
            continue

        has_pos = symbol in engine.state["positions"]
        ok, why = strategy.passes_filters(ind, tickers[symbol], has_pos)
        sig = strategy.score_signal(ind)
        if not ok:
            continue
        if strategy.is_tradeable(sig):
            candidates.append((symbol, ind, sig, tickers[symbol]))

    candidates.sort(key=lambda c: abs(c[2]["score"]), reverse=True)
    print(f"\n📊 {len(candidates)} candidatos tras filtros")

    # 3. Analista IA (Ollama) sobre los mejores candidatos
    ai_calls = 0
    for symbol, ind, sig, ticker in candidates:
        if ai_calls >= AI_MAX_CANDIDATES:
            break
        verdict = None
        if AI_ENABLED:
            print(f"\n🤖 Analista IA evaluando {symbol} ({sig['side']} score {sig['score']})...")
            verdict = analyst.judge(symbol, ind, sig, ticker)
            ai_calls += 1
            if verdict:
                print(f"   → {verdict['verdict']} (confianza {verdict['confidence']}%): {verdict['reason']}")
                # La IA puede veto la operación o confirmarla
                if verdict["verdict"] == "FLAT":
                    continue
                if verdict["verdict"].lower() != sig["side"]:
                    print(f"   ✋ IA contradice la señal — se descarta")
                    continue
                if verdict["confidence"] < 55:
                    print(f"   ✋ Confianza baja — se descarta")
                    continue

        # 4. Motor de riesgo + ejecución
        note = f"score {sig['score']}" + (f" | IA: {verdict['reason']}" if verdict else "")
        engine.open(symbol, sig["side"], ind["price"], ind["atr"], note)

    engine.save()
    log_equity(engine, tickers)
    storage.backup()  # respaldo en HF (no-op en local sin HF_TOKEN)
    _print_status(engine, tickers)
    return engine.state


def _print_status(engine: PaperEngine, tickers: dict):
    st = engine.state
    eq = engine.equity(tickers)
    ret = (eq / st["initial_balance"] - 1) * 100
    print(f"\n💰 Equity: ${eq:.2f} | Cash: ${st['balance']:.2f} | Retorno: {ret:+.2f}%")
    print(f"📈 Posiciones abiertas: {len(st['positions'])} | Cerradas: {st['closed']} | PnL realizado: {st['realized_pnl']:+.2f}")
    for sym, p in st["positions"].items():
        price = tickers.get(sym, {}).get("price", p["entry"])
        pnl = (price - p["entry"]) * p["qty"] if p["side"] == "long" else (p["entry"] - price) * p["qty"]
        print(f"   {'▲' if p['side']=='long' else '▼'} {sym}: entry {p['entry']:.6g} → ahora {price:.6g} ({pnl:+.2f} USD)")


def cmd_report():
    engine = PaperEngine()
    tickers = data.fetch_24h_tickers(SYMBOLS)
    print(f"📋 REPORTE — {now()}")
    _print_status(engine, tickers)

    trades = []
    try:
        with open("trades.jsonl") as f:
            trades = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        pass
    if trades:
        wins = [t for t in trades if t["pnl"] > 0]
        print(f"\n📊 Historial: {len(trades)} trades | Win rate: {len(wins)/len(trades)*100:.0f}%")
        print(f"   Mejor: {max(t['pnl'] for t in trades):+.2f} | Peor: {min(t['pnl'] for t in trades):+.2f}")
        print("   Últimos 5:")
        for t in trades[-5:]:
            print(f"   {t['closed_at'][:16]} {t['symbol']} {t['side']} {t['pnl']:+.2f} USD ({t['reason']})")


def cmd_reflect():
    """Fase de aprendizaje: la IA revisa los trades y guarda lecciones."""
    import json as _json
    import analyst as _  # noqa
    import requests as _rq
    from config import AI_URL, AI_MODEL, AI_TIMEOUT
    try:
        with open("trades.jsonl") as f:
            trades = [_json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print("Sin trades todavía.")
        return
    recent = trades[-30:]
    prompt = (
        "Eres un revisor de trading. Analiza estos trades de un bot y escribe 3-5 lecciones "
        "concretas y accionables (en español, formato markdown, una viñeta cada una). "
        "Solo lecciones basadas en los datos:\n\n"
        + _json.dumps(recent, ensure_ascii=False, indent=1)
    )
    r = _rq.post(AI_URL, json={"model": AI_MODEL, "prompt": prompt, "stream": False},
                 timeout=AI_TIMEOUT)
    r.raise_for_status()
    lesson = r.json()["response"].strip()
    with open(LESSONS_FILE, "a") as f:
        f.write(f"\n## Reflexión {now()} ({len(recent)} trades)\n\n{lesson}\n")
    print(f"✅ Lección guardada en {LESSONS_FILE}:\n\n{lesson}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    storage.restore()  # baja el estado respaldado si el FS está vacío (Space efímero)
    if cmd == "cycle":
        run_cycle()
    elif cmd == "loop":
        minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 15
        print(f"🔁 Bucle cada {minutes} min. Ctrl+C para parar.")
        while True:
            try:
                run_cycle()
            except Exception as e:
                print(f"⚠️ Error en ciclo: {e}")
            time.sleep(minutes * 60)
    elif cmd == "report":
        cmd_report()
    elif cmd == "closeall":
        engine = PaperEngine()
        tickers = data.fetch_24h_tickers(SYMBOLS)
        engine.close_all(tickers)
        engine.save()
        log_equity(engine, tickers)
        _print_status(engine, tickers)
    elif cmd == "reflect":
        cmd_reflect()
    else:
        print(__doc__)
