import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import os
import json
from datetime import datetime, timezone

import roostoo

st.set_page_config(page_title="Roostoo Trading Bot Dashboard", layout="wide", page_icon="📈")

# -- Configuration --
DATA_FILE = "live_data.csv"
TRADE_LOG_FILE = "live_trades.csv"
DEFAULT_INIT_BALANCE = 50000.0  # Common starting balance for mock accounts

# -- Caching/Loading Functions --
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
            return df
        except Exception as e:
            print(f"Error loading data: {e}")
            pass
    return pd.DataFrame()

def load_trades():
    if os.path.exists(TRADE_LOG_FILE):
        try:
            df = pd.read_csv(TRADE_LOG_FILE)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
            return df
        except Exception as e:
            print(f"Error loading trades: {e}")
            pass
    return pd.DataFrame()

# Fetch external API data
@st.cache_data(ttl=10) # cache for 10 seconds to not hit rate limits constantly during refreshes
def get_roostoo_tickers():
    res = roostoo.get_ticker()
    return res.get('Data', {}) if res and res.get('Success') else {}

def get_roostoo_balance():
    res = roostoo.get_balance()
    # Support both 'Wallet' and 'SpotWallet' from the API
    return res.get('SpotWallet', res.get('Wallet', {})) if res and res.get('Success') else {}

def get_roostoo_pending_orders():
    res = roostoo.query_order(pending_only=True)
    return res.get('OrderMatched', []) if res and res.get('Success') else []

# -- Sidebar: Refresh Logic --
manual_refresh = st.button("🔄 Manual Refresh")
# -- Dashboard Header --
st.title("📈 Crypto Trading Bot Dashboard")

# Fetch Core Data
df_data = load_data()
df_trades = load_trades()
balances = get_roostoo_balance()
tickers = get_roostoo_tickers()
pending_orders = get_roostoo_pending_orders()

# -- 1. Account & Performance Overview & Portfolio Holdings --
st.header("1. Account Portfolio & Performance Overview")

# Calculate metrics
total_portfolio_value = 0.0
holdings = []

if balances:
    for coin, b in balances.items():
        useable = float(b.get('Free', 0))
        frozen = float(b.get('Lock', 0))
        total_amount = useable + frozen
        
        if total_amount > 0:
            price_in_usd = 1.0
            if coin != 'USD':
                pair = f"{coin}/USD"
                ticker_data = tickers.get(pair, {})
                price_in_usd = float(ticker_data.get('LastPrice', 0.0))
                # Fallback to local live_data close price for BTC if API fails
                if price_in_usd == 0.0 and coin == 'BTC' and not df_data.empty:
                    price_in_usd = df_data.iloc[-1]['close']
            
            value_usd = total_amount * price_in_usd
            total_portfolio_value += value_usd
            
            holdings.append({
                "Asset": coin,
                "Usable Amount": useable,
                "Frozen Amount": frozen,
                "Total Amount": total_amount,
                "Price (USD)": price_in_usd,
                "Value (USD)": value_usd
            })

col1, col2, col3, col4 = st.columns(4)
start_capital = DEFAULT_INIT_BALANCE
diff_to_init = total_portfolio_value - start_capital
pct_capital = (diff_to_init / start_capital) * 100 if start_capital > 0 else 0

delta_color = "normal" if diff_to_init >= 0 else "inverse"
col1.metric("Total Portfolio Value", f"${total_portfolio_value:,.2f}", f"${diff_to_init:+.2f} ({pct_capital:+.2f}%)", delta_color=delta_color)
col2.metric("Pending Orders", len(pending_orders))
col3.metric("Live Monitored Coins", len(tickers) if tickers else 0)
col4.metric("Total Executed Signals", len(df_trades))

st.subheader("Current Portfolio Holdings")
if holdings:
    holdings_df = pd.DataFrame(holdings)
    holdings_df = holdings_df.rename(columns={
        "Usable Amount": "Free",
        "Frozen Amount": "Locked",
        "Total Amount": "Total",
        "Value (USD)": "Est. USD Value",
        "Price (USD)": "Price"
    })
    holdings_df['Est. USD Value ($)'] = holdings_df['Est. USD Value'].copy()
    holdings_df['Est. USD Value'] = holdings_df['Est. USD Value'].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(holdings_df.drop(columns=['Est. USD Value ($)']).set_index('Asset'), use_container_width=True)
else:
    st.info("No balances found or unable to fetch from Roostoo API.")


# -- 2. Historical + Live Price Chart --
st.header("2. Historical & Live Price Chart (BTC/USD 5m)")

if not df_data.empty:
    fig = go.Figure(data=[go.Candlestick(
                x=df_data['timestamp'],
                open=df_data['open'],
                high=df_data['high'],
                low=df_data['low'],
                close=df_data['close'],
                name='Candles')])

    if not df_trades.empty:
        buys = df_trades[df_trades['action'] == 'BUY']
        sells = df_trades[df_trades['action'] == 'SELL']
        
        fig.add_trace(go.Scatter(
            x=buys['timestamp'],
            y=buys['price'],
            mode='markers',
            name='BUY Executed',
            marker=dict(color='green', size=15, symbol='triangle-up', line=dict(width=2, color='DarkSlateGrey'))
        ))
        
        fig.add_trace(go.Scatter(
            x=sells['timestamp'],
            y=sells['price'],
            mode='markers',
            name='SELL Executed',
            marker=dict(color='red', size=15, symbol='triangle-down', line=dict(width=2, color='DarkSlateGrey'))
        ))

    # Keep a good slice of history but don't overwhelm the browser context
    last_idx = len(df_data) - 1
    start_idx = max(0, last_idx - 500) # last ~2 days of 5m candles
    
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    # Autoscale to recent slice
    if last_idx > start_idx:
        fig.update_xaxes(range=[df_data.iloc[start_idx]['timestamp'], df_data.iloc[last_idx]['timestamp']])
        
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No price data collected yet. Start the bot and wait for the stream.")


