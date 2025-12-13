from typing import Optional, List
from src.core.types import Strategy, Bar, Order

class MomentumStrategy(Strategy):
    def __init__(self, symbol: str, fast: int = 10, slow: int = 30, size: float = 1.0):
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.size = size
        self.closes: List[float] = []

    def warmup(self, bars: List[Bar]) -> None:
        for b in bars:
            self.closes.append(b.close)

    def on_bar(self, bar: Bar) -> Optional[Order]:
        self.closes.append(bar.close)
        if len(self.closes) < self.slow + 1:
            return None
        f = sum(self.closes[-self.fast:]) / float(self.fast)
        s = sum(self.closes[-self.slow:]) / float(self.slow)
        if f > s:
            return Order(symbol=self.symbol, side="buy", type="market", qty=self.size)
        if f < s:
            return Order(symbol=self.symbol, side="sell", type="market", qty=self.size)
        return None

