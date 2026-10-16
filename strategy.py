import datetime
import pandas as pd
from indicators import calculate_ema, calculate_ttm_squeeze, get_liquidity_levels
from config import DEEP_ITM_OFFSET

def evaluate_market_setup(df_1h: pd.DataFrame, df_15m: pd.DataFrame):
    """
    Evaluates institutional triggers at 15m candle close:
    Returns: 'BUY_CALL', 'BUY_PUT', or None
    """
    if len(df_1h) < 25 or len(df_15m) < 35:
        return None
        
    # 1. 1-Hour Trend Filter
    df_1h = df_1h.copy()
    df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
    latest_1h = df_1h.iloc[-1]
    bullish_trend = latest_1h['close'] > latest_1h['ema20']
    bearish_trend = latest_1h['close'] < latest_1h['ema20']
    
    # 2. 15-Minute Squeeze Calculation
    df_15m = calculate_ttm_squeeze(df_15m)
    
    # Check last 3 candles for Squeeze Compression or Firing
    recent_squeeze = df_15m['squeeze_on'].iloc[-4:-1].any() or df_15m['squeeze_fired'].iloc[-2]
    if not recent_squeeze:
        return None
        
    last_15m = df_15m.iloc[-1]
    prev_15m = df_15m.iloc[-2]
    
    # 3. Liquidity Reference Levels
    curr_ts = int(last_15m['time'])
    levels = get_liquidity_levels(df_15m, curr_ts)
    asian_low = levels.get('asian_low')
    asian_high = levels.get('asian_high')
    pdl = levels.get('pdl')
    pdh = levels.get('pdh')
    
    # A. BUY CALL SETUP (Bullish Trend + Support Sweep + Green close above 20 EMA)
    if bullish_trend:
        support_level = min([x for x in [asian_low, pdl] if x is not None], default=None)
        if support_level:
            # Rejection wick below support in previous or current candle
            swept_support = (prev_15m['low'] < support_level and prev_15m['close'] > support_level) or (last_15m['low'] < support_level)
            # Confirmation: current 15m candle is strong green & closed above 20 EMA
            is_green = last_15m['close'] > last_15m['open']
            above_ema = last_15m['close'] > last_15m['ema20']
            if swept_support and is_green and above_ema:
                return 'BUY_CALL'
                
    # B. BUY PUT SETUP (Bearish Trend + Resistance Sweep + Red close below 20 EMA)
    if bearish_trend:
        resistance_level = max([x for x in [asian_high, pdh] if x is not None], default=None)
        if resistance_level:
            # Rejection wick above resistance in previous or current candle
            swept_resistance = (prev_15m['high'] > resistance_level and prev_15m['close'] < resistance_level) or (last_15m['high'] > resistance_level)
            # Confirmation: current 15m candle is strong red & closed below 20 EMA
            is_red = last_15m['close'] < last_15m['open']
            below_ema = last_15m['close'] < last_15m['ema20']
            if swept_resistance and is_red and below_ema:
                return 'BUY_PUT'
                
    return None

def get_weekly_expiry(entry_dt: datetime.datetime):
    """Calculates nearest Friday weekly expiry with 2 to 5 DTE."""
    weekday = entry_dt.weekday() # Monday=0, Friday=4, Sunday=6
    days_until_friday = (4 - weekday) % 7
    if days_until_friday < 2:
        days_until_friday += 7 # Roll forward if expiry is today/tomorrow
    exp_date = entry_dt.date() + datetime.timedelta(days=days_until_friday)
    exp_code = exp_date.strftime('%d%m%y')
    dte = (datetime.datetime.combine(exp_date, datetime.time(12, 0), tzinfo=datetime.timezone.utc) - entry_dt).total_seconds() / 86400.0
    return exp_code, exp_date.strftime('%d/%m/%Y'), round(dte, 1)

def find_best_deep_itm_contract(spot_price: float, trade_type: str, all_options: list, entry_dt: datetime.datetime):
    """
    Finds exact matching Delta Exchange Option contract:
    - Strike: Spot - $7000 for Call, Spot + $7000 for Put
    - Expiry: Weekly Friday
    """
    is_call = (trade_type == 'BUY_CALL')
    target_strike_raw = spot_price - DEEP_ITM_OFFSET if is_call else spot_price + DEEP_ITM_OFFSET
    exp_code, exp_str, dte = get_weekly_expiry(entry_dt)
    
    contract_type = 'call_options' if is_call else 'put_options'
    
    # Filter products for this expiry and contract type
    candidates = []
    for p in all_options:
        sym = p.get('symbol', '')
        if p.get('contract_type') == contract_type and exp_code in sym:
            strike = float(p.get('strike_price', 0))
            candidates.append((p, strike))
            
    if not candidates:
        # Fallback to closest available weekly options
        for p in all_options:
            if p.get('contract_type') == contract_type:
                candidates.append((p, float(p.get('strike_price', 0))))
                
    if not candidates:
        return None
        
    # Pick contract closest to target strike
    best_prod, best_strike = min(candidates, key=lambda x: abs(x[1] - target_strike_raw))
    return best_prod
