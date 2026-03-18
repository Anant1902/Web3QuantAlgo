import os
import pandas as pd


class MarketDataLoader:
    def __init__(self, data_path: str):
        self.data_path = data_path
        # Standard Binance kline/candlestick columns
        self.columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'number_of_trades', 
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]

    def load_csv(self, filename: str) -> pd.DataFrame:
        """
        Loads historical klines from a CSV file into a pandas DataFrame,
        formats it for algo trading, and sets a Datetime index.
        """
        filepath = os.path.join(self.data_path, filename)
        
        # 1. Read CSV using the defined column names
        df = pd.read_csv(filepath, names=self.columns)
        
        # 2. Convert timestamps (microseconds) to datetime objects
        df['open_time'] = pd.to_datetime(df['open_time'], unit='us')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='us')
        
        # 3. Set the 'open_time' as the DataFrame Index for easy time-series operations
        df.set_index('open_time', inplace=True)
        
        # 4. Drop unused legacy columns
        df.drop(columns=['ignore'], inplace=True, errors='ignore')
        
        # 5. Ensure price and volume data are floating point numbers
        numeric_cols = [
            'open', 'high', 'low', 'close', 'volume', 
            'quote_asset_volume', 'taker_buy_base_asset_volume', 
            'taker_buy_quote_asset_volume'
        ]
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        return df


if __name__ == "__main__":
    # Test the loader with your existing data
    loader = MarketDataLoader("data")
    market_data = loader.load_csv("BTCUSD-5m-2026-02.csv")
    
    print("Market Data Head:")
    print(market_data[['open', 'high', 'low', 'close', 'volume']].head())
    print("\nData Info:")
    market_data.info()