# -- 3. Side-by-side Layout: Current Prices & Activity Log / Pending Orders --
st.header("3. Market & Activity")
col_curr, col_act = st.columns([1, 1])

with col_curr:
    st.subheader("Major Pair Current Prices")
    if tickers:
        # Show some major pairs
        top_pairs = ['BTC/USD', 'ETH/USD', 'BNB/USD', 'SOL/USD', 'XRP/USD']
        ticker_list = []
        for pair in top_pairs:
            t_data = tickers.get(pair)
            if t_data:
                change = float(t_data.get('Change', 0))
                ticker_list.append({
                    "Pair": pair,
                    "Last Price": float(t_data.get('LastPrice', 0)),
                    "24h ±%": change * 100
                })
        if ticker_list:
            st.dataframe(pd.DataFrame(ticker_list), use_container_width=True)
        else:
            st.write("Major pairs not found in ticker.")
    else:
        st.info("Unable to fetch live tickers.")

    st.subheader("Pending Orders")
    if pending_orders:
        parsed_pending = []
        for po in pending_orders:
            if po.get('Status') not in ('PENDING', 'PARTIALLY_FILLED'):
                continue
            ts_ms = int(po.get('CreateTimestamp', 0))
            dt_str = datetime.fromtimestamp(ts_ms/1000).strftime('%Y-%m-%d %H:%M:%S') if ts_ms > 0 else 'Unknown'
            parsed_pending.append({
                "Order ID": po.get('OrderID'),
                "Time": dt_str,
                "Pair": po.get('Pair'),
                "Side": po.get('Side'),
                "Type": po.get('Type'),
                "Price": float(po.get('Price', 0)),
                "Qty": float(po.get('Quantity', 0)),
                "Remaining": float(po.get('Quantity', 0)) - float(po.get('FilledQuantity', 0))
            })
            
        if parsed_pending:
            st.dataframe(pd.DataFrame(parsed_pending), use_container_width=True)
            
            # Add a quick cancel functionality for fun (optional, using selectbox)
            cancel_id = st.selectbox("Cancel Order ID", options=[p["Order ID"] for p in parsed_pending])
            if st.button("Cancel Selected Order"):
                res = roostoo.cancel_order(order_id=cancel_id)
                if res and res.get('Success'):
                    st.success(f"Order {cancel_id} cancelled.")
                    time.sleep(1)
                    st.rerun()
                else:
                    err_msg = res.get("ErrMsg", "API Error") if res else "No response"
                    st.error(f"Failed to cancel order: {err_msg}")
        else:
            st.info("No active pending orders.")
    else:
        st.info("No pending orders.")


with col_act:
    st.subheader("Recent Filled Executions (Local Bot Log)")
    if not df_trades.empty:
        st.dataframe(df_trades.sort_values(by="timestamp", ascending=False).head(15), use_container_width=True)
    else:
        st.write("No bot trades executed yet.")


# -- 4. Manual Order Entry --
st.markdown("---")
st.header("⚠️ Manual Order Entry")

with st.form("manual_order_form"):
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    with col_m1:
        pair_input = st.text_input("Symbol Pair", value="BTC/USD")
    with col_m2:
        side_input = st.selectbox("Action", ["BUY", "SELL"])
    with col_m3:
        type_input = st.selectbox("Order Type", ["MARKET", "LIMIT"])
    with col_m4:
        qty_input = st.number_input("Quantity", min_value=0.0001, value=0.01, step=0.01, format="%f")
    with col_m5:
        price_input = st.number_input("Limit Price (only for LIMIT)", min_value=0.0, value=90000.0, step=100.0)

    submitted = st.form_submit_button("🚀 Submit Order via Roostoo API")

# Moved outside the form to ensure it only executes during the form submission rerun
if submitted:
    if type_input == "LIMIT" and price_input <= 0:
        st.error("Please enter a valid price for LIMIT orders.")
    else:
        p = price_input if type_input == "LIMIT" else None
        out = roostoo.place_order(pair_or_coin=pair_input, side=side_input, quantity=qty_input, price=p, order_type=type_input)
        
        if out and out.get("Success"):
            st.success(f"Successfully placed {side_input} {type_input} order for {qty_input} {pair_input}!")
            
            # If market or limit order, log it directly simulating bot execution
            # For market orders, we simulate the execution price from last ticker. For limits, use the input price.
            exec_price = tickers.get(pair_input, {}).get("LastPrice", 0) if type_input == "MARKET" else price_input
            trade_df = pd.DataFrame([{
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'symbol': pair_input,
                'action': side_input,
                'price': float(exec_price),
                'quantity': qty_input,
                'source': f'Manual ({type_input})',
                'response': json.dumps(out)
            }])
            trade_df.to_csv(TRADE_LOG_FILE, mode='a', header=not os.path.exists(TRADE_LOG_FILE), index=False)

            # Refresh logic here immediately updates the tables
            time.sleep(1)
            st.rerun()
        else:
            err_msg = out.get("ErrMsg", "Unknown Error") if out else "API Error"
            st.error(f"Failed to place order: {err_msg}")
