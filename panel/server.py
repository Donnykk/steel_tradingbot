import os
import sys
import logging
from typing import List, Optional
import psycopg
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env
load_dotenv()

app = FastAPI(title="SteelTrade Panel")
templates = Jinja2Templates(directory="panel/templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Panel")

DB_URL = os.getenv("DB_URL")

def interval_to_seconds(interval: str) -> int:
    try:
        mapping = {
            "1s": 1, "5s": 5, "15s": 15, "30s": 30,
            "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
            "1d": 86400
        }
        if interval in mapping:
            return mapping[interval]
        import re
        m = re.match(r"^(\d+)([smhd])$", interval)
        if not m:
            return 60
        value = int(m.group(1))
        unit = m.group(2)
        if unit == "s":
            return max(1, value)
        if unit == "m":
            return max(60, value * 60)
        if unit == "h":
            return max(3600, value * 3600)
        if unit == "d":
            return max(86400, value * 86400)
        return 60
    except Exception:
        return 60

class BarData(BaseModel):
    time: int  
    open: float
    high: float
    low: float
    close: float
    volume: float

def get_db_connection():
    if not DB_URL:
        raise ValueError("DB_URL not set in .env")
    return psycopg.connect(DB_URL)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/symbols")
async def get_symbols():
    """Get list of available symbols in DB"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT symbol FROM ohlcv_bars ORDER BY symbol")
                rows = cur.fetchall()
                return {"symbols": [row[0] for row in rows]}
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return {"symbols": []}

@app.get("/api/history/{symbol:path}")
async def get_history(symbol: str, interval: str = "1m", limit: int = 1000):
    """Get historical bars for a symbol"""
    try:
        # Decode symbol if needed (e.g. replacing - with /)
        if "-" in symbol and "/" not in symbol:
            symbol = symbol.replace("-", "/")
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                secs = interval_to_seconds(interval)
                if secs <= 0:
                    raise HTTPException(status_code=400, detail="Invalid interval")
                if interval == "1s":
                    cur.execute(
                        """
                        SELECT ts, open, high, low, close, volume 
                        FROM ohlcv_bars 
                        WHERE symbol = %s AND interval = %s
                        ORDER BY ts DESC
                        LIMIT %s
                        """,
                        (symbol, "1s", limit)
                    )
                else:
                    seconds_to_fetch = secs * limit
                    cur.execute(
                        """
                        SELECT ts, open, high, low, close, volume 
                        FROM ohlcv_bars 
                        WHERE symbol = %s AND interval = %s
                        ORDER BY ts DESC
                        LIMIT %s
                        """,
                        (symbol, "1s", seconds_to_fetch)
                    )
                rows_desc = cur.fetchall()
                rows = list(reversed(rows_desc))

                if interval == "1s":
                    data = []
                    seen_times = set()
                    for row in rows:
                        ts_sec = int(row[0] / 1000)
                        if ts_sec in seen_times:
                            continue
                        seen_times.add(ts_sec)
                        data.append({
                            "time": ts_sec,
                            "open": row[1],
                            "high": row[2],
                            "low": row[3],
                            "close": row[4],
                            "volume": row[5]
                        })
                else:
                    buckets = {}
                    order_keys = []
                    for ts_ms, o, h, l, c, v in rows:
                        ts_sec = int(ts_ms / 1000)
                        bucket = (ts_sec // secs) * secs
                        if bucket not in buckets:
                            buckets[bucket] = {"open": o, "high": h, "low": l, "close": c, "volume": v}
                            order_keys.append(bucket)
                        else:
                            b = buckets[bucket]
                            b["high"] = max(b["high"], h)
                            b["low"] = min(b["low"], l)
                            b["close"] = c
                            b["volume"] += v
                    data = [{"time": k, **buckets[k]} for k in order_keys]

                logger.info(f"Returning {len(data)} bars for {symbol}")
                return {"data": data}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=["panel"])