import pandas as pd
import numpy as np

def fvg_strategy(data):
    """
    Fair Value Gap (FVG) Strategy.
    Looks for an impulsive dip that creates a bearish FVG.
    Then buys when a bullish reversal structure (e.g. green candle or hammer) forms.
    Takes profit at the FVG area.
    """
    if isinstance(data, str):
        df = pd.read_csv(data)
    else:
        df = data.copy()
        
    df.reset_index(drop=True, inplace=True)
    
    signals = [0] * len(df)
    suggested_tp = [np.nan] * len(df)
    suggested_sl = [np.nan] * len(df)
    
    active_fvg = None # Store (fvg_bottom, fvg_top)
    lowest_since_fvg = np.inf
    
    for i in range(5, len(df)):
        # Check for new Bearish FVG (downward gap) indicating an impulsive dip
        # FVG formed by candles i-3, i-2, i-1
        c1_low = df.loc[i-3, 'low']
        c3_high = df.loc[i-1, 'high']
        
        # Condition for bearish FVG: C1 low > C3 high
        if c1_low > c3_high:
            fvg_bottom = c3_high
            fvg_top = c1_low
            # Ensure it's a somewhat significant dip
            drop_pct = (fvg_top - fvg_bottom) / fvg_top
            if drop_pct > 0.001: # 0.1% minimum gap
                active_fvg = (fvg_bottom, fvg_top)
                lowest_since_fvg = df.loc[i-1, 'low']
                
        curr_open = df.loc[i, 'open']
        curr_close = df.loc[i, 'close']
        curr_low = df.loc[i, 'low']
        curr_high = df.loc[i, 'high']
        
        # Check if an active FVG has been filled or invalidated
        if active_fvg:
            fvg_bottom, fvg_top = active_fvg
            
            # Maintain the lowest point reached while below the gap
            if curr_low < lowest_since_fvg:
                lowest_since_fvg = curr_low
            
            # If price completely fills the gap, invalidate
            if curr_high >= fvg_top:
                active_fvg = None
            else:
                # Gap Fill Strategy:
                # Enter LONG when price approaches/enters the previously identified FVG
                if curr_high >= fvg_bottom:
                    signals[i] = 1
                    
                    # Set profit target at the opposite end of the gap (the top of the gap)
                    suggested_tp[i] = fvg_top 
                    
                    # Place stop-loss beyond the gap's furthest point / extreme of the dip
                    # We use the lowest low established before the gap started filling
                    suggested_sl[i] = lowest_since_fvg * 0.9995
                    
                    # Prevent multiple buys for the same FVG
                    active_fvg = None
                    
    df['signal'] = signals
    df['suggested_tp'] = suggested_tp
    df['suggested_sl'] = suggested_sl
    
    return df

# Example usage
if __name__ == "__main__":
    df = fvg_strategy('./data/processed-5m-2026-02.csv')
    df.to_csv('fvg_prices_with_signals.csv', index=False)
    print(df.head())
