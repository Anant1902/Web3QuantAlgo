from market_data_loader import MarketDataLoader
from strategy2 import fvg_strategy
from performance_analysis import analyze_and_plot

def main():
    print("Hello from web3quantalgo!")
    
    # Initialize the data loader
    loader = MarketDataLoader("data")
    
    # Load the raw CSV (the loader automatically adds appropriate names/index)
    print("Loading data...")
    market_data = loader.load_csv("BTCUSD-5m-combined-3months.csv")
    
    # Run the strategy on the loaded DataFrame
    print("Running FVG strategy...")
    result_df = fvg_strategy(market_data)
    
    # Run the performance analysis and plot
    analyze_and_plot(result_df, initial_capital=1000000.0, risk_per_trade=0.05, rr_ratio=4.0)

if __name__ == "__main__":
    main()
