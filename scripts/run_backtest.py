import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.monitor.logger import setup_logging
from src.data.loader import load_dummy_bars
from src.strategies.momentum import MomentumStrategy
from src.risk.basic import BasicRisk
from src.backtest.engine import BacktestEngine, SimpleMatcher

def main():
    setup_logging()
    symbol = "BTCUSDT"
    bars = load_dummy_bars(600)
    strat = MomentumStrategy(symbol=symbol, fast=10, slow=30, size=1.0)
    risk = BasicRisk(max_order_qty=2.0, max_position_qty=5.0)
    matcher = SimpleMatcher()
    engine = BacktestEngine(strategy=strat, matcher=matcher, risk=risk, symbol=symbol)
    equity = engine.run(bars)
    print(f"Final equity: {equity[-1]:.4f}")

if __name__ == "__main__":
    main()
