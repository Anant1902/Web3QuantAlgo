import pandas as pd
from market_data_loader import MarketDataLoader
from strategy2 import fvg_strategy
from performance_analysis import backtest_strategy

loader = MarketDataLoader("data")
market_data = loader.load_csv("BTCUSD-5m-combined-3months.csv")
result_df = fvg_strategy(market_data)

# Replicate what's in analyze_and_plot
result_df, trades = backtest_strategy(result_df, initial_capital=1000000.0, risk_per_trade=0.02, rr_ratio=3.0)

for t in trades[:1]:
    print(t)
