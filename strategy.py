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
        
        # Shooting star (bearish reversal)
        elif upper_wick > 2 * body and lower_wick < body and prev_close > prev_open:
            signals[i] = -1  # Sell signal
    
    df['signal'] = signals
    return df

# Example usage
if __name__ == "__main__":
    df = candlestick_reversal_strategy('./data/processed-5m-2026-02.csv')
    df.to_csv('prices_with_signals.csv', index=False)
    print(df.head())