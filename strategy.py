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
    
    signals = [0] * len(df)
    
    for i in range(1, len(df)):
        prev_open = df.loc[i-1, 'open']
        prev_close = df.loc[i-1, 'close']
        prev_high = df.loc[i-1, 'high']
        prev_low = df.loc[i-1, 'low']
        
        curr_open = df.loc[i, 'open']
        curr_close = df.loc[i, 'close']
        curr_high = df.loc[i, 'high']
        curr_low = df.loc[i, 'low']
        
        # Hammer pattern (bullish reversal)
        body = abs(curr_close - curr_open)
        lower_wick = min(curr_open, curr_close) - curr_low
        upper_wick = curr_high - max(curr_open, curr_close)
        
        if lower_wick > 2 * body and upper_wick < body and prev_close < prev_open:
            signals[i] = 1  # Buy signal
        
        # Shooting star pattern (bearish reversal) is disabled to prevent shorting
        # elif upper_wick > 2 * body and lower_wick < body and prev_close > prev_open:
        #     signals[i] = -1  # Sell signal
    
    df['signal'] = signals
    return df

def calculate_trade_parameters(df, current_index, signal, entry_price, capital, risk_per_trade=0.02, rr_ratio=3.0):
    """
    Calculates Stop Loss (SL), Take Profit (TP), and Position Size based on risk management rules.
    """
    if current_index <= 5:
        return 0.0, 0.0, 0.0
        
    risk_amount = capital * risk_per_trade
    sl = 0.0
    tp = 0.0
    position_size = 0.0
    
    if signal == 1: # LONG
        # SL at previous local support (minimum low of the last 5 finalized candles)
        sl = df.loc[current_index-6:current_index-1, 'low'].min()
        if entry_price > sl: # Valid risk distance
            price_delta_per_unit_in_rr = entry_price - sl
            
            # Position Size in BTC such that if SL is hit, we lose exactly risk_amount
            # This ensures we are only *allocating* enough such that if the SL hits, 
            # we lose exactly our risk_amount.
            position_size = (risk_amount / price_delta_per_unit_in_rr)
            
            tp = entry_price + (price_delta_per_unit_in_rr * rr_ratio)
            
    elif signal == -1: # SHORT
        # SL at previous local resistance (maximum high of the last 5 finalized candles)
        sl = df.loc[current_index-6:current_index-1, 'high'].max()
        if sl > entry_price: # Valid risk distance
            price_delta_per_unit_in_rr = sl - entry_price
            
            position_size = (risk_amount / price_delta_per_unit_in_rr)
            
            # For shorts, the risk logic requires margin or borrowing equivalent
            # For spot trading limits, we ensure we don't sell more value than we have
                
            tp = entry_price - (price_delta_per_unit_in_rr * rr_ratio)
            
    return sl, tp, position_size

# Example usage
if __name__ == "__main__":
    df = candlestick_reversal_strategy('./data/processed-5m-2026-02.csv')
    df.to_csv('prices_with_signals.csv', index=False)
    print(df.head())