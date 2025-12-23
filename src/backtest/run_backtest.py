import os
import sys
from dotenv import load_dotenv

# Ensure project root is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

import datetime as dt
from typing import List

from src.core.types import Bar
from src.data.store_postgres import load_bars, init_db
from src.strategies.momentum import MomentumStrategy
from src.risk.basic import BasicRisk
from src.backtest.engine import BacktestEngine, SimpleMatcher

# Load environment variables
load_dotenv()

def generate_dummy_data() -> List[Bar]:
    """Generate some dummy data if DB is empty or not available for quick testing."""
    bars = []
    base_price = 10000.0
    for i in range(1000):
        ts = dt.datetime.now() - dt.timedelta(minutes=1000-i)
        change = (i % 10 - 5) + (0.5 if i % 20 > 10 else -0.5)
        base_price += change
        bars.append(Bar(
            ts=ts,
            open=base_price,
            high=base_price + 5,
            low=base_price - 5,
            close=base_price + change,
            volume=100.0
        ))
    return bars

def main():
    symbol = os.getenv("BACKTEST_SYMBOL", "BTC-USDT")
    exchange = os.getenv("BACKTEST_EXCHANGE", "okx")
    interval = os.getenv("BACKTEST_INTERVAL", "1m")
    db_url = os.getenv("DB_URL", "")
    use_dummy = os.getenv("BACKTEST_USE_DUMMY", "false").lower() == "true"

    print(f"Starting backtest for {symbol} on {exchange} ({interval})...")
    
    bars = []
    if use_dummy:
        print("Using dummy data generation...")
        bars = generate_dummy_data()
    else:
        try:
            print(f"Loading data from {db_url}...")
            # Load last 30 days of data roughly
            start_ts = int((dt.datetime.now() - dt.timedelta(days=30)).timestamp() * 1000)
            bars = load_bars(db_url, exchange, symbol, interval, start_ts=start_ts)
        except Exception as e:
            print(f"Error loading data from DB: {e}")
            print("Falling back to dummy data generation...")
            bars = generate_dummy_data()

    if not bars:
        print("No data found. Exiting.")
        return

    print(f"Loaded {len(bars)} bars.")

    # Initialize components
    strategy = MomentumStrategy(symbol=symbol, fast=10, slow=30, size=0.1)
    risk = BasicRisk(max_order_qty=1.0, max_position_qty=5.0)
    matcher = SimpleMatcher(maker_fee=0.0002, taker_fee=0.0005)
    
    engine = BacktestEngine(strategy, matcher, risk, symbol=symbol)
    
    # Run backtest
    print("Running backtest engine...")
    engine.run(bars)
    
    # Analyze results
    print("Analyzing results...")
    report = engine.analyze()
    
    # Print report
    print("\n" + "="*40)
    print(" BACKTEST REPORT ")
    print("="*40)
    print(f"Symbol:       {symbol}")
    print(f"Period:       {bars[0].ts} - {bars[-1].ts}")
    print(f"Trades:       {report['trades']}")
    print(f"Final Equity: {report['final_equity']:.4f}")
    print(f"Max Drawdown: {report['max_drawdown']:.4f}")
    print(f"Sharpe Ratio: {report['sharpe']:.4f}")
    print(f"Win Rate:     {report['win_rate']:.2%}")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
