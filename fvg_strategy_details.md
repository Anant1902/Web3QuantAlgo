# Fair Value Gap (FVG) Strategy Logic

This strategy logic is designed to be easily translatable into Pine Script for TradingView. It operates as a strict "Gap Fill" reversal strategy.

## 1. Core Definitions

A **Bearish Fair Value Gap (FVG)** is defined over three consecutive candles (let's call them Candle 1, 2, and 3, where Candle 3 is the most recent closed candle).
- It occurs when there is a sudden downward impulse.
- The **Top** of the gap is Candle 1's Low.
- The **Bottom** of the gap is Candle 3's High.
- An active gap must have: `Candle 1 Low > Candle 3 High`.
- **Minimum Gap Size:** The gap distance `(Top - Bottom) / Top` must be strictly greater than `0.1%` (`0.001`).

## 2. Strategy State Management

While scanning through candles:
- The script must remember if there is a currently `active_fvg`.
- It must also track the `lowest_since_fvg`, which is continuously updated with `current_low` while the price remains below the `active_fvg` gap.
- An `active_fvg` is completely **invalidated** if the `current_high >= FVG Top` (the gap has been 100% filled before we could get a proper entry). At this point, stop looking for entries on this specific gap.

## 3. Entry Conditions

**Long Entry:**
When there is an `active_fvg` that has NOT been invalidated (the gap isn't completely filled), watch for the price to rise and **touch the bottom of the gap**.
Condition: `current_high >= FVG Bottom`

Once this condition is met, execute a Long entry immediately (or at candle close, depending on your preferred execution model). Only one entry is allowed per identified FVG.

## 4. Exit Conditions (Stop Loss & Take Profit)

The strategy uses dynamic, structural Stop Loss and Take Profit levels that are determined at the exact moment of Entry.

**Take Profit (Target):**
- Set at the **Top** of the FVG structure.
- Logic: `Take Profit = FVG Top`

**Stop Loss:**
- Placed just below the absolute furthest point the price reached while dipping under the gap before the reversal started.
- Logic: `Stop Loss = lowest_since_fvg * 0.9995` (0.05% below the structural swing low).

## 5. Position Sizing Rules

- Maximum risk per trade: 5% of Portfolio Equity.
- Leverage constraint: Position notional value cannot exceed 1x (Total Portfolio Equity / Entry Price). If the stop loss requires buying more than the cash equivalent to meet the 5% risk threshold, scale the position down to 1x leverage. 

*(Note: In Pine Script, position sizing can be configured directly in the `strategy()` declaration using `default_qty_type = strategy.percent_of_equity` and risk management filters, or manually calculated down via `qty` based on the SL distance).*
