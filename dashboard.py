import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
from market_data_loader import MarketDataLoader
from dotenv import load_dotenv

load_dotenv()

# Set page config
st.set_page_config(page_title="Web3QuantAlgo Dashboard", layout="wide", page_icon="📈")

# Auto-refresh mechanism (refreshes every 10 seconds)
st.button("Manual Refresh")

# Helper to read data
@st.cache_data(ttl=5)
def load_data():
    try:
        # Load the latest strategy output containing prices, signals, and capital
        df = pd.read_csv("data/strategy_output.csv")
        
        # Ensure we have date formatting
        if 'close_time' in df.columns:
            df['close_time'] = pd.to_datetime(df['close_time'])
            df = df.sort_values(by="close_time")
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def load_live_trades():
    try:
        df = pd.read_csv("data/live_trading_results.csv")
        if 'close_time' in df.columns:
            df['close_time'] = pd.to_datetime(df['close_time'])
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=5)
def get_live_holdings():
    """Fetch all wallet holdings from the API."""
    try:
        loader = MarketDataLoader(data_path="", use_api=True)
        balance_data = loader.get_balance()
        if balance_data and balance_data.get("Success"):
            wallet = balance_data.get("Wallet") or balance_data.get("SpotWallet", {})
            return wallet
    except Exception as e:
        print(f"Error fetching holdings from API: {e}")
    return None

@st.cache_data(ttl=5)
def get_live_prices():
    """Fetch current market prices from the API."""
    try:
        import requests
        import time
        timestamp = str(int(time.time() * 1000))
        res = requests.get("https://mock-api.roostoo.com/v3/ticker", params={'timestamp': timestamp})
        data = res.json()
        if data and data.get("Success"):
            return data.get("Data", {})
    except Exception as e:
        print(f"Error fetching prices from API: {e}")
    return {}

@st.cache_data(ttl=5)
def get_live_balance():
    wallet = get_live_holdings()
    if wallet:
        usd_balance = wallet.get("USD", {})
        free = float(usd_balance.get('Free', 0))
        locked = float(usd_balance.get('Lock', 0))
        return free + locked
    return None

def get_pending_orders():
    """Fetch pending orders from the Roostoo API."""
    try:
        loader = MarketDataLoader(data_path="", use_api=True)
        # Note: the doc says "pending_only can send to ask pending order(s) only"
        response = loader.query_order(pending_only=True)
        if response:
            if response.get("Success"):
                return response.get("OrderMatched", [])
            else:
                return []
    except Exception as e:
        print(f"Error fetching pending orders: {e}")
    return []

st.title("🤖 Web3QuantAlgo Live Trading Dashboard")

df = load_data()

if df.empty:
    st.warning("No trading data found. Make sure the bot is running and generating 'data/strategy_output.csv'.")
