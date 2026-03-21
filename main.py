import os
import sys
import pandas as pd
from dotenv import load_dotenv
from market_data_loader import MarketDataLoader
from trading_engine import TradingEngine
from strategy import candlestick_reversal_strategy
from performance_analysis import analyze_and_plot

# Make output unbuffered
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except:
        pass

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

def main():
    print("Hello from web3quantalgo!")
    print(f"Python: {sys.version}")
    print(f"PID: {os.getpid()}\n")
    
    # Initialize the data loader
    loader = MarketDataLoader("data", use_api=False)
    
    # Choose data source
    use_websocket = os.getenv("USE_WEBSOCKET", "false").lower() == "true"
    use_api = os.getenv("USE_API", "false").lower() == "true"
    
    try:
        market_data = None
        data_source = "CSV (default)"
        live_trading_engine = None
        
        # Step 1: Get market data (from WebSocket or CSV)
        if use_websocket:
            print("\n" + "="*80)
            print("📡 LIVE TRADING MODE: WEBSOCKET + MASTER DATA")
            print("="*80)
            
            # Load master CSV
            print("Loading master CSV data...")
            market_data = loader.load_csv("BTCUSD-5m-master.csv")
            print(f"✓ Loaded {len(market_data)} candles from master CSV")
            initial_rows = len(market_data)
            
            # Collect WebSocket data
            num_candles = int(os.getenv("NUM_CANDLES", "2"))
            timeout_seconds = int(os.getenv("WS_TIMEOUT", "300"))
            
            print(f"\n📡 Collecting NEW candles from Binance WebSocket...")
            print(f"   Target: {num_candles} NEW candles")
            print(f"   Timeout: {timeout_seconds} seconds\n")
            
            ws_data = loader.get_klines_websocket(
                symbol="btcusdt",
                interval="5m",
                num_candles=num_candles,
                timeout=timeout_seconds
            )
            
            print(f"\n✓ WebSocket collected {len(ws_data)} live candles")
            
            # Append WebSocket data to master CSV
            print("\n📝 Appending WebSocket data to master CSV...")
            market_data_combined = pd.concat([market_data, ws_data])
            market_data_combined = market_data_combined[~market_data_combined.index.duplicated(keep='last')]
            market_data_combined = market_data_combined.sort_index()
            
            # Save updated master CSV
            master_csv_path = "data/BTCUSD-5m-master.csv"
            market_data_combined.to_csv(master_csv_path)
            print(f"✓ Updated master CSV: {initial_rows} → {len(market_data_combined)} candles")
            print(f"💾 Saved to: {master_csv_path}\n")
            
            print("Latest candles:")
            print(market_data_combined[['open', 'high', 'low', 'close', 'volume']].tail(5))
            
            market_data = market_data_combined
            data_source = f"Master CSV ({initial_rows}) + WebSocket ({len(ws_data)} live)" 
        else:
            # Load from master CSV (default)
            print("\n" + "="*80)
            print("📂 BACKTEST MODE: LOADING FROM MASTER CSV")
            print("="*80)
            market_data = loader.load_csv("BTCUSD-5m-master.csv")
            data_source = "Master CSV (historical)"
        
        # Step 2: Initialize trading engine if using API
        if use_api:
            print("\n" + "="*80)
            print("💰 ROOSTOO API LIVE TRADING")
            print("="*80)
            
            # Initialize trading engine
            live_trading_engine = TradingEngine(loader, initial_capital=1000000.0)
            
            # Check initial balance
            live_trading_engine.check_balance()
            
            # Get current ticker data
            ticker_data = loader.get_ticker("BTC/USD")
            if ticker_data and ticker_data.get("Success"):
                print("\n📊 Market Ticker (BTC/USD):")
                ticker = ticker_data["Data"]["BTC/USD"]
                print(f"   Last Price: ${ticker.get('LastPrice', 0):.2f}")
                print(f"   24h Change: {ticker.get('Change', 0)*100:.2f}%")
                print(f"   24h Volume: {ticker.get('CoinTradeValue', 0):.2f} BTC")
            
            # Update data source
            data_source += " → LIVE TRADING"
        
        print("\n" + "="*80)
        print("🎯 RUNNING CANDLESTICK REVERSAL STRATEGY")
        print("="*80)
        print(f"Data source: {data_source}")
        print(f"Candles: {len(market_data)}")
        print(f"Date range: {market_data.index[0]} to {market_data.index[-1]}\n")
        
        result_df = candlestick_reversal_strategy(market_data)
        
        # Count signals
        buy_signals = (result_df['signal'] == 1).sum()
        sell_signals = (result_df['signal'] == -1).sum()
        total_signals = buy_signals + sell_signals
        
        print(f"\nSignals generated:")
        print(f"  Buy signals:  {buy_signals}")
        print(f"  Sell signals: {sell_signals}")
        print(f"  Total:        {total_signals}\n")
        
        if total_signals == 0:
            print("⚠️  No trading signals generated (data may be insufficient)")
            print("   Try collecting more candles: NUM_CANDLES=50")
        
        # Execute trades via Roostoo API if using live trading
        trading_stats = None
        if use_api and 'live_trading_engine' in locals() and live_trading_engine is not None:
            result_df = live_trading_engine.execute_signals(result_df, pair="BTC/USD", quantity_per_trade=0.01)
            trading_stats = live_trading_engine.get_trading_statistics()
            
            # Save execution results
            result_df.to_csv("data/live_trading_results.csv")
            print("\n💾 Saved live trading results to: data/live_trading_results.csv")
        
        # Run the performance analysis and plot
        print("\n" + "="*80)
        print("📊 PERFORMANCE ANALYSIS")
        print("="*80 + "\n")
        
        analyze_and_plot(result_df, initial_capital=1000000.0, risk_per_trade=0.01, rr_ratio=4.0)
        
        # Print trading statistics
        if trading_stats:
            print("\n" + "="*80)
            print("🏦 LIVE TRADING STATISTICS")
            print("="*80)
            print(f"Total trades executed: {trading_stats['total_trades']}")
            print(f"  Buy orders:  {trading_stats['buy_trades']}")
            print(f"  Sell orders: {trading_stats['sell_trades']}")
            print(f"Total commissions: ${trading_stats['total_commission']:.2f}")
            
            if trading_stats.get('starting_balance'):
                print(f"\nBalance:")
                print(f"  Starting: ${trading_stats['starting_balance']:.2f}")
                print(f"  Current:  ${trading_stats['current_balance']:.2f}")
                print(f"  Change:   ${trading_stats.get('balance_change', 0):.2f}")
                print(f"  Change %: {trading_stats.get('balance_change_pct', 0):.2f}%")
            print("="*80)
        
        print("\n" + "="*80)
        print("✅ COMPLETE")
        print("="*80)
        print("📁 Reports saved:")
        print("   • data/interactive_trades.html (open in browser)")
        print("   • data/strategy_output.csv")
        if use_websocket:
            print("   • data/websocket_candles.csv (WebSocket data)")
        if use_api:
            print("   • data/live_trading_results.csv (execution results)")
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
