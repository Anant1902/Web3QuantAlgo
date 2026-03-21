"""
Trading engine for executing strategy signals via Roostoo API.
Handles order placement, tracking, and performance analysis.
"""
import pandas as pd
from typing import List, Dict, Optional
from market_data_loader import MarketDataLoader


class TradingEngine:
    """Execute trading signals using Roostoo API."""
    
    def __init__(self, loader: MarketDataLoader, initial_capital: float = 1000000.0):
        """
        Initialize trading engine.
        
        Args:
            loader: MarketDataLoader instance with API credentials
            initial_capital: Starting capital in USD
        """
        self.loader = loader
        self.initial_capital = initial_capital
        self.trades = []
        self.orders = []
        self.starting_balance = None
        self.current_balance = None
        
    def check_balance(self) -> Optional[Dict]:
        """Check account balance on Roostoo."""
        print("\n💰 Checking account balance...")
        balance_data = self.loader.get_balance()
        
        if balance_data and balance_data.get("Success"):
            wallet = balance_data.get("Wallet") or balance_data.get("SpotWallet", {})
            usd_balance = wallet.get("USD", {})
            
            print(f"   USD Balance:")
            print(f"   - Free: ${usd_balance.get('Free', 0):.2f}")
            print(f"   - Locked: ${usd_balance.get('Lock', 0):.2f}")
            
            self.starting_balance = usd_balance.get('Free', 0)
            self.current_balance = usd_balance.get('Free', 0)
            
            return balance_data
        else:
            print(f"   ✗ Failed to get balance: {balance_data.get('ErrMsg', 'Unknown error')}")
            return None
    
    def place_order(self, pair: str, side: str, quantity: float, order_type: str = "MARKET", 
                    price: Optional[float] = None) -> Optional[Dict]:
        """
        Place order on Roostoo exchange.
        
        Args:
            pair: Trading pair (e.g., "BTC/USD")
            side: "BUY" or "SELL"
            quantity: Amount to trade
            order_type: "MARKET" or "LIMIT"
            price: Price for LIMIT orders
            
        Returns:
            Order response from API
        """
        if order_type == "LIMIT" and price is None:
            print(f"   ✗ LIMIT order requires price")
            return None
        
        payload = {
            'pair': pair,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': str(quantity)
        }
        
        if order_type == "LIMIT":
            payload['price'] = str(price)
        
        url = f"{self.loader.base_url}/v3/place_order"
        headers, _, total_params = self.loader._get_signed_headers(payload)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        try:
            import requests
            res = requests.post(url, headers=headers, data=total_params)
            res.raise_for_status()
            order_response = res.json()
            
            if order_response.get("Success"):
                self.orders.append(order_response)
                return order_response
            else:
                print(f"   ✗ Order failed: {order_response.get('ErrMsg')}")
                return None
                
        except Exception as e:
            print(f"   ✗ Error placing order: {e}")
            return None
    
    def query_order(self, order_id: Optional[int] = None, pair: Optional[str] = None) -> Optional[Dict]:
        """Query order status."""
        payload = {}
        if order_id:
            payload['order_id'] = str(order_id)
        elif pair:
            payload['pair'] = pair
        
        url = f"{self.loader.base_url}/v3/query_order"
        headers, _, total_params = self.loader._get_signed_headers(payload)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        try:
            import requests
            res = requests.post(url, headers=headers, data=total_params)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"   ✗ Error querying order: {e}")
            return None
    
    def cancel_order(self, order_id: Optional[int] = None, pair: Optional[str] = None) -> Optional[Dict]:
        """Cancel pending order."""
        payload = {}
        if order_id:
            payload['order_id'] = str(order_id)
        elif pair:
            payload['pair'] = pair
        
        url = f"{self.loader.base_url}/v3/cancel_order"
        headers, _, total_params = self.loader._get_signed_headers(payload)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        try:
            import requests
            res = requests.post(url, headers=headers, data=total_params)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"   ✗ Error canceling order: {e}")
            return None
    
    def execute_signals(self, result_df: pd.DataFrame, pair: str = "BTC/USD", 
                       quantity_per_trade: float = 0.01) -> pd.DataFrame:
        """
        Execute buy/sell signals from strategy.
        
        Args:
            result_df: DataFrame with 'signal' column (1=BUY, -1=SELL, 0=HOLD)
            pair: Trading pair (e.g., "BTC/USD")
            quantity_per_trade: Amount of BTC to trade per signal
            
        Returns:
            DataFrame with execution results
        """
        print("\n" + "="*80)
        print("🎯 EXECUTING STRATEGY SIGNALS ON ROOSTOO API")
        print("="*80)
        
        result_df = result_df.copy()
        result_df['order_id'] = None
        result_df['order_status'] = None
        result_df['filled_price'] = None
        result_df['filled_quantity'] = None
        result_df['execution_cost'] = None
        
        buy_trades = []
        sell_trades = []
        
        for idx, row in result_df.iterrows():
            signal = row['signal']
            current_price = row['close']
            
            if signal == 1:  # BUY signal
                print(f"\n📈 BUY Signal at {idx}")
                print(f"   Price: ${current_price:.2f}")
                print(f"   Quantity: {quantity_per_trade} BTC")
                
                order = self.place_order(pair, "BUY", quantity_per_trade, "MARKET")
                
                if order and order.get("Success"):
                    order_detail = order.get("OrderDetail", {})
                    result_df.loc[idx, 'order_id'] = order_detail.get('OrderID')
                    result_df.loc[idx, 'order_status'] = order_detail.get('Status')
                    result_df.loc[idx, 'filled_price'] = order_detail.get('FilledAverPrice')
                    result_df.loc[idx, 'filled_quantity'] = order_detail.get('FilledQuantity')
                    result_df.loc[idx, 'execution_cost'] = order_detail.get('UnitChange', 0)
                    
                    print(f"   ✓ Order #{order_detail.get('OrderID')}: {order_detail.get('Status')}")
                    print(f"   Filled @ ${order_detail.get('FilledAverPrice'):.2f}")
                    print(f"   Cost: ${order_detail.get('UnitChange', 0):.2f}")
                    
                    buy_trades.append(order_detail)
                else:
                    print(f"   ✗ Order failed")
            
            elif signal == -1:  # SELL signal
                print(f"\n📉 SELL Signal at {idx}")
                print(f"   Price: ${current_price:.2f}")
                print(f"   Quantity: {quantity_per_trade} BTC")
                
                order = self.place_order(pair, "SELL", quantity_per_trade, "MARKET")
                
                if order and order.get("Success"):
                    order_detail = order.get("OrderDetail", {})
                    result_df.loc[idx, 'order_id'] = order_detail.get('OrderID')
                    result_df.loc[idx, 'order_status'] = order_detail.get('Status')
                    result_df.loc[idx, 'filled_price'] = order_detail.get('FilledAverPrice')
                    result_df.loc[idx, 'filled_quantity'] = order_detail.get('FilledQuantity')
                    result_df.loc[idx, 'execution_cost'] = order_detail.get('UnitChange', 0)
                    
                    print(f"   ✓ Order #{order_detail.get('OrderID')}: {order_detail.get('Status')}")
                    print(f"   Filled @ ${order_detail.get('FilledAverPrice'):.2f}")
                    print(f"   Revenue: ${order_detail.get('UnitChange', 0):.2f}")
                    
                    sell_trades.append(order_detail)
                else:
                    print(f"   ✗ Order failed")
        
        # Summary
        print("\n" + "="*80)
        print("📊 EXECUTION SUMMARY")
        print("="*80)
        print(f"Total signals: {(result_df['signal'] != 0).sum()}")
        print(f"Buy orders executed: {len(buy_trades)}")
        print(f"Sell orders executed: {len(sell_trades)}")
        
        if buy_trades:
            total_buy_cost = sum(t.get('UnitChange', 0) for t in buy_trades)
            print(f"Total BUY cost: ${total_buy_cost:.2f}")
        
        if sell_trades:
            total_sell_revenue = sum(t.get('UnitChange', 0) for t in sell_trades)
            print(f"Total SELL revenue: ${total_sell_revenue:.2f}")
        
        # Check final balance
        final_balance_data = self.check_balance()
        
        self.trades = buy_trades + sell_trades
        
        return result_df
    
    def get_trading_statistics(self) -> Dict:
        """Generate trading statistics."""
        stats = {
            'total_trades': len(self.trades),
            'buy_trades': sum(1 for t in self.trades if t.get('Side') == 'BUY'),
            'sell_trades': sum(1 for t in self.trades if t.get('Side') == 'SELL'),
            'total_commission': sum(t.get('CommissionChargeValue', 0) for t in self.trades),
            'starting_balance': self.starting_balance,
            'current_balance': self.current_balance,
        }
        
        if self.starting_balance:
            stats['balance_change'] = self.current_balance - self.starting_balance
            stats['balance_change_pct'] = (stats['balance_change'] / self.starting_balance * 100)
        
        return stats
