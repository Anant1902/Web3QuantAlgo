from market_data_loader import MarketDataLoader
from strategy import candlestick_reversal_strategy
from performance_analysis import analyze_and_plot

def main():
    print("Hello from web3quantalgo!")
    
    # Initialize the data loader
    loader = MarketDataLoader("data")
    
    # Load the raw CSV (the loader automatically adds appropriate names/index)
    print("Loading data...")
    market_data = loader.load_csv("BTCUSD-5m-2026-02.csv")
    
    # Run the strategy on the loaded DataFrame
    print("Running candlestick reversal strategy...")
    result_df = candlestick_reversal_strategy(market_data)
    
    # Run the performance analysis and plot
    analyze_and_plot(result_df, initial_capital=1000000.0, risk_per_trade=0.02, rr_ratio=3.0)

if __name__ == "__main__":
    main()
