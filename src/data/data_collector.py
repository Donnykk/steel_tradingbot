import asyncio
import os
import sys
import logging
import signal
import psycopg
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from dotenv import load_dotenv
from src.data.okx_fetcher import ExchangeDataClient
from src.data.store_postgres import write_bars, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataCollector")

# Global flag for shutdown
SHUTDOWN = False

def handle_signal(signum, frame):
    global SHUTDOWN
    logger.info("Received shutdown signal. Stopping...")
    SHUTDOWN = True

async def run_collector():
    # Load environment variables
    load_dotenv()
    
    # Configuration
    symbol = os.getenv("SYMBOL", "BTC/USDT")
    interval = os.getenv("TIMEFRAME", "1m")
    db_url = os.getenv("DB_URL")
    
    
    if not db_url:
        logger.error("DB_URL is not set in environment variables.")
        return

    # Initialize Database
    try:
        logger.info(f"Initializing database at {db_url.split('@')[-1]}...") # Log safe part of URL
        init_db(db_url)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return

    # Initialize Exchange Client
    try:
        client = ExchangeDataClient()
    except Exception as e:
        logger.error(f"Failed to initialize ExchangeDataClient: {e}")
        return

    logger.info(f"Starting data collection for {symbol} ({interval})...")

    try:
        do_backfill = os.getenv("BACKFILL_ON_START", "true").lower() not in ("false", "0", "no")
        backfill_limit = int(os.getenv("BACKFILL_LIMIT", "2000"))
        if do_backfill and backfill_limit > 0:
            existing = 0
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM ohlcv_bars WHERE exchange=%s AND symbol=%s AND interval=%s",
                        (exchange_id, symbol, interval)
                    )
                    row = cur.fetchone()
                    existing = row[0] if row else 0
            if existing < backfill_limit:
                bars = client.fetch_ohlcv(symbol, timeframe=interval, limit=backfill_limit)
                if bars:
                    saved = write_bars(db_url, symbol, interval, bars, src="backfill")
                    logger.info(f"Backfilled {saved} bars for {symbol} ({interval})")
            else:
                logger.info(f"Skip backfill: already have {existing} bars for {symbol} ({interval})")
    except Exception as e:
        logger.error(f"Backfill error: {e}")

    # while not SHUTDOWN:
    #     try:
    #         # Connect and stream
    #         async for bar in client.stream_klines(symbol, interval):
    #             if SHUTDOWN:
    #                 break
                
    #             logger.info(f"Received Bar: {bar}")
                
    #             # Write to DB
    #             try:
    #                 count = write_bars(db_url, exchange_id, symbol, interval, [bar], src="stream")
    #                 if count > 0:
    #                     logger.debug(f"Saved bar to DB: {bar.ts}")
    #             except Exception as db_err:
    #                 logger.error(f"Database write error: {db_err}")
                
    #     except NotImplementedError as e:
    #         logger.error(f"Configuration error: {e}")
    #         break
    #     except Exception as e:
    #         logger.error(f"Stream connection lost or error: {e}")
    #         if not SHUTDOWN:
    #             logger.info("Reconnecting in 5 seconds...")
    #             await asyncio.sleep(5)
    #         else:
    #             break
                
    logger.info("Collector stopped.")

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # On Windows, signal handling with asyncio can be tricky, but this is a standard approach
    try:
        asyncio.run(run_collector())
    except KeyboardInterrupt:
        pass