import os
from dotenv import load_dotenv
from market_data_loader import MarketDataLoader
from strategy import candlestick_reversal_strategy
from performance_analysis import analyze_and_plot

# Load environment variables from .env file
load_dotenv()

def main():
    print("Hello from web3quantalgo!")
    
    # Initialize the data loader
    # Set use_api=True to fetch from Roostoo API instead of CSV
    # Make sure ROOSTOO_API_KEY and ROOSTOO_SECRET_KEY are set in environment
    loader = MarketDataLoader("data", use_api=True)
    
    if loader.use_api:
        print("Fetching data from Roostoo API...")
        # Get current ticker data
        ticker_data = loader.get_ticker("BTC/USD")
        if ticker_data and ticker_data.get("Success"):
            print("Ticker data retrieved successfully:")
            print(ticker_data["Data"]["BTC/USD"])
            
            # Get account balance
            balance_data = loader.get_balance()
            if balance_data:
                if balance_data.get("Success"):
                    print("Account Balance:")
                    # Handle both Wallet (documented) and SpotWallet (actual mock API response)
                    wallet = balance_data.get("Wallet") or balance_data.get("SpotWallet", {})
                    print(wallet)
                else:
                    print(f"API Error: {balance_data.get('ErrMsg', 'Unknown error')}")
                    print(f"Full response: {balance_data}")
            else:
                print("Failed to retrieve balance from API")
        else:
            print("Failed to retrieve ticker data from API")
            if ticker_data:
                print(f"Response: {ticker_data}")
    else:
        # Load from CSV
        print("Loading data from CSV...")
        market_data = loader.load_csv("BTCUSD-5m-combined-3months.csv")
        
        # Run the strategy on the loaded DataFrame
        print("Running candlestick reversal strategy...")
        result_df = candlestick_reversal_strategy(market_data)
        
        # Run the performance analysis and plot
        analyze_and_plot(result_df, initial_capital=1000000.0, risk_per_trade=0.01, rr_ratio=4.0)

if __name__ == "__main__":
    main()