else:
    # ------------------ TOP KPIs ------------------
    st.header("Account & Performance Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    current_price = df['close'].iloc[-1]
    
    # Capital / Account Balance
    live_balance = get_live_balance()
    if live_balance is not None:
        current_capital = live_balance
        start_capital = df['capital'].iloc[0] if 'capital' in df.columns and len(df) > 0 else current_capital
    else:
        current_capital = df['capital'].iloc[-1] if 'capital' in df.columns else 0.0
        start_capital = df['capital'].iloc[0] if 'capital' in df.columns and len(df) > 0 else current_capital
        
    profit_capital = current_capital - start_capital
    pct_capital = (profit_capital / start_capital) * 100 if start_capital > 0 else 0
    
    col1_placeholder = col1.empty()
    col1_placeholder.metric("Account Balance (USD Only)", f"${current_capital:,.2f}", f"{profit_capital:+,.2f} ({pct_capital:+.2f}%)")
    col2.metric("Current Asset Price", f"${current_price:,.2f}")
    
    # Trade Count
    num_trades = len(df[df['signal'] != 0]) if 'signal' in df.columns else 0
    col3.metric("Total Executed Signals", num_trades)
    
    # ------------------ Portfolio Holdings ------------------
    st.subheader("Current Portfolio Holdings")
    wallet = get_live_holdings()
    prices = get_live_prices()
    if wallet:
        # Convert dictionary to DataFrame for nice Display
        holdings_list = []
        total_usd_value = 0.0
        
        for asset, data in wallet.items():
            free = float(data.get('Free', 0))
            locked = float(data.get('Lock', 0))
            total = free + locked
            
            if total > 0:
                asset_usd_value = 0.0
                if asset == "USD":
                    asset_usd_value = total
                else:
                    pair = f"{asset}/USD"
                    if pair in prices:
                        price = float(prices[pair].get("LastPrice", 0))
                        asset_usd_value = total * price
                        
                total_usd_value += asset_usd_value
                
                holdings_list.append({
                    "Asset": asset,
                    "Free": free,
                    "Locked": locked,
                    "Total": total,
                    "Est. USD Value": asset_usd_value
                })
                
        if holdings_list:
            holdings_df = pd.DataFrame(holdings_list)
            # Format the USD Value column
            holdings_df['Est. USD Value ($)'] = holdings_df['Est. USD Value'].copy()
            holdings_df['Est. USD Value'] = holdings_df['Est. USD Value'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(holdings_df.drop(columns=['Est. USD Value ($)']).set_index('Asset'), use_container_width=True)
            st.markdown(f"**Total Portfolio Value (incl. USD):** ${total_usd_value:,.2f}")
            
            # Update the account balance widget to use the total portfolio value instead of just USD
            col1_placeholder.metric("Total Portfolio Value", f"${total_usd_value:,.2f}", f"{(total_usd_value - start_capital):+,.2f} ({((total_usd_value - start_capital) / start_capital) * 100 if start_capital > 0 else 0:+.2f}%)")
        else:
            st.info("No balances found in your wallet.")
    else:
        st.warning("Could not fetch live wallet holdings from the API.")

    # ------------------ Pending Orders ------------------
    st.subheader("Pending Orders")
    if st.button("Query Pending Orders"):
        with st.spinner("Fetching from API..."):
            pending_orders = get_pending_orders()
            if pending_orders:
                orders_df = pd.DataFrame(pending_orders)
                # Filter down to useful display columns if they exist
                desired_cols = ["OrderId", "Pair", "Side", "Type", "Price", "Amount", "Timestamp"]
                display_cols = [c for c in desired_cols if c in orders_df.columns]
                
                # Format Timestamp if available
                if "Timestamp" in orders_df.columns:
                    orders_df["Timestamp"] = pd.to_datetime(orders_df["Timestamp"], unit='ms')
                
                if len(display_cols) > 0:
                    st.dataframe(orders_df[display_cols].set_index("OrderId"), use_container_width=True)
                else:
                    st.dataframe(orders_df, use_container_width=True)
            else:
                st.info("No pending orders matched.")

    # ------------------ Candlestick Chart ------------------
    st.subheader("Price & Signal Chart (Historical + Live)")
    
    fig = go.Figure()
    
    # Add Candlesticks
    fig.add_trace(go.Candlestick(
        x=df['close_time'] if 'close_time' in df.columns else df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ))
    
    # Add Buy/Sell Signals
    if 'signal' in df.columns:
        buys = df[df['signal'] == 1]
        sells = df[df['signal'] == -1]
        
        fig.add_trace(go.Scatter(
            x=buys['close_time'] if 'close_time' in df.columns else buys.index,
            y=buys['low'] * 0.999,
            mode='markers',
            marker=dict(symbol='triangle-up', color='green', size=12),
            name='Buy Signal'
        ))
        
        fig.add_trace(go.Scatter(
            x=sells['close_time'] if 'close_time' in df.columns else sells.index,
            y=sells['high'] * 1.001,
            mode='markers',
            marker=dict(symbol='triangle-down', color='red', size=12),
            name='Sell Signal'
        ))
    
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=0, r=0, t=30, b=0),
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # ------------------ Recent Trade History ------------------
    st.subheader("Recent Activity Log")
    col_log1, col_log2 = st.columns(2)
    
    with col_log1:
        st.markdown("**All Trade Signals**")
        if 'signal' in df.columns:
            signals_df = df[df['signal'] != 0].copy()
            if not signals_df.empty:
                display_cols = ['close_time', 'close', 'signal', 'capital']
                display_cols = [c for c in display_cols if c in signals_df.columns]
                
                signals_df['signal'] = signals_df['signal'].map({1: 'BUY', -1: 'SELL'})
                st.dataframe(signals_df[display_cols].sort_index(ascending=False).head(15), use_container_width=True)
            else:
                st.info("No trading signals generated yet.")
                
    with col_log2:
        st.markdown("**Live Filled Trades (from live_trading_results.csv)**")
        live_df = load_live_trades()
        if not live_df.empty:
            if 'signal' in live_df.columns:
                live_df = live_df[live_df['signal'] != 0]
            display_cols = ['close_time', 'filled_price', 'filled_quantity', 'execution_cost']
            display_cols = [c for c in display_cols if c in live_df.columns]
            if not live_df.empty:
                st.dataframe(live_df[display_cols].sort_index(ascending=False).head(15), use_container_width=True)
            else:
                st.info("No live trade executions found.")
        else:
            st.info("live_trading_results.csv is empty or missing.")

st.info("Tip: Click 'Manual Refresh' to update the latest data points from the bot if auto-refresh is paused.")
