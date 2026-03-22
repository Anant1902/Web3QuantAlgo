import asyncio
import json
import websockets
import pandas as pd
import datetime
import os

from strategy import candlestick_reversal_strategy, calculate_trade_parameters
import roostoo

# Configuration
TRADE_COIN = "SOL" # Edit this to trade a different coin (e.g., "ETH", "SOL")
SYMBOL = f"{TRADE_COIN.lower()}usdt"  # Binance symbol
ROOSTOO_SYMBOL = f"{TRADE_COIN}/USD"
INTERVAL = "5m"     # 5-minute candles
WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL}@kline_{INTERVAL}"

DATA_FILE = "live_data.csv"
TRADE_LOG_FILE = "live_trades.csv"

HISTORICAL_FILES = [
    f"data/{TRADE_COIN}USD-5m-combined-3months.csv",
    f"data/{TRADE_COIN}USD-5m-2026-03-01-to-2026-03-20.csv"
]

STATE_FILE = "position_state.json"
exchange_info_cache = {}

def load_position_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_position_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

position_state = load_position_state()

def get_precision(symbol, default=5):
    if symbol in exchange_info_cache:
        return exchange_info_cache[symbol].get("AmountPrecision", default)
    return default
    
def get_price_precision(symbol, default=2):
    if symbol in exchange_info_cache:
        return exchange_info_cache[symbol].get("PricePrecision", default)
    return default


def load_initial_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            if len(df) > 100:
                print(f"✅ Found '{DATA_FILE}' with {len(df)} rows. Skipping historical data import.")
                return df
        except Exception:
            pass
            
    print("Pre-filling data from historical logs (Dec 2025 - Mar 2026)...")
    dfs = []
    for f in HISTORICAL_FILES:
        if os.path.exists(f):
            print(f"Parsing {f}...")
            temp_df = pd.read_csv(f, header=None, usecols=[0,1,2,3,4,5])
            temp_df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            
            first_val = str(temp_df['timestamp'].iloc[0])
            if len(first_val) >= 16:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='us')
            elif len(first_val) >= 13:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='ms')
            else:
                temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp'], unit='s')
            
            dfs.append(temp_df)
            
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
        df.to_csv(DATA_FILE, index=False)
        print(f"Successfully loaded {len(df)} historical rows into {DATA_FILE}")
        return df
        
    df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.to_csv(DATA_FILE, index=False)
    return df

# Globals to store historical klines
klines_df = load_initial_data()

# Initialize files
if not os.path.exists(TRADE_LOG_FILE):
    pd.DataFrame(columns=['timestamp', 'symbol', 'action', 'price', 'quantity', 'source', 'response']).to_csv(TRADE_LOG_FILE, index=False)

def log_trade(action, price, quantity, symbol=ROOSTOO_SYMBOL, response_data=""):
    """Log executed trades."""
    trade_df = pd.DataFrame([{
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'symbol': symbol,
        'action': action,
        'price': price,
        'quantity': quantity,
        'source': 'Bot',
        'response': json.dumps(response_data) if isinstance(response_data, dict) else str(response_data)
    }])
    trade_df.to_csv(TRADE_LOG_FILE, mode='a', header=False, index=False)

def execute_signal(signal, current_price, quantity=0.01, symbol=ROOSTOO_SYMBOL):
    """Execute trade on Roostoo based on prediction."""
    
    precision = get_precision(symbol, default=5)
    quantity = round(quantity, precision)
    
    if signal == 1:
        print(f"Executing BUY order on Roostoo mock API at ~{current_price} for {symbol}...")
        res = roostoo.place_order(symbol, "BUY", quantity, order_type="MARKET")
        print(f"Roostoo Response: {res}")
        if res and res.get("Success"):
            log_trade('BUY', current_price, quantity, symbol, res)
            return res
            
    elif signal == -1:
        print(f"Executing SELL order on Roostoo mock API at ~{current_price} for {symbol}...")
        res = roostoo.place_order(symbol, "SELL", quantity, order_type="MARKET")
        print(f"Roostoo Response: {res}")
        if res and res.get("Success"):
            log_trade('SELL', current_price, quantity, symbol, res)
            return res
            
    return None

