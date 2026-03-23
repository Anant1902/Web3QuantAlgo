import pandas as pd

def candlestick_reversal_strategy(data):
    """
    Candlestick reversal trading strategy.
    Adds 'signal' column with: 1 (buy), -1 (sell), 0 (hold)
    """
    if isinstance(data, str):
        df = pd.read_csv(data)
    else:
        df = data.copy()
        
    df.reset_index(drop=True, inplace=True)
    
    # Calculate a 20-period moving average of volume for "larger than usual" check
    if 'volume' in df.columns:
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
    else:
        df['volume_sma'] = 0
        
    signals = [0] * len(df)
    
    for i in range(20, len(df)): # Start at 20 to allow SMA to compute
        prev2_open = df.loc[i-2, 'open']
        prev2_close = df.loc[i-2, 'close']
        
        prev_open = df.loc[i-1, 'open']
        prev_close = df.loc[i-1, 'close']
        prev_high = df.loc[i-1, 'high']
        prev_low = df.loc[i-1, 'low']
        
        curr_open = df.loc[i, 'open']
        curr_close = df.loc[i, 'close']
        curr_high = df.loc[i, 'high']
        curr_low = df.loc[i, 'low']
        
        prev_volume = df.loc[i-1, 'volume'] if 'volume' in df.columns else 0
        prev_volume_sma = df.loc[i-1, 'volume_sma'] if 'volume_sma' in df.columns else 0
        
        # Hammer pattern (bullish reversal) on the PREVIOUS candle
        prev2_body = abs(prev2_close - prev2_open)
        body = abs(prev_close - prev_open)
        lower_wick = min(prev_open, prev_close) - prev_low
        upper_wick = prev_high - max(prev_open, prev_close)
        
        is_hammer = (lower_wick > 2 * body and upper_wick < body and 
                     prev2_close < prev2_open and body < prev2_body and 
                     prev_open <= min(prev2_open, prev2_close) and
                     prev_volume > prev_volume_sma)
        
        # Shooting star pattern (bearish reversal) on the PREVIOUS candle
        is_shooting_star = (upper_wick > 2 * body and lower_wick < body and 
                            prev2_close > prev2_open and body < prev2_body and
                            prev_volume > prev_volume_sma)
        
        # Confirmation on the CURRENT candle
        bullish_confirmation = curr_close > curr_open and curr_close > prev_close and curr_high <= prev2_open
        bearish_confirmation = curr_close < curr_open and curr_close < prev_close and curr_high <= prev2_open
        
        if is_hammer and bullish_confirmation:
            signals[i] = 1  # Buy signal
        
        # Shooting star pattern (bearish reversal) with confirmation
        elif is_shooting_star and bearish_confirmation:
            signals[i] = -1  # Sell signal
    
    df['signal'] = signals
    return df

def calculate_trade_parameters(df, current_index, signal, entry_price, capital, available_cash=None, risk_per_trade=0.02, rr_ratio=3.0):
    """
    Calculates Stop Loss (SL), Take Profit (TP), and Position Size based on risk management rules.
    """
    if current_index <= 5:
        return 0.0, 0.0, 0.0
        
    if available_cash is None:
        available_cash = capital
        
    risk_amount = capital * risk_per_trade
    sl = 0.0
    tp = 0.0
    position_size = 0.0
    
    if signal == 1: # LONG
        # SL at the midpoint between the bottom of the body and the low of the hammer (i-1)
        prev_low = df.loc[current_index-1, 'low']
        prev_open = df.loc[current_index-1, 'open']
        prev_close = df.loc[current_index-1, 'close']
        bottom_of_body = min(prev_open, prev_close)
        
        sl = prev_low + ((bottom_of_body - prev_low) * 0.1)
        
        if entry_price > sl: # Valid risk distance
            price_delta_per_unit_in_rr = entry_price - sl
            
            # Position Size in SOL such that if SL is hit, we lose exactly risk_amount
            # This ensures we are only *allocating* enough such that if the SL hits, 
            # we lose exactly our risk_amount.
            position_size = (risk_amount / price_delta_per_unit_in_rr)
            
            max_size = available_cash / entry_price
            if position_size > max_size:
                position_size = max_size
            
            tp = entry_price + (price_delta_per_unit_in_rr * rr_ratio)
            
    elif signal == -1: # SHORT
        # SL at the midpoint between the top of the body and the high of the shooting star (i-1)
        prev_high = df.loc[current_index-1, 'high']
        prev_open = df.loc[current_index-1, 'open']
        prev_close = df.loc[current_index-1, 'close']
        top_of_body = max(prev_open, prev_close)
        
        sl = top_of_body + ((prev_high - top_of_body) / 2.0)
        
        if sl > entry_price: # Valid risk distance
            price_delta_per_unit_in_rr = sl - entry_price
            
            position_size = (risk_amount / price_delta_per_unit_in_rr)
            
            # For shorts, the risk logic requires margin or borrowing equivalent
            # For spot trading limits, we ensure we don't sell more value than we have
            max_size = available_cash / entry_price
            if position_size > max_size:
                position_size = max_size
                
            tp = entry_price - (price_delta_per_unit_in_rr * rr_ratio)
    
    print(f"Calculated trade parameters at index {current_index}: SL={sl:.2f}, TP={tp:.2f}, Position Size={position_size:.6f} SOL")
    return sl, tp, position_size

# Example usage
if __name__ == "__main__":
    df = candlestick_reversal_strategy('./data/processed-5m-2026-02.csv')
    df.to_csv('prices_with_signals.csv', index=False)
    print(df.head())