import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.data.exchange import ExchangeDataClient

def main():
    ex_id = os.environ.get("EXCHANGE_ID", "binance")
    symbol = os.environ.get("SYMBOL", "BTC/USDT")
    timeframe = os.environ.get("TIMEFRAME", "1h")
    limit = int(os.environ.get("LIMIT", "100"))
    ex = ExchangeDataClient(exchange_id=ex_id)
    bars = ex.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    print(f"bars: {len(bars)}")
    for b in bars[-5:]:
        print(b)

if __name__ == "__main__":
    main()
