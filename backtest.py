import pandas as pd
from strategy import candlestick_reversal_strategy
from performance_analysis import analyze_and_plot

def run_backtest():
    file_path = 'data/SOLUSDT-5m-5months.csv'
    print(f"Loading data from {file_path}...")
    
    # Standard format for Binance Klines if no header is present
    column_names = [
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ]
    df = pd.read_csv(file_path, names=column_names)
    
    print("Generating strategy signals...")
    result_df = candlestick_reversal_strategy(df)
    
    # Optional parameters based on performance_analysis defaults
    initial_capital = 1000000.0
    risk_per_trade = 0.02
    rr_ratio = 3.0
    long_only = True  # Added a flag to optionally run long only
    
    print("Running performance analysis and visualization...")
    analyze_and_plot(
        result_df,
        initial_capital=initial_capital,
        risk_per_trade=risk_per_trade,
        rr_ratio=rr_ratio,
        save_path='data/performance_chart.png',
        csv_path='data/strategy_output.csv',
        long_only=long_only
    )
    print("Backtest complete!")

if __name__ == "__main__":
    run_backtest()
