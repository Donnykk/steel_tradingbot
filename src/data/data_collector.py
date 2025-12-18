import asyncio
import os
import sys
import logging
import signal
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from dotenv import load_dotenv
from src.data.exchange import ExchangeDataClient
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
    exchange_id = os.getenv("EXCHANGE_ID", "binance")
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
        client = ExchangeDataClient(exchange_id=exchange_id)
    except Exception as e:
        logger.error(f"Failed to initialize ExchangeDataClient: {e}")
        return

    logger.info(f"Starting data collection for {exchange_id} - {symbol} ({interval})...")

    while not SHUTDOWN:
        try:
            # Connect and stream
            async for bar in client.stream_klines(symbol, interval):
                if SHUTDOWN:
                    break
                
                logger.info(f"Received Bar: {bar}")
                
                # Write to DB
                try:
                    count = write_bars(db_url, exchange_id, symbol, interval, [bar], src="stream")
                    if count > 0:
                        logger.debug(f"Saved bar to DB: {bar.ts}")
                except Exception as db_err:
                    logger.error(f"Database write error: {db_err}")
                
        except NotImplementedError as e:
            logger.error(f"Configuration error: {e}")
            break
        except Exception as e:
            logger.error(f"Stream connection lost or error: {e}")
            if not SHUTDOWN:
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            else:
                break
                
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
