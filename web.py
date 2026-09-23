#!/usr/bin/env python3
"""Dashboard web local del bot de paper trading.

Uso:  python3 web.py [puerto]     (por defecto 8787)
Abre: http://localhost:8787
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import SYMBOLS

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8787))
HOST = os.environ.get("HOST", "127.0.0.1")  # 0.0.0.0 en el despliegue HF


def _read_json(name, default):
    try:
        with open(os.path.join(ROOT, name)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _read_jsonl(name):
    out = []
    try:
        with open(os.path.join(ROOT, name)) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return out


def api_state():
    st = _read_json("state.json", {})
    tickers = {}
    try:
        import data
        tickers = data.fetch_24h_tickers(SYMBOLS)
    except Exception as e:
        print(f"[web] no se pudieron obtener precios: {e}")
    if not st:
        return {"error": "sin estado todavía — ejecuta bot.py cycle"}

    # posición abierta con PnL en vivo
    positions = []
    for sym, p in st.get("positions", {}).items():
        price = tickers.get(sym, {}).get("price", p["entry"])
        if p["side"] == "long":
            pnl = (price - p["entry"]) * p["qty"]
        else:
            pnl = (p["entry"] - price) * p["qty"]
        positions.append({
            "symbol": sym, "side": p["side"], "qty": p["qty"],
            "entry": p["entry"], "price": price, "pnl": round(pnl, 2),
            "sl": p["sl"], "tp": p["tp"], "opened_at": p["opened_at"],
            "note": p.get("note", ""),
        })

    # equity (con precio vivo de posiciones abiertas)
    eq = st.get("balance", 0)
    for pos in positions:
        eq += pos["pnl"]

    trades = _read_jsonl("trades.jsonl")
    wins = [t for t in trades if t["pnl"] > 0]
    equity_hist = _read_jsonl("equity.jsonl")

    # log reciente
    log_tail = []
    try:
        with open(os.path.join(ROOT, "bot.log"), errors="replace") as f:
            log_tail = f.read().splitlines()[-60:]
    except FileNotFoundError:
        pass

    # lecciones aprendidas
    lessons = ""
    try:
        with open(os.path.join(ROOT, "APRENDIDO.md"), errors="replace") as f:
            lessons = f.read()
    except FileNotFoundError:
        pass

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "PAPER TRADING (simulado)",
        "cycle_minutes": 15,
        "last_cycle": equity_hist[-1]["ts"] if equity_hist else None,
        "symbols": SYMBOLS,
        "started": st.get("started"),
        "equity": round(eq, 2),
        "cash": round(st.get("balance", 0), 2),
        "initial_balance": st.get("initial_balance", 1000),
        "return_pct": round((eq / st.get("initial_balance", 1000) - 1) * 100, 2),
        "realized_pnl": round(st.get("realized_pnl", 0), 2),
        "closed_count": st.get("closed", 0),
        "open_count": len(positions),
        "positions": positions,
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "trades_total": len(trades),
        "best": max((t["pnl"] for t in trades), default=0),
        "worst": min((t["pnl"] for t in trades), default=0),
        "trades": trades[-50:],
        "equity_history": equity_hist[-500:],
        "log": log_tail,
        "lessons": lessons,
        "prices": {s: tickers.get(s, {}) for s in SYMBOLS},
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = open(os.path.join(ROOT, "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")  # siempre la última versión
        elif self.path.startswith("/api/klines"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            symbol = q.get("symbol", ["BTCUSDT"])[0]
            limit = min(int(q.get("limit", ["168"])[0]), 300)
            if symbol not in SYMBOLS:
                self.send_error(400, "símbolo no soportado")
                return
            try:
                import data
                k = data.fetch_klines(symbol, "1h", limit)
                payload = {
                    "symbol": symbol,
                    "times": [int(t / 1000) for t in k["close_time"]],
                    "close": [round(float(c), 8) for c in k["close"]],
                    "high": [round(float(h), 8) for h in k["high"]],
                    "low": [round(float(l), 8) for l in k["low"]],
                }
            except Exception as e:
                self.send_error(502, f"error de datos: {e}")
                return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        elif self.path == "/api/state":
            body = json.dumps(api_state(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        else:
            self.send_error(404)
            return
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # sin ruido en consola


if __name__ == "__main__":
    print(f"🌐 Dashboard: http://{HOST}:{PORT}  (Ctrl+C para parar)")
    HTTPServer((HOST, PORT), Handler).serve_forever()
