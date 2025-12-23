import asyncio
import os
import datetime as dt
import json
from typing import List, Optional
from src.core.types import Bar
from okx.api.market_data import MarketData

def to_ccxt_symbol(symbol: str) -> str:
    if "/" in symbol:
        return symbol
    for q in ("USDT", "BUSD", "USDC"):
        if symbol.endswith(q):
            return f"{symbol[:-len(q)]}/{q}"
    return symbol

class ExchangeDataClient:
    def __init__(self, sandbox: bool = False):
        self.okx_market_api = None
        self.client = None
        
        # Proxy settings
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        print(f"DEBUG: Proxy config: {proxy}")

        try:
            flag = "1" if sandbox else "0"
            self.okx_market_api = MarketData.MarketAPI(flag=flag, proxy=proxy, debug=False)
            print("DEBUG: Initialized OKX official SDK")
            return
        except ImportError:
            print("WARNING: 'okx' library not found. ")
        except Exception as e:
                print(f"WARNING: OKX SDK init failed ({e}). Falling back to ccxt.")


    def fetch_ohlcv(self, symbol: str, timeframe: str = "1s", limit: int = 1000, since: Optional[int] = None) -> List[Bar]:
        # OKX SDK Implementation
        if self.okx_market_api:
            inst_id = symbol.replace("/", "-") # BTC/USDT -> BTC-USDT
            # Map timeframe to OKX format (1m, 1H, 1D, 1W)
            bar = timeframe
            if bar.endswith('h'): bar = bar.upper()
            if bar.endswith('d'): bar = bar.upper()
            if bar.endswith('w'): bar = bar.upper()
            
            try:
                # OKX API: get_candlesticks
                # limit max is usually 100 or 300 depending on endpoint, SDK handles request
                result = self.okx_market_api.get_candlesticks(instId=inst_id, bar=bar, limit=str(limit))
                
                if result.get('code') != '0':
                    print(f"OKX API Error: {result}")
                    return []
                
                bars = []
                # OKX returns newest first. We want chronological order (oldest first).
                data = result.get('data', [])
                for k in reversed(data):
                    ts = dt.datetime.fromtimestamp(int(k[0]) / 1000.0, tz=dt.timezone.utc)
                    bars.append(Bar(
                        ts=ts, 
                        open=float(k[1]), 
                        high=float(k[2]), 
                        low=float(k[3]), 
                        close=float(k[4]), 
                        volume=float(k[5])
                    ))
                return bars
            except Exception as e:
                print(f"OKX Fetch Error: {e}")
                return []


    async def stream_klines(self, symbol: str, interval: str = "1m"):
        if self.exchange_id == "binance":
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
        elif self.exchange_id == "okx":
            import websockets
            # OKX format: BTC-USDT
            inst_id = symbol.replace("/", "-")
            # Map interval: 1m -> 1m, 1h -> 1H (OKX specific)
            bar_map = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", 
                       "1h": "1H", "2h": "2H", "4h": "4H"}
            channel_interval = bar_map.get(interval, interval)
            
            url = "wss://ws.okx.com:8443/ws/v5/public"
            async with websockets.connect(url) as ws:
                # Subscribe
                sub_msg = {
                    "op": "subscribe",
                    "args": [{"channel": f"candle{channel_interval}", "instId": inst_id}]
                }
                await ws.send(json.dumps(sub_msg))
                
                async for msg in ws:
                    data = json.loads(msg)
                    if "data" in data:
                        for k in data["data"]:
                            # k: [ts, o, h, l, c, vol, ...]
                            ts = dt.datetime.fromtimestamp(int(k[0]) / 1000.0, tz=dt.timezone.utc)
                            yield Bar(
                                ts=ts,
                                open=float(k[1]),
                                high=float(k[2]),
                                low=float(k[3]),
                                close=float(k[4]),
                                volume=float(k[5]),
                            )
        else:
            raise NotImplementedError(f"Streaming not implemented for {self.exchange_id}")