import os
import pandas as pd
import requests
import time
import hmac
import hashlib
import json
import websocket
import threading
from typing import Optional, List
from collections import deque


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

    def get_klines_websocket(self, symbol: str = "btcusdt", interval: str = "5m", num_candles: int = 100, timeout: int = 60) -> pd.DataFrame:
        """
        Fetch kline (candlestick) data from Binance WebSocket stream.
        
        Args:
            symbol: Trading pair (lowercase, e.g., 'btcusdt' for BTC/USDT)
            interval: Kline interval (e.g., '5m' for 5 minutes)
            num_candles: Number of completed candles to collect
            timeout: Maximum time to wait in seconds
            
        Returns:
            DataFrame with OHLCV data indexed by open_time
        """
        klines = deque(maxlen=num_candles)
        ws_error = [None]
        collection_complete = threading.Event()
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if 'k' in data:
                    kline = data['k']
                    # Only add closed candles
                    if kline['x']:  # x = true means kline is closed
                        klines.append(kline)
                        if len(klines) >= num_candles:
                            collection_complete.set()
                            ws.close()
            except Exception as e:
                ws_error[0] = str(e)
                print(f"Error processing message: {e}")
        
        def on_error(ws, error):
            ws_error[0] = str(error)
            print(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed")
        
        def on_open(ws):
            print(f"Connected to Binance WebSocket for {symbol}@kline_{interval}")
        
        # Connect to Binance kline stream
        stream_name = f"{symbol}@kline_{interval}"
        ws_url = f"wss://stream.binance.com:9443/ws/{stream_name}"
        
        print(f"Connecting to Binance WebSocket...")
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Run WebSocket in a thread with timeout
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for collection to complete or timeout
        if not collection_complete.wait(timeout=timeout):
            print(f"Timeout waiting for {num_candles} candles. Collected {len(klines)} candles.")
            ws.close()
        
        if ws_error[0]:
            raise Exception(f"WebSocket error: {ws_error[0]}")
        
        if not klines:
            raise Exception("No kline data received")
        
        # Convert klines to DataFrame
        records = []
        for k in klines:
            records.append({
                'open_time': pd.to_datetime(int(k['t']), unit='ms'),
                'open': float(k['o']),
                'high': float(k['h']),
                'low': float(k['l']),
                'close': float(k['c']),
                'volume': float(k['v']),
                'close_time': pd.to_datetime(int(k['T']), unit='ms'),
                'quote_asset_volume': float(k['q']),
                'number_of_trades': int(k['n']),
                'taker_buy_base_asset_volume': float(k['V']),
                'taker_buy_quote_asset_volume': float(k['Q']),
            })
        
        df = pd.DataFrame(records)
        df.set_index('open_time', inplace=True)
        
        print(f"✓ Collected {len(df)} candles")
        return df

    def load_csv(self, filename: str) -> pd.DataFrame:
        """
        Loads historical klines from a CSV file into a pandas DataFrame.
        
        Supports two formats:
        - Raw format: numeric timestamps in microseconds, no header
        - Master format: ISO datetime strings with header row
        """
        filepath = os.path.join(self.data_path, filename)
        
        # load with header first (master CSV format)
        try:
            df = pd.read_csv(filepath)
            # If successful, convert open_time from ISO datetime string
            df.rename(columns={'Unnamed: 0': 'open_time'}, inplace=True)
            if 'open_time' not in df.columns:
                df.columns = self.columns
            df['open_time'] = pd.to_datetime(df['open_time'])
            df['close_time'] = pd.to_datetime(df['close_time'], errors='coerce')
        except (ValueError, KeyError):
            # Fallback to raw numeric format
            df = pd.read_csv(filepath, names=self.columns, header=None)
            # Convert timestamps from microseconds to datetime
            df['open_time'] = pd.to_datetime(df['open_time'], unit='us')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='us')
        
        # Set the 'open_time' as the DataFrame Index
        df.set_index('open_time', inplace=True)
        
        # Drop unused columns
        df.drop(columns=['ignore'], inplace=True, errors='ignore')
        
        # Convert price and volume columns to float
        numeric_cols = [
            'open', 'high', 'low', 'close', 'volume', 
            'quote_asset_volume', 'taker_buy_base_asset_volume', 
            'taker_buy_quote_asset_volume'
        ]
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        return df
