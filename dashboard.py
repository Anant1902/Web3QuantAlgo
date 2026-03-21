import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import os

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

st.title("📈 Crypto Trading Bot Dashboard")

data_file = "live_data.csv"
trade_file = "live_trades.csv"

def load_data():
    if os.path.exists(data_file):
        try:
            df = pd.read_csv(data_file)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception:
            pass
    return pd.DataFrame()

def load_trades():
    if os.path.exists(trade_file):
        try:
            df = pd.read_csv(trade_file)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception:
            pass
    return pd.DataFrame()

# Refresh button
st.button("Refresh Data")

# Read data
df_data = load_data()
df_trades = load_trades()

# Metrics
if not df_data.empty:
    latest_close = df_data.iloc[-1]['close']
    st.metric("Latest Close (BTC/USD)", f"${latest_close:.2f}")

    # Plot Candlesticks
    st.subheader("Price Chart History")
    fig = go.Figure(data=[go.Candlestick(x=df_data['timestamp'],
                open=df_data['open'],
                high=df_data['high'],
                low=df_data['low'],
                close=df_data['close'])])

    # If we have trades, add them onto the chart
    if not df_trades.empty:
        buys = df_trades[df_trades['action'] == 'BUY']
        sells = df_trades[df_trades['action'] == 'SELL']
        
        fig.add_trace(go.Scatter(
            x=buys['timestamp'],
            y=buys['price'],
            mode='markers',
            name='BUY',
            marker=dict(color='green', size=12, symbol='triangle-up')
        ))
        
        fig.add_trace(go.Scatter(
            x=sells['timestamp'],
            y=sells['price'],
            mode='markers',
            name='SELL',
            marker=dict(color='red', size=12, symbol='triangle-down')
        ))

    fig.update_layout(xaxis_rangeslider_visible=False, height=600)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No price data collected yet. Start the bot and wait for a 5-minute candle to close.")

st.subheader("Recent Trades")
if not df_trades.empty:
    st.dataframe(df_trades.sort_values(by="timestamp", ascending=False).head(10))
else:
    st.write("No trades executed yet.")
