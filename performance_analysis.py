import matplotlib.pyplot as plt
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def calculate_metrics(df):
    """
    Calculates strategy performance metrics.
    Assumes each row in df is a 5-minute interval.
    """
    # Portfolio periodic returns (clean infinities and NaNs)
    returns = df['capital'].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    N = 288 * 365 # Count of 5-min intervals in a standard 365-day year

    # Annualized components
    mean_return = returns.mean() * N
    volatility = returns.std() * np.sqrt(N)
    
    # Sharpe Ratio
    sharpe = mean_return / volatility if volatility != 0 else 0
    
    # Sortino Ratio (use downside deviation). If downside volatility is zero
    # (e.g., almost no negative periodic returns) fall back to total volatility
    downside_returns = returns[returns < 0]
    if downside_returns.empty or downside_returns.std() == 0:
        # Fallback to total volatility to avoid division by near-zero
        downside_volatility = volatility
    else:
        downside_volatility = downside_returns.std() * np.sqrt(N)
    sortino = mean_return / downside_volatility if downside_volatility != 0 else np.nan
    
    # Calmar Ratio
    cumulative_max = df['capital'].cummax()
    drawdown = (df['capital'] - cumulative_max) / cumulative_max
    mdd = abs(drawdown.min())
    calmar = mean_return / mdd if mdd != 0 else 0
    
    # Calculate Beta and Alpha relative to the Buy and Hold asset path
    market_returns = df['close'].pct_change().dropna()
    
    # Align lengths just in case (they should be identical coming from same DF)
    strat_r = returns.align(market_returns, join='inner')[0]
    mkt_r = market_returns.align(returns, join='inner')[0]
    
    # Covariance and Variance to find Beta
    covariance = strat_r.cov(mkt_r)
    variance = mkt_r.var()
    beta = covariance / variance if variance != 0 else np.nan
    
    # Calculate Alpha (Annualized) based on CAPM: Alpha = StratReturn - (RiskFree + Beta * (MarketReturn - RiskFree))
    # Assuming risk free rate of 0% for crypto strategies for simplicity
    annualized_market_return = mkt_r.mean() * N
    alpha = mean_return - (beta * annualized_market_return) if np.isfinite(beta) else np.nan

    # Calculate Annualized Percentage Return on Portfolio
    # Total percentage return converted to an annualized figure using geometric mean
    total_return = (df['capital'].iloc[-1] / df['capital'].iloc[0]) - 1
    years = len(df) / N
    if years > 0:
        annualized_return = (1 + total_return) ** (1 / years) - 1
    else:
        annualized_return = 0

    # Composite Score
    # If any metric is not finite, set composite parts to zero for safety
    s_sortino = sortino if np.isfinite(sortino) else 0.0
    s_sharpe = sharpe if np.isfinite(sharpe) else 0.0
    s_calmar = calmar if np.isfinite(calmar) else 0.0
    composite_score = (0.4 * s_sortino) + (0.3 * s_sharpe) + (0.3 * s_calmar)
    
    return {
        'Sharpe Ratio': sharpe,
        'Sortino Ratio': sortino,
        'Calmar Ratio': calmar,
        'Max Drawdown': mdd,
        'Beta': beta,
        'Alpha': alpha,
        'Annualized Return': annualized_return,
        'Composite Score': composite_score
    }

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

def plot_interactive_trades(df, trades, initial_capital=1000000.0, risk_per_trade=0.02, rr_ratio=3.0, save_path='data/interactive_trades.html'):
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
                             
    # Calculate operational metrics
    metrics = calculate_metrics(df)

    # Prepare ratios table (separate view for ratios/metrics)
    ratios_keys = [
        'Annualized Return', 'Sharpe Ratio', 'Sortino Ratio', 'Calmar Ratio',
        'Max Drawdown', 'Beta', 'Alpha', 'Composite Score'
    ]
    ratios_values = []
    for k in ratios_keys:
        v = metrics.get(k)
        if k == 'Annualized Return' and np.isfinite(v):
            ratios_values.append(f"{v*100:.2f}%")
        elif k == 'Max Drawdown' and np.isfinite(v):
            ratios_values.append(f"-{v*100:.2f}%")
        elif k == 'Alpha' and np.isfinite(v):
            ratios_values.append(f"{v*100:.2f}%")
        elif isinstance(v, float) and np.isfinite(v):
            ratios_values.append(f"{v:.2f}")
        else:
            ratios_values.append("N/A")

    ratios_table = go.Table(
        header=dict(values=["Metric", "Value"], fill_color='lightgrey', align='left'),
        cells=dict(values=[ratios_keys, ratios_values], fill_color='white', align='left'),
        domain=dict(x=[0.01, 0.28], y=[0.62, 0.98])
    )

    # Prepare parameters table (separate from ratios)
    params_keys = ["Initial Capital", "Risk Per Trade", "RR Ratio"]
    params_values = [f"${initial_capital:,.2f}", f"{risk_per_trade*100:.2f}%", f"{rr_ratio:.2f}:1"]

    params_table = go.Table(
        header=dict(values=["Parameter", "Value"], fill_color='lightgrey', align='left'),
        cells=dict(values=[params_keys, params_values], fill_color='white', align='left'),
        domain=dict(x=[0.01, 0.28], y=[0.38, 0.60])
    )

    # Add the tables to the figure
    fig.add_trace(ratios_table)
    fig.add_trace(params_table)

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
            x=1.02,
            y=1.0,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.9)'
        ),
        margin=dict(r=260)
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
    plot_interactive_trades(backtested_df, trades, initial_capital=initial_capital, risk_per_trade=risk_per_trade, rr_ratio=rr_ratio, save_path='data/interactive_trades.html')
    
    # Optionally, save to CSV
    backtested_df.to_csv(csv_path, index=False)
    print(f"Full output saved to {csv_path}")
