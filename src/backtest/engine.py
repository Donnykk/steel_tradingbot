from typing import Optional, List, Dict
from src.core.types import Order, Fill, Bar, Position, Strategy, RiskManager

class SimpleMatcher:
    def match(self, order: Order, bar: Bar) -> Optional[Fill]:
        if order.type == "market":
            price = bar.close
        elif order.type == "limit":
            if order.side == "buy":
                if bar.low <= (order.price or bar.close):
                    price = min(order.price or bar.close, bar.close)
                else:
                    return None
            else:
                if bar.high >= (order.price or bar.close):
                    price = max(order.price or bar.close, bar.close)
                else:
                    return None
        else:
            return None
        qty = order.qty if order.side == "buy" else -order.qty
        return Fill(order_id="bt", ts=bar.ts, price=price, qty=qty, fee=0.0, maker=False)

class BacktestEngine:
    def __init__(self, strategy: Strategy, matcher: SimpleMatcher, risk: RiskManager, symbol: str):
        self.strategy = strategy
        self.matcher = matcher
        self.risk = risk
        self.position = Position(symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        self.account_state: Dict = {}
        self.equity_series: List[float] = []

    def run(self, bars: List[Bar]) -> List[float]:
        warm = bars[:200] if len(bars) > 200 else bars[:]
        self.strategy.warmup(warm)
        for bar in bars:
            ord = self.strategy.on_bar(bar)
            if ord and self.risk.approve(ord, self.position, self.account_state):
                fill = self.matcher.match(ord, bar)
                if fill:
                    self._apply_fill(fill)
                    self.strategy.on_fill(fill)
            eq = self.position.realized_pnl + self.position.qty * (bar.close - self.position.avg_price)
            self.equity_series.append(eq)
        return self.equity_series

    def _apply_fill(self, fill: Fill) -> None:
        q = self.position.qty
        p = self.position.avg_price
        fq = fill.qty
        fp = fill.price
        if q == 0.0:
            self.position.qty = fq
            self.position.avg_price = fp
        elif (q > 0 and fq > 0) or (q < 0 and fq < 0):
            new_qty = q + fq
            wq = abs(q)
            wfq = abs(fq)
            self.position.avg_price = (p * wq + fp * wfq) / (abs(new_qty))
            self.position.qty = new_qty
        else:
            close_qty = min(abs(q), abs(fq))
            sign = 1.0 if q > 0 else -1.0
            pnl = close_qty * (fp - p) * sign
            self.position.realized_pnl += pnl - abs(close_qty) * 0.0
            new_qty = q + fq
            if new_qty == 0.0:
                self.position.avg_price = 0.0
                self.position.qty = 0.0
            else:
                self.position.qty = new_qty
                if (q > 0 and new_qty < 0) or (q < 0 and new_qty > 0):
                    remaining = abs(new_qty)
                    self.position.avg_price = fp
                else:
                    self.position.avg_price = p

