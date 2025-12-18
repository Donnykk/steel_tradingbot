import asyncio
import datetime as dt
import json
from typing import List, Optional
from src.core.types import Bar

def to_ccxt_symbol(symbol: str) -> str:
    if "/" in symbol:
        return symbol
    for q in ("USDT", "BUSD", "USDC"):
        if symbol.endswith(q):
            return f"{symbol[:-len(q)]}/{q}"
    return symbol

class ExchangeDataClient:
    def __init__(self, exchange_id: str = "binance", sandbox: bool = False):
        import ccxt
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"unsupported exchange: {exchange_id}")
        self.exchange_id = exchange_id
        self.client = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        if sandbox and hasattr(self.client, "setSandboxMode"):
            self.client.setSandboxMode(True)

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500, since: Optional[int] = None) -> List[Bar]:
        s = to_ccxt_symbol(symbol)
        ohlcv = self.client.fetch_ohlcv(s, timeframe=timeframe, limit=limit, since=since)
        bars: List[Bar] = []
        for t, o, h, l, c, v in ohlcv:
            ts = dt.datetime.fromtimestamp(t / 1000.0, tz=dt.timezone.utc)
            bars.append(Bar(ts=ts, open=float(o), high=float(h), low=float(l), close=float(c), volume=float(v)))
        return bars

    async def stream_klines(self, symbol: str, interval: str = "1m"):
        if self.exchange_id != "binance":
            raise NotImplementedError(f"Streaming not implemented for {self.exchange_id}")

        import websockets
        # Binance stream expects lowercase symbol without slash (e.g. btcusdt)
        sym = symbol.lower().replace("/", "")
        url = f"wss://stream.binance.com:9443/ws/{sym}@kline_{interval}"
        async with websockets.connect(url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                k = data.get("k")
                if not k:
                    continue
                if k.get("x"):
                    ts = dt.datetime.fromtimestamp(k.get("T") / 1000.0, tz=dt.timezone.utc)
                    yield Bar(
                        ts=ts,
                        open=float(k.get("o")),
                        high=float(k.get("h")),
                        low=float(k.get("l")),
                        close=float(k.get("c")),
                        volume=float(k.get("v")),
                    )

