import datetime
import pandas as pd
from indicators import calculate_ema, get_liquidity_levels
from config import DEEP_ITM_OFFSET, NY_SESSION_ONLY, NY_START_UTC, NY_END_UTC

def evaluate_market_setup(df_1h: pd.DataFrame, df_1m: pd.DataFrame):
    """
    Evaluates institutional triggers at 1-minute candle close:
    - 1-Hour Trend Filter (20 EMA)
    - Asian Range High/Low Liquidity Sweep (SMC Institutional Setup)
    Returns: 'BUY_CALL', 'BUY_PUT', or None
    """
    if len(df_1h) < 25 or len(df_1m) < 60:
        return None

    # Optional New York Session Filter (13:00 to 21:00 UTC = 6:30 PM to 2:30 AM IST)
    if NY_SESSION_ONLY:
        last_ts = int(df_1m.iloc[-1]['time'])
        utc_dt = datetime.datetime.fromtimestamp(last_ts, tz=datetime.timezone.utc)
        if not (NY_START_UTC <= utc_dt.hour < NY_END_UTC):
            return None
        
    # 1. 1-Hour Trend Filter
    df_1h = df_1h.copy()
    df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
    latest_1h = df_1h.iloc[-1]
    bullish_trend = latest_1h['close'] > latest_1h['ema20']
    bearish_trend = latest_1h['close'] < latest_1h['ema20']
    
    last_1m = df_1m.iloc[-1]
    prev_1m = df_1m.iloc[-2]
    
    # 2. Asian Session Reference Levels (00:00 to 08:00 UTC = 05:30 to 13:30 IST)
    curr_ts = int(last_1m['time'])
    levels = get_liquidity_levels(df_1m, curr_ts)
    asian_low = levels.get('asian_low')
    asian_high = levels.get('asian_high')
    
    # A. BUY CALL SETUP (Bullish Trend + Asian Support Liquidity Sweep & Reclaim)
    is_sweep_buy = (asian_low is not None and prev_1m['low'] < asian_low and last_1m['close'] > asian_low and last_1m['close'] > last_1m['open'])
    
    if bullish_trend and is_sweep_buy:
        return 'BUY_CALL'
                
    # B. BUY PUT SETUP (Bearish Trend + Asian Resistance Liquidity Sweep & Rejection)
    is_sweep_sell = (asian_high is not None and prev_1m['high'] > asian_high and last_1m['close'] < asian_high and last_1m['close'] < last_1m['open'])
    
    if bearish_trend and is_sweep_sell:
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
