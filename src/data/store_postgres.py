import time
from typing import List
from src.core.types import Bar

def _epoch_ms(dt):
    return int(dt.timestamp() * 1000)

def init_db(db_url: str):
    import psycopg
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv_bars (
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    ts BIGINT NOT NULL,
                    open DOUBLE PRECISION NOT NULL,
                    high DOUBLE PRECISION NOT NULL,
                    low DOUBLE PRECISION NOT NULL,
                    close DOUBLE PRECISION NOT NULL,
                    volume DOUBLE PRECISION NOT NULL,
                    src TEXT,
                    ingest_ts BIGINT NOT NULL,
                    PRIMARY KEY (exchange, symbol, interval, ts)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_ts ON ohlcv_bars(symbol, ts)"
            )
        conn.commit()

def write_bars(db_url: str, exchange: str, symbol: str, interval: str, bars: List[Bar], src: str = "api"):
    if not bars:
        return 0
    import psycopg
    # init_db(db_url)  # Optimization: Expect DB to be initialized externally
    now_ms = int(time.time() * 1000)
    rows = [
        (
            exchange,
            symbol,
            interval,
            _epoch_ms(b.ts),
            b.open,
            b.high,
            b.low,
            b.close,
            b.volume,
            src,
            now_ms,
        )
        for b in bars
    ]
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ohlcv_bars (exchange, symbol, interval, ts, open, high, low, close, volume, src, ingest_ts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exchange, symbol, interval, ts) DO UPDATE SET
                    open=EXCLUDED.open,
                    high=EXCLUDED.high,
                    low=EXCLUDED.low,
                    close=EXCLUDED.close,
                    volume=EXCLUDED.volume,
                    src=EXCLUDED.src,
                    ingest_ts=EXCLUDED.ingest_ts
                """
                ,
                rows,
            )
        conn.commit()
    return len(rows)

def load_bars(db_url: str, exchange: str, symbol: str, interval: str, start_ts: int = 0, end_ts: int = 2**63 - 1) -> List[Bar]:
    import psycopg
    import datetime as dt
    
    query = """
        SELECT ts, open, high, low, close, volume 
        FROM ohlcv_bars 
        WHERE exchange = %s AND symbol = %s AND interval = %s AND ts >= %s AND ts <= %s
        ORDER BY ts ASC
    """
    
    bars = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (exchange, symbol, interval, start_ts, end_ts))
            rows = cur.fetchall()
            for row in rows:
                ts_ms, o, h, l, c, v = row
                bars.append(Bar(
                    ts=dt.datetime.fromtimestamp(ts_ms / 1000.0),
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=v
                ))
    return bars

