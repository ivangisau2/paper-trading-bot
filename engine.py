"""Motor de riesgo + ejecución en paper trading (simulación, sin dinero real)."""
import json
import os
from datetime import datetime, timezone
from config import (
    INITIAL_BALANCE, FEES, RISK_BASE, AGGRESSION, MAX_POSITIONS,
    MAX_POSITION_PCT, STOP_ATR_MULT, TAKE_PROFIT_ATR,
    STATE_FILE, TRADES_FILE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PaperEngine:
    def __init__(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                self.state = json.load(f)
        else:
            self.state = {
                "balance": INITIAL_BALANCE,
                "initial_balance": INITIAL_BALANCE,
                "positions": {},
                "closed": 0,
                "realized_pnl": 0.0,
                "started": _now(),
            }

    def save(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    # ---- Motor de riesgo ----
    def position_size(self, price: float, atr: float) -> float:
        """Decide cuánto invertir: riesgo basado en ATR, escalado por agresividad."""
        equity = self.equity({})
        risk_per_unit = max(atr * STOP_ATR_MULT, price * 0.002)
        scale = AGGRESSION / 5.0
        risk_usd = equity * RISK_BASE * scale * 2  # 2 = ventana del stop
        qty = risk_usd / risk_per_unit if risk_per_unit else 0
        max_usd = equity * MAX_POSITION_PCT
        if qty * price > max_usd:
            qty = max_usd / price
        return round(qty, 8)

    def can_open(self) -> tuple[bool, str]:
        if len(self.state["positions"]) >= MAX_POSITIONS:
            return False, f"máximo {MAX_POSITIONS} posiciones"
        return True, "ok"

    # ---- Ejecución ----
    def open(self, symbol: str, side: str, price: float, atr: float, note: str = "") -> dict | None:
        ok, why = self.can_open()
        if not ok or symbol in self.state["positions"]:
            print(f"  [riesgo] No se abre {symbol}: {why}")
            return None
        qty = self.position_size(price, atr)
        notional = qty * price
        fee = notional * FEES
        if notional < 10:
            print(f"  [riesgo] {symbol}: tamaño demasiado pequeño (${notional:.2f})")
            return None
        sl_mult, tp_mult = STOP_ATR_MULT, TAKE_PROFIT_ATR
        pos = {
            "side": side,
            "qty": qty,
            "entry": price,
            "sl": price - atr * sl_mult if side == "long" else price + atr * sl_mult,
            "tp": price + atr * tp_mult if side == "long" else price - atr * tp_mult,
            "opened_at": _now(),
            "notional": notional,
            "fee": fee,
            "note": note,
        }
        self.state["balance"] -= fee
        self.state["positions"][symbol] = pos
        arrow = "▲ LONG" if side == "long" else "▼ SHORT"
        print(f"  [ejecución] {arrow} {symbol}: {qty} @ {price} | SL {pos['sl']:.6g} | TP {pos['tp']:.6g} | {note}")
        return pos

    def close(self, symbol: str, price: float, reason: str) -> float | None:
        pos = self.state["positions"].pop(symbol, None)
        if not pos:
            return None
        if pos["side"] == "long":
            pnl = (price - pos["entry"]) * pos["qty"]
        else:
            pnl = (pos["entry"] - price) * pos["qty"]
        fee = price * pos["qty"] * FEES
        net = pnl - fee - pos["fee"]
        self.state["balance"] += pnl - fee
        self.state["closed"] += 1
        self.state["realized_pnl"] += net
        trade = {
            "symbol": symbol,
            "side": pos["side"],
            "entry": pos["entry"],
            "exit": price,
            "qty": pos["qty"],
            "pnl": round(net, 4),
            "opened_at": pos["opened_at"],
            "closed_at": _now(),
            "reason": reason,
            "note": pos.get("note", ""),
        }
        with open(TRADES_FILE, "a") as f:
            f.write(json.dumps(trade, ensure_ascii=False) + "\n")
        emoji = "✅" if net >= 0 else "❌"
        print(f"  [ejecución] {emoji} CERRADO {symbol} @ {price}: {net:+.2f} USD ({reason})")
        return net

    def check_exits(self, prices: dict) -> list:
        """Revisa SL/TP de todas las posiciones abiertas."""
        closed = []
        for symbol in list(self.state["positions"]):
            price = prices.get(symbol, {}).get("price")
            if price is None:
                continue
            pos = self.state["positions"][symbol]
            hit_sl = price <= pos["sl"] if pos["side"] == "long" else price >= pos["sl"]
            hit_tp = price >= pos["tp"] if pos["side"] == "long" else price <= pos["tp"]
            if hit_sl:
                closed.append((symbol, self.close(symbol, price, "stop loss")))
            elif hit_tp:
                closed.append((symbol, self.close(symbol, price, "take profit")))
        return closed

    def close_all(self, prices: dict, reason: str = "modo solo cierre") -> list:
        closed = []
        for symbol in list(self.state["positions"]):
            price = prices.get(symbol, {}).get("price")
            if price is not None:
                closed.append((symbol, self.close(symbol, price, reason)))
        return closed

    def equity(self, prices: dict) -> float:
        eq = self.state["balance"]
        for symbol, pos in self.state["positions"].items():
            price = prices.get(symbol, {}).get("price")
            if price is None:
                price = pos["entry"]
            pnl = (price - pos["entry"]) * pos["qty"] if pos["side"] == "long" else (pos["entry"] - price) * pos["qty"]
            eq += pnl
        return eq
