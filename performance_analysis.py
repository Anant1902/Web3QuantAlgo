import matplotlib.pyplot as plt
import plotly.graph_objects as go
import pandas as pd

def backtest_strategy(df, initial_capital=1000000.0, risk_per_trade=0.02, rr_ratio=3.0):
    """
    Backtests the strategy using generated signals.
    - initial_capital: Starting capital (e.g., 1,000,000)
    - risk_per_trade: Amount of capital risked per trade (e.g., 0.02 for 2%)
    - rr_ratio: Risk-to-Reward ratio (e.g., 3.0 for 1:3 RR)
    SL is placed at the highest/lowest point of the last 5 periods (representing support/resistance).
    Returns the dataframe and a list of trade dictionaries.
    """
    capital = initial_capital
    capital_history = []
    trades = []
    current_trade = None
    
    in_position = False
    position_type = None
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    position_size = 0.0
    
    for i in range(len(df)):
        # Record equity curve at the current point in time
        capital_history.append(capital)
        
        curr_row = df.loc[i]
        
        # Check if an existing position hit SL or TP
        if in_position:
            if position_type == 'LONG':
                # Conservative approach: Check if SL is hit.
                if curr_row['low'] <= sl:
                    loss = (entry_price - sl) * position_size
                    capital -= loss
                    current_trade.update({'exit_i': i, 'exit_price': sl, 'pnl': -loss, 'reason': 'SL'})
                    trades.append(current_trade)
                    in_position = False
                elif curr_row['high'] >= tp:
                    profit = (tp - entry_price) * position_size
                    capital += profit
                    current_trade.update({'exit_i': i, 'exit_price': tp, 'pnl': profit, 'reason': 'TP'})
                    trades.append(current_trade)
                    in_position = False
                    
            elif position_type == 'SHORT':
                if curr_row['high'] >= sl:
                    loss = (sl - entry_price) * position_size
                    capital -= loss
                    current_trade.update({'exit_i': i, 'exit_price': sl, 'pnl': -loss, 'reason': 'SL'})
                    trades.append(current_trade)
                    in_position = False
                elif curr_row['low'] <= tp:
                    profit = (entry_price - tp) * position_size
                    capital += profit
                    current_trade.update({'exit_i': i, 'exit_price': tp, 'pnl': profit, 'reason': 'TP'})
                    trades.append(current_trade)
                    in_position = False
        
        # Check for new signals to open a position
        # We need at least index > 5 to safely get the previous 5 periods for Support/Resistance
        if not in_position and i > 5:
            prev_signal = df.loc[i-1, 'signal']
            
            if prev_signal == 1:
                # Buy signal
                position_type = 'LONG'
                entry_price = curr_row['open']
                # SL at previous local support (minimum low of the last 5 finalized candles)
                sl = df.loc[i-6:i-1, 'low'].min()
                
                if entry_price > sl: # Valid risk distance
                    risk_per_unit = entry_price - sl
                    risk_amount = capital * risk_per_trade
                    position_size = risk_amount / risk_per_unit
                    tp = entry_price + (risk_per_unit * rr_ratio)
                    in_position = True
                    current_trade = {'type': 'LONG', 'entry_i': i, 'entry_price': entry_price, 'size': position_size}
                    
            elif prev_signal == -1:
                # Sell signal
                position_type = 'SHORT'
                entry_price = curr_row['open']
                # SL at previous local resistance (maximum high of the last 5 finalized candles)
                sl = df.loc[i-6:i-1, 'high'].max()
                
                if sl > entry_price: # Valid risk distance
                    risk_per_unit = sl - entry_price
                    risk_amount = capital * risk_per_trade
                    position_size = risk_amount / risk_per_unit
                    tp = entry_price - (risk_per_unit * rr_ratio)
                    in_position = True
                    current_trade = {'type': 'SHORT', 'entry_i': i, 'entry_price': entry_price, 'size': position_size}

    df['capital'] = capital_history
    return df, trades

