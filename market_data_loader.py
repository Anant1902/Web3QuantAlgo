import os
import pandas as pd
import requests
import time
import hmac
import hashlib
from typing import Optional


class MarketDataLoader:
    def __init__(self, data_path: str, use_api: bool = False):
        self.data_path = data_path
        self.use_api = use_api
        
        # API configuration
        self.base_url = "https://mock-api.roostoo.com"
        self.api_key = os.getenv("ROOSTOO_API_KEY")
        self.secret_key = os.getenv("ROOSTOO_SECRET_KEY")
        
        # Standard Binance kline/candlestick columns
        self.columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'number_of_trades', 
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]

    def _get_timestamp(self) -> str:
        """Return a 13-digit millisecond timestamp as string."""
        return str(int(time.time() * 1000))

    def _get_signed_headers(self, payload: dict = {}) -> tuple:
        """
        Generate signed headers and totalParams for RCL_TopLevelCheck endpoints.
        Returns: (headers dict, updated payload dict, total_params string)
        """
        payload['timestamp'] = self._get_timestamp()
        sorted_keys = sorted(payload.keys())
        total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)

        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            total_params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            'RST-API-KEY': self.api_key,
            'MSG-SIGNATURE': signature
        }

        return headers, payload, total_params

    def get_ticker(self, pair: str = "BTC/USD") -> Optional[dict]:
        """Get current market ticker from API."""
        if not self.api_key or not self.secret_key:
            raise ValueError("API_KEY and SECRET_KEY environment variables must be set")
        
        url = f"{self.base_url}/v3/ticker"
        params = {
            'timestamp': self._get_timestamp(),
            'pair': pair
        }
        
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting ticker from API: {e}")
            return None

    def get_balance(self) -> Optional[dict]:
        """Get wallet balance from API (requires signed request)."""
        if not self.api_key or not self.secret_key:
            raise ValueError("API_KEY and SECRET_KEY environment variables must be set")
        
        url = f"{self.base_url}/v3/balance"
        headers, payload, _ = self._get_signed_headers({})
        
        try:
            res = requests.get(url, headers=headers, params=payload)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting balance from API: {e}")
            return None

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