async def check_strategy():
    """Run strategy on stored klines."""
    global klines_df
    
    if len(klines_df) < 2:
        return # Need at least 2 complete candles for the strategy
        
    df = klines_df.copy()
    
    # Convert numerical columns to float
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
        
    # Run strategy (it relies on latest candle and previous candle)
    df_with_signals = candlestick_reversal_strategy(df)
    
    # Get latest signal
    latest_index = len(df_with_signals) - 1
    latest_signal = df_with_signals.iloc[latest_index]['signal']
    latest_close = df_with_signals.iloc[latest_index]['close']
    latest_open = df_with_signals.iloc[latest_index]['open']
    
    global position_state
    
    # 1. Manage Active Position (Exit Strategy)
    if position_state.get("active"):
        # Check if the TP order was filled
        tp_order_id = position_state.get("tp_order_id")
        if tp_order_id:
            order_res = roostoo.query_order(order_id=tp_order_id)
            if order_res and order_res.get("Success"):
                matched = order_res.get("OrderMatched", [])
                if matched and matched[0].get("Status") == "FILLED":
                    print(f"Take Profit hit! Position closed.")
                    position_state = {}
                    save_position_state(position_state)
                    return
                    
        # Check if strategy gave a bearish/sell signal to close position early
        if latest_signal == -1:
            print(f"Strategy Sell Signal (-1) Detected! Closing position early at {latest_close}.")
            if position_state.get("tp_order_id"):
                roostoo.cancel_order(order_id=position_state["tp_order_id"])
            quantity = position_state["quantity"]
            execute_signal(-1, latest_close, quantity=quantity)
            position_state = {}
            save_position_state(position_state)
            return
            
        # Check Stop Loss in real time
        sl = position_state["sl"]
        if latest_close <= sl:
            print(f"Stop Loss Triggered! Price {latest_close} <= SL {sl}. Closing position.")
            if position_state.get("tp_order_id"):
                roostoo.cancel_order(order_id=position_state["tp_order_id"])
            quantity = position_state["quantity"]
            execute_signal(-1, latest_close, quantity=quantity)
            position_state = {}
            save_position_state(position_state)
            return

        print(f"Holding active position... SL: {sl:.4f}")
        return

    # 2. Look for Entry (Long Only)
    if latest_signal == 1:
        signal_type = "BUY"
        cash = 100000.0  
        capital = 100000.0
        try:
            balance_res = roostoo.get_balance()
            if balance_res and balance_res.get('Success') and 'Wallet' in balance_res:
                wallet = balance_res['Wallet']
                if 'USD' in wallet:
                    cash = float(wallet['USD'].get('Free', 0.0))
                else:
                    cash = 0.0
                
                ticker_res = roostoo.get_ticker()
                prices = {}
                if ticker_res and ticker_res.get('Success') and 'Data' in ticker_res:
                    for pair, data in ticker_res['Data'].items():
                        coin = pair.split('/')[0]
                        prices[coin] = data.get('LastPrice', 0.0)
                
                total_capital = 0.0
                for coin, balances in wallet.items():
                    amount = balances.get('Free', 0.0) + balances.get('Lock', 0.0)
                    if amount > 0:
                        if coin == 'USD':
                            total_capital += amount
                        elif coin in prices:
                            total_capital += amount * prices[coin]
                        elif coin == TRADE_COIN:
                            total_capital += amount * latest_close
                capital = total_capital
                print(f"Live Roostoo Available Cash: ${cash:.2f} | Total Balance Equivalent: ${capital:.2f}")
        except Exception as e:
            print(f"Error fetching balance from Roostoo: {e}, using default Capital ${capital}.")

        sl, tp, position_size = calculate_trade_parameters(
            df_with_signals, latest_index, latest_signal, latest_open, capital, available_cash=cash
        )
        
        print(f"Signal Detected: {signal_type} at {latest_close}")
        if position_size > 0:
            print(f"Calculated Trade Params -> Size: {position_size:.4f}, SL: {sl:.2f}, TP: {tp:.2f}")
            res = execute_signal(latest_signal, latest_close, quantity=position_size)
            if res and res.get("Success"):
                price_precision = get_price_precision(ROOSTOO_SYMBOL)
                rounded_tp = round(tp, price_precision)
                precision_amt = get_precision(ROOSTOO_SYMBOL)
                rounded_qty = round(position_size, precision_amt)
                
                print(f"Placing LIMIT SELL Take Profit at {rounded_tp}")
                tp_res = roostoo.place_order(ROOSTOO_SYMBOL, "SELL", rounded_qty, price=rounded_tp, order_type="LIMIT")
                
                tp_order_id = None
                if tp_res and tp_res.get("Success"):
                    tp_order_id = tp_res.get("OrderDetail", {}).get("OrderID")
                    
                position_state = {
                    "active": True,
                    "entry_price": latest_close,
                    "quantity": rounded_qty,
                    "sl": sl,
                    "tp": rounded_tp,
                    "tp_order_id": tp_order_id
                }
                save_position_state(position_state)
        else:
            print("Trade skipped: Insufficient data for Stop Loss calculation.")
    else:
        if latest_signal == -1:
            print("Bearish reversal detected, but safely ignored (No active position to close).")
        else:
            print("No trade signal generated.")

async def consume_kline_stream():
    """Consume websocket and process closed candles."""
    global klines_df

    async with websockets.connect(WS_URL) as ws:
        print(f"Connected to Binance WebSocket stream: {WS_URL}")
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                
                k = data['k']
                is_closed = k['x']
                
                if is_closed:
                    # New completed candle
                    new_row = {
                        'timestamp': pd.to_datetime(k['t'], unit='ms'),
                        'open': float(k['o']),
                        'high': float(k['h']),
                        'low': float(k['l']),
                        'close': float(k['c']),
                        'volume': float(k['v'])
                    }
                    
                    df_new = pd.DataFrame([new_row])
                    # Update local dataframe
                    if klines_df.empty:
                        klines_df = df_new
                    else:
                        klines_df = pd.concat([klines_df, df_new], ignore_index=True)
                    # Convert object types before concatenation, handling possible warnings
                    
                    # Ensure timestamp format is consistent
                    klines_df.to_csv(DATA_FILE, index=False)
                    
                    print(f"Candle closed at {new_row['timestamp']}. Close: {new_row['close']}")
                    await check_strategy()

            except Exception as e:
                print(f"WebSocket error: {e}")
                await asyncio.sleep(5)
                # If disconnected, the outer async loop or script restart would be needed. 
                # For robustness we can just break and let a wrapper restart it, 
                # or break and reconnect.
                break

async def main():
    global exchange_info_cache
    print("Fetching exchange rules...")
    info = roostoo.get_exchange_info()
    if info and "TradePairs" in info:
        exchange_info_cache = info["TradePairs"]
        print("Exchange constraints loaded.")
    else:
        print("Warning: Could not fetch exchange constraints.")
        
    while True:
        try:
            await consume_kline_stream()
        except Exception as e:
             print(f"Connection lost, reconnecting in 5s... ({e})")
             await asyncio.sleep(5)

if __name__ == "__main__":
    print("Starting Trading Bot...")
    asyncio.run(main())