def plot_interactive_trades(df, trades, save_path='data/interactive_trades.html'):
    """
    Creates an interactive Plotly candlestick chart with trade entries and exits.
    """
    print(f"\nGenerating interactive trades chart...")
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    )])
    
    # Add portfolio balance trace on secondary y-axis
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['capital'],
        name='Portfolio Balance',
        line=dict(color='blue', width=2),
        opacity=0.3, # Semi-transparent to avoid obscuring candles
        yaxis='y2'
    ))
    
    # Extract trade markers
    # Using df.index based on the stored integer positions
    long_entry_x = [df.index[t['entry_i']] for t in trades if t['type'] == 'LONG']
    long_entry_y = [t['entry_price'] for t in trades if t['type'] == 'LONG']
    short_entry_x = [df.index[t['entry_i']] for t in trades if t['type'] == 'SHORT']
    short_entry_y = [t['entry_price'] for t in trades if t['type'] == 'SHORT']
    
    exit_tp_x = [df.index[t['exit_i']] for t in trades if t.get('reason') == 'TP']
    exit_tp_y = [t['exit_price'] for t in trades if t.get('reason') == 'TP']
    exit_sl_x = [df.index[t['exit_i']] for t in trades if t.get('reason') == 'SL']
    exit_sl_y = [t['exit_price'] for t in trades if t.get('reason') == 'SL']
    
    # Add traces for entries and exits
    fig.add_trace(go.Scatter(x=long_entry_x, y=long_entry_y, mode='markers',
                             marker=dict(symbol='triangle-up', size=12, color='green', line=dict(width=1, color='DarkSlateGrey')),
                             name='Long Entry'))
    fig.add_trace(go.Scatter(x=short_entry_x, y=short_entry_y, mode='markers',
                             marker=dict(symbol='triangle-down', size=12, color='red', line=dict(width=1, color='DarkSlateGrey')),
                             name='Short Entry'))
    fig.add_trace(go.Scatter(x=exit_tp_x, y=exit_tp_y, mode='markers',
                             marker=dict(symbol='star', size=10, color='gold', line=dict(width=1, color='DarkSlateGrey')),
                             name='Take Profit Hit'))
    fig.add_trace(go.Scatter(x=exit_sl_x, y=exit_sl_y, mode='markers',
                             marker=dict(symbol='x', size=10, color='black'),
                             name='Stop Loss Hit'))
                             
    fig.update_layout(
        title='Strategy Execution: Entries, Exits & Portfolio Balance',
        xaxis_title='Time',
        yaxis_title='Price (USD)',
        yaxis2=dict(
            title='Capital (USD)',
            overlaying='y',
            side='right',
            fixedrange=False
        ),
        xaxis_rangeslider_visible=True,
        template='plotly_white',
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(255, 255, 255, 0.8)'
        )
    )
    
    # Crucial fix: The rangeslider defaults to locking the Y-axis zoom. 
    # Setting fixedrange=False allows the Y-axis to scale to the selected window 
    # when box-zooming on the graph.
    fig.update_yaxes(fixedrange=False)
    
    fig.write_html(save_path, include_plotlyjs='cdn')
    print(f"Interactive trades chart saved to '{save_path}'")

def analyze_and_plot(result_df, initial_capital=1000000.0, risk_per_trade=0.02, rr_ratio=3.0, save_path='data/performance_chart.png', csv_path='data/strategy_output.csv'):
    # Run the backtest 
    print(f"Running backtest with initial capital ${initial_capital:,.2f}...")
    backtested_df, trades = backtest_strategy(result_df, initial_capital=initial_capital, risk_per_trade=risk_per_trade, rr_ratio=rr_ratio)
    
    final_capital = backtested_df['capital'].iloc[-1]
    print(f"\nFinal Capital: ${final_capital:,.2f}")
    print(f"Total Completed Trades: {len(trades)}")
    
    # Output existing performance plot
    print("\nGenerating performance chart...")
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # Plot Portfolio Equity on primary y-axis
    color1 = 'tab:green'
    ax1.set_xlabel('Trades / Time')
    ax1.set_ylabel('Capital in USD', color=color1)
    ax1.plot(backtested_df.index, backtested_df['capital'], label='Portfolio Equity', color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True)

    # Create a secondary y-axis for the close price
    ax2 = ax1.twinx()
    color2 = 'tab:blue'
    ax2.set_ylabel('BTCUSD Close Price', color=color2)
    ax2.plot(backtested_df.index, backtested_df['close'], label='Close Price', color=color2, alpha=0.5)
    ax2.tick_params(axis='y', labelcolor=color2)

    # Combine legends from both axes
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')

    plt.title('Strategy Performance vs Asset Price')
    fig.tight_layout()
    
    # Save chart
    plt.savefig(save_path)
    print(f"Chart saved to '{save_path}'")
    
    # Run the interactive Plotly graphing function
    plot_interactive_trades(backtested_df, trades, save_path='data/interactive_trades.html')
    
    # Optionally, save to CSV
    backtested_df.to_csv(csv_path, index=False)
    print(f"Full output saved to {csv_path}")
