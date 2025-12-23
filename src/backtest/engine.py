from typing import Optional, List, Dict
from src.core.types import Order, Fill, Bar, Position, Strategy, RiskManager

class SimpleMatcher:
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def match(self, order: Order, bar: Bar) -> Optional[Fill]:
        if order.type == "market":
            price = bar.close
            is_maker = False 
        elif order.type == "limit":
            if order.side == "buy":
                if bar.low <= (order.price or bar.close):
                    price = min(order.price or bar.close, bar.close)
                    is_maker = True
                else:
                    return None
            else:
                if bar.high >= (order.price or bar.close):
                    price = max(order.price or bar.close, bar.close)
                    is_maker = True
                else:
                    return None
        else:
            return None
        
        qty = order.qty if order.side == "buy" else -order.qty
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        fee = price * abs(qty) * fee_rate
        
        return Fill(order_id="bt", ts=bar.ts, price=price, qty=qty, fee=fee, maker=is_maker)

class BacktestEngine:
    def __init__(self, strategy: Strategy, matcher: SimpleMatcher, risk: RiskManager, symbol: str):
        self.strategy = strategy
        self.matcher = matcher
        self.risk = risk
        self.position = Position(symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
        self.account_state: Dict = {}
        self.equity_series: List[float] = []
        self.fills: List[Fill] = []
        self.trade_pnls: List[float] = []

    def run(self, bars: List[Bar]) -> List[float]:
        warm = bars[:200] if len(bars) > 200 else bars[:]
        self.strategy.warmup(warm)
        for bar in bars:
            ord = self.strategy.on_bar(bar)
            if ord and self.risk.approve(ord, self.position, self.account_state):
                fill = self.matcher.match(ord, bar)
                if fill:
                    prev = self.position.realized_pnl
                    self._apply_fill(fill)
                    delta = self.position.realized_pnl - prev
                    if delta != 0.0:
                        self.trade_pnls.append(delta)
                    self.fills.append(fill)
                    self.strategy.on_fill(fill)
            eq = self.position.realized_pnl + self.position.qty * (bar.close - self.position.avg_price)
            self.equity_series.append(eq)
        return self.equity_series

    def _apply_fill(self, fill: Fill) -> None:
        self.position.realized_pnl -= fill.fee
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
            self.position.realized_pnl += pnl
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

    def analyze(self) -> Dict:
        if not self.equity_series:
            return {
                "equity": [],
                "final_equity": 0.0,
                "max_drawdown": 0.0,
                "mean_return": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "trades": 0
            }
        eq = self.equity_series
        final_equity = eq[-1]
        peak = eq[0]
        max_dd = 0.0
        for v in eq:
            if v > peak:
                peak = v
            dd = peak - v if v < peak else 0.0
            if dd > max_dd:
                max_dd = dd
        returns = []
        for i in range(1, len(eq)):
            returns.append(eq[i] - eq[i - 1])
        mean_ret = sum(returns) / len(returns) if returns else 0.0
        if returns:
            m = mean_ret
            var = sum((r - m) ** 2 for r in returns) / len(returns)
            vol = var ** 0.5
        else:
            vol = 0.0
        sharpe = (mean_ret / vol) if vol != 0.0 else 0.0
        wins = [x for x in self.trade_pnls if x > 0]
        losses = [x for x in self.trade_pnls if x < 0]
        trades = len(self.trade_pnls)
        win_rate = (len(wins) / trades) if trades > 0 else 0.0
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0
        return {
            "equity": eq,
            "final_equity": final_equity,
            "max_drawdown": max_dd,
            "mean_return": mean_ret,
            "volatility": vol,
            "sharpe": sharpe,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "trades": trades
        }
