from typing import List
import datetime as dt
from src.core.types import Bar

def load_dummy_bars(n: int = 500, start: dt.datetime = None) -> List[Bar]:
    import random
    start = start or dt.datetime.utcnow()
    bars: List[Bar] = []
    price = 100.0
    for i in range(n):
        ts = start + dt.timedelta(minutes=i)
        change = random.uniform(-1.0, 1.0)
        close = max(1.0, price + change)
        high = max(close, price + abs(change))
        low = min(close, price - abs(change))
        open_ = price
        volume = random.uniform(10.0, 100.0)
        bars.append(Bar(ts=ts, open=open_, high=high, low=low, close=close, volume=volume))
        price = close
    return bars

