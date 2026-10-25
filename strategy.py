import os
import math
import datetime
import pandas as pd
import numpy as np

def norm_cdf(x: float) -> float:
    """Exact Normal CDF using standard library math.erf (zero dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
from config import (
    SL_MIN_PTS, SL_MAX_PTS, SL_BUFFER_PTS, 
    SESSION_START_UTC, SESSION_END_UTC, 
    TARGET_DELTA, REVERSAL_EXPIRY_MODE
)

def calculate_swing_sl(df_15m: pd.DataFrame, entry_signal: str, entry_price: float, buffer: float = SL_BUFFER_PTS):
    """
    Price Action Swing High/Low Stop Loss:
    - BUY_CALL: SL placed below the Swing Low of last 4 candles (1 hour) minus 30 pts buffer.
    - BUY_PUT:  SL placed above the Swing High of last 4 candles (1 hour) plus 30 pts buffer.
    - Capped between 150 pts min (avoid noise) and 500 pts max (risk control).
    """
    last_4_candles = df_15m.iloc[-4:]
    if entry_signal == 'BUY_CALL':
        recent_low = float(last_4_candles['low'].min())
        sl_dist = entry_price - (recent_low - buffer)
    else:
        recent_high = float(last_4_candles['high'].max())
        sl_dist = (recent_high + buffer) - entry_price
        
    sl_dist = max(SL_MIN_PTS, min(SL_MAX_PTS, sl_dist))
    return round(sl_dist, 2)

def evaluate_market_setup(df_1h: pd.DataFrame, df_15m: pd.DataFrame, levels: dict, current_utc_hour: int):
    """
    Evaluates independent triggers at 15m candle close:
    1. Trading Hours: London + NY (08:00 to 21:00 UTC = 13:30 to 02:30 IST)
    2. REVERSAL (SMC Liquidity Sweep):
       - Bullish Sweep of Asian Low / PDL + Green Reclaim + Close > 15m EMA20 + 1H Trend == 1
       - Bearish Sweep of Asian High / PDH + Red Rejection + Close < 15m EMA20 + 1H Trend == -1
    3. BREAKOUT (Trend-Aligned Level Breakout):
       - 1H Bullish + 15m Green close above Resistance + Close > 15m EMA20
       - 1H Bearish + 15m Red close below Support + Close < 15m EMA20
    Returns: (signal, setup_type) or (None, None)
    """
    # 1. Trading Session Filter (08:00 to 21:00 UTC)
    if current_utc_hour < SESSION_START_UTC or current_utc_hour > SESSION_END_UTC:
        return None, None

    if len(df_1h) < 25 or len(df_15m) < 35:
        return None, None

    last_15m = df_15m.iloc[-1]
    prev_15m = df_15m.iloc[-2]
    latest_1h = df_1h.iloc[-1]

    # Higher Timeframe Trend Bias (1H Close vs 1H 20-EMA)
    trend_1h = 1 if latest_1h['close'] > latest_1h['ema20'] else -1

    # SMC Reference Levels
    al = levels.get('asian_low')
    ah = levels.get('asian_high')
    pdl = levels.get('pdl')
    pdh = levels.get('pdh')

    if al is None or ah is None or pdl is None or pdh is None:
        return None, None

    support = min([al, pdl])
    resistance = max([ah, pdh])

    is_green = last_15m['close'] > last_15m['open']
    is_red   = last_15m['close'] < last_15m['open']
    above_ema15 = last_15m['close'] > last_15m['ema20']
    below_ema15 = last_15m['close'] < last_15m['ema20']

    # 1. REVERSAL CHECK (PRIORITY 1: High Win Rate Liquidity Sweep)
    swept_support = (prev_15m['low'] < support or last_15m['low'] < support) and last_15m['close'] > support and is_green and above_ema15
    swept_resistance = (prev_15m['high'] > resistance or last_15m['high'] > resistance) and last_15m['close'] < resistance and is_red and below_ema15

    if trend_1h == 1 and swept_support:
        return 'BUY_CALL', 'REVERSAL'
    if trend_1h == -1 and swept_resistance:
        return 'BUY_PUT', 'REVERSAL'

    # 2. BREAKOUT CHECK (PRIORITY 2: Trend Continuation Breakout)
    bo_call = (trend_1h == 1) and (last_15m['close'] > resistance) and (prev_15m['close'] <= resistance) and is_green and above_ema15
    bo_put  = (trend_1h == -1) and (last_15m['close'] < support) and (prev_15m['close'] >= support) and is_red and below_ema15

    if bo_call:
        return 'BUY_CALL', 'BREAKOUT'
    if bo_put:
        return 'BUY_PUT', 'BREAKOUT'

    return None, None

def calculate_option_delta(spot: float, strike: float, dte_days: float, is_call: bool, iv: float = 0.48) -> float:
    """Calculates Black-Scholes Delta for a given strike and DTE."""
    T = max(dte_days, 0.005) / 365.0
    d1 = (np.log(spot / strike) + 0.5 * iv**2 * T) / (iv * np.sqrt(T))
    return float(norm_cdf(d1)) if is_call else float(norm_cdf(d1) - 1.0)

def find_best_contract(spot_price: float, trade_type: str, setup_type: str, all_options: list, entry_dt: datetime.datetime):
    """
    Intelligent Expiry & Strike Selector:
    - BREAKOUT: Always selects Weekly Friday Expiry (3 to 7 DTE) to avoid rapid theta decay.
    - REVERSAL: Selects 1 DTE / 0 DTE (if >= 10h) or Weekly based on REVERSAL_EXPIRY_MODE.
    - Target Delta: Closest to 0.85 (0.80 to 0.90) on liquid $500 or $200 strike intervals.
    """
    is_call = (trade_type == 'BUY_CALL')
    contract_type = 'call_options' if is_call else 'put_options'
    target_d = TARGET_DELTA if is_call else -TARGET_DELTA

    eligible_options = [p for p in all_options if p.get('contract_type') == contract_type]
    if not eligible_options:
        return None

    # Group options by settlement expiration date
    exp_groups = {}
    for p in eligible_options:
        settle_str = p.get('settlement_time')
        if not settle_str:
            continue
        try:
            settle_dt = pd.to_datetime(settle_str).to_pydatetime()
            if settle_dt.tzinfo is None:
                settle_dt = settle_dt.replace(tzinfo=datetime.timezone.utc)
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=datetime.timezone.utc)
            
            hours_left = (settle_dt - entry_dt).total_seconds() / 3600.0
            if hours_left >= 2.0:
                dte_days = hours_left / 24.0
                exp_key = settle_dt.strftime('%Y-%m-%d %H:%M')
                if exp_key not in exp_groups:
                    exp_groups[exp_key] = {
                        'settle_dt': settle_dt, 
                        'dte': dte_days, 
                        'hours': hours_left,
                        'is_friday': settle_dt.weekday() == 4,
                        'products': []
                    }
                exp_groups[exp_key]['products'].append(p)
        except Exception:
            continue

    if not exp_groups:
        return None

    # Sort expirations by DTE
    sorted_expiries = sorted(exp_groups.values(), key=lambda x: x['dte'])

    # Determine which expirations to search based on Setup Type
    candidate_expiries = []
    
    if setup_type == 'BREAKOUT':
        # BREAKOUT RULE: Must use Weekly Friday expiration (min 2.5 DTE, typically 3 to 7 DTE)
        candidate_expiries = [exp for exp in sorted_expiries if exp['is_friday'] and exp['dte'] >= 2.0]
        if not candidate_expiries:
            # Fallback to any expiry >= 3 days
            candidate_expiries = [exp for exp in sorted_expiries if exp['dte'] >= 2.5]
    else: # REVERSAL
        if REVERSAL_EXPIRY_MODE == 'WEEKLY':
            candidate_expiries = [exp for exp in sorted_expiries if exp['is_friday'] and exp['dte'] >= 2.0]
        else:
            # 1 DTE Mode: 0 DTE (if >= 10h) -> 1 DTE -> 2 DTE -> Weekly fallback
            candidate_expiries = [exp for exp in sorted_expiries if exp['hours'] >= 10.0]

    if not candidate_expiries:
        candidate_expiries = sorted_expiries

    # Find liquid strike closest to Delta 0.85 in the candidate expiries
    for exp_info in candidate_expiries:
        dte = exp_info['dte']
        best_prod = None
        best_diff = 999.0

        for p in exp_info['products']:
            strike = float(p.get('strike_price', 0))
            if strike <= 0:
                continue
            delta = calculate_option_delta(spot_price, strike, dte, is_call)
            diff = abs(delta - target_d)
            
            # Check target range: 0.80 to 0.90 (buffer 0.78-0.92)
            in_range = (0.78 <= delta <= 0.92) if is_call else (-0.92 <= delta <= -0.78)
            if in_range and diff < best_diff:
                best_diff = diff
                best_prod = p

        if best_prod is not None:
            exp_str = exp_info['settle_dt'].strftime('%d-%b %H:%M UTC')
            print(f"[Contract Selected] {best_prod.get('symbol')} | Setup: {setup_type} | Expiry: {exp_str} ({exp_info['dte']:.1f} DTE) | Strike: ${best_prod.get('strike_price')}")
            return best_prod

    # Fallback to nearest valid strike
    nearest_exp = candidate_expiries[0]
    best_prod = min(nearest_exp['products'], key=lambda p: abs(float(p.get('strike_price', 0)) - (spot_price * (0.96 if is_call else 1.04))))
    return best_prod
