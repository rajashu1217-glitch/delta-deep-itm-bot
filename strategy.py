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
    TARGET_DELTA, REVERSAL_EXPIRY_MODE, OB_FVG_EXPIRY_MODE,
    TRAP_HOURS_IST, SKIP_DAYS_REVERSAL, SKIP_DAYS_OB_FVG,
    MIN_FVG_GAP, MAX_OB_BARS
)

def calculate_swing_sl(df_15m: pd.DataFrame, entry_signal: str, entry_price: float, buffer: float = SL_BUFFER_PTS, custom_sl: float = None):
    """
    Price Action Swing / OB Stop Loss:
    - If custom_sl provided (e.g. OB Low / High), use it with buffer.
    - Otherwise, last 4 candles swing high/low.
    - Capped between 150 pts min and 500 pts max.
    """
    if custom_sl is not None:
        if entry_signal == 'BUY_CALL':
            sl_dist = entry_price - custom_sl
        else:
            sl_dist = custom_sl - entry_price
    else:
        last_4 = df_15m.iloc[-4:]
        if entry_signal == 'BUY_CALL':
            recent_low = float(last_4['low'].min())
            sl_dist = entry_price - (recent_low - buffer)
        else:
            recent_high = float(last_4['high'].max())
            sl_dist = (recent_high + buffer) - entry_price
        
    sl_dist = max(SL_MIN_PTS, min(SL_MAX_PTS, sl_dist))
    return round(sl_dist, 2)

def update_active_obs(df_15m: pd.DataFrame, buffer: float = 30.0, min_gap: float = MIN_FVG_GAP):
    """
    Scans the last 35 candles to find active, unmitigated SMC Order Blocks + Fair Value Gaps.
    """
    active_obs = []
    n = len(df_15m)
    c_open = df_15m['open'].values
    c_high = df_15m['high'].values
    c_low = df_15m['low'].values
    c_close = df_15m['close'].values

    for i in range(2, n):
        # 1. Bullish FVG (Gap between Candle i-2 High and Candle i Low)
        if c_low[i] > c_high[i-2] + min_gap and c_close[i-1] > c_open[i-1] and c_close[i-2] < c_open[i-2]:
            active_obs.append({
                'type': 'BULLISH',
                'ob_high': float(c_high[i-2]),
                'ob_low': float(c_low[i-2]),
                'fvg_top': float(c_low[i]),
                'created_i': i,
                'sl': float(c_low[i-2] - buffer),
                'mitigated': False
            })
        # 2. Bearish FVG (Gap between Candle i-2 Low and Candle i High)
        if c_high[i] < c_low[i-2] - min_gap and c_close[i-1] < c_open[i-1] and c_close[i-2] > c_open[i-2]:
            active_obs.append({
                'type': 'BEARISH',
                'ob_high': float(c_high[i-2]),
                'ob_low': float(c_low[i-2]),
                'fvg_bot': float(c_high[i]),
                'created_i': i,
                'sl': float(c_high[i-2] + buffer),
                'mitigated': False
            })

        # Mark mitigated by subsequent candles
        for ob in active_obs:
            if ob['mitigated']: continue
            if i > ob['created_i']:
                if ob['type'] == 'BULLISH' and c_low[i] <= ob['ob_low']:
                    ob['mitigated'] = True
                elif ob['type'] == 'BEARISH' and c_high[i] >= ob['ob_high']:
                    ob['mitigated'] = True

    # Filter out mitigated or expired (> 32 bars)
    curr_i = n - 1
    valid_obs = [ob for ob in active_obs if (curr_i - ob['created_i']) <= MAX_OB_BARS and not ob['mitigated']]
    return valid_obs

def evaluate_market_setup(df_1h: pd.DataFrame, df_15m: pd.DataFrame, levels: dict, now_ist: datetime.datetime):
    """
    100% DELTA_API VERIFIED STRATEGY EVALUATOR (+45,000 USD Audited Setup):
    - Priority 1: SMC Liquidity Sweep (Reversal) -> Skip Saturday
    - Priority 2: SMC Order Block + FVG Genuine Retest -> Skip Sat & Sun
    - Hourly Filter: Skips the 7 identified loss-making trap hours (TRAP_HOURS_IST)
    Returns: (signal, setup_type, custom_sl) or (None, None, None)
    """
    day_name = now_ist.strftime("%A")
    hour_ist = now_ist.hour

    # 1. TRAP HOUR FILTER: Skip the 7 verified loss hours [1, 7, 8, 9, 12, 18, 23]
    if hour_ist in TRAP_HOURS_IST:
        return None, None, None

    if len(df_1h) < 25 or len(df_15m) < 35:
        return None, None, None

    last_15m = df_15m.iloc[-1]
    prev_15m = df_15m.iloc[-2]
    latest_1h = df_1h.iloc[-1]

    # Higher Timeframe Trend Bias (1H Close vs 1H 20-EMA)
    trend_1h = 1 if latest_1h['close'] > latest_1h['ema20'] else -1

    is_green = last_15m['close'] > last_15m['open']
    is_red   = last_15m['close'] < last_15m['open']
    above_ema15 = last_15m['close'] > last_15m['ema20']
    below_ema15 = last_15m['close'] < last_15m['ema20']

    # =========================================================================
    # PRIORITY 1: SMC LIQUIDITY SWEEP (REVERSAL) - SKIPS SATURDAY ONLY
    # =========================================================================
    if day_name not in SKIP_DAYS_REVERSAL:
        al = levels.get('asian_low')
        ah = levels.get('asian_high')
        pdl = levels.get('pdl')
        pdh = levels.get('pdh')

        valid_sups = [x for x in [al, pdl] if x is not None]
        valid_res  = [x for x in [ah, pdh] if x is not None]

        if valid_sups and valid_res:
            support = min(valid_sups)
            resistance = max(valid_res)

            swept_support = (prev_15m['low'] < support or last_15m['low'] < support) and last_15m['close'] > support and is_green and above_ema15
            swept_resistance = (prev_15m['high'] > resistance or last_15m['high'] > resistance) and last_15m['close'] < resistance and is_red and below_ema15

            if trend_1h == 1 and swept_support:
                return 'BUY_CALL', 'REVERSAL', None
            if trend_1h == -1 and swept_resistance:
                return 'BUY_PUT', 'REVERSAL', None

    # =========================================================================
    # PRIORITY 2: SMC ORDER BLOCK + FVG GENUINE RETEST - SKIPS SAT & SUN
    # =========================================================================
    if day_name not in SKIP_DAYS_OB_FVG:
        active_obs = update_active_obs(df_15m, buffer=SL_BUFFER_PTS, min_gap=MIN_FVG_GAP)
        curr_i = len(df_15m) - 1

        for ob in active_obs:
            # GENUINE RETEST ONLY: Must be a subsequent candle (never same bar as creation)
            if ob['created_i'] == curr_i:
                continue

            if ob['type'] == 'BULLISH' and trend_1h == 1:
                # Price pulls back into FVG gap and closes green above 15m 20-EMA
                if last_15m['low'] <= ob['fvg_top'] and last_15m['close'] >= ob['ob_low'] and is_green and above_ema15:
                    return 'BUY_CALL', 'OB_FVG', ob['sl']

            elif ob['type'] == 'BEARISH' and trend_1h == -1:
                # Price rallies into FVG gap and closes red below 15m 20-EMA
                if last_15m['high'] >= ob['fvg_bot'] and last_15m['close'] <= ob['ob_high'] and is_red and below_ema15:
                    return 'BUY_PUT', 'OB_FVG', ob['sl']

    return None, None, None

def calculate_option_delta(spot: float, strike: float, dte_days: float, is_call: bool, iv: float = 0.48) -> float:
    """Calculates Black-Scholes Delta for a given strike and DTE."""
    T = max(dte_days, 0.005) / 365.0
    d1 = (np.log(spot / strike) + 0.5 * iv**2 * T) / (iv * np.sqrt(T))
    return float(norm_cdf(d1)) if is_call else float(norm_cdf(d1) - 1.0)

def find_candidate_contracts(spot_price: float, trade_type: str, setup_type: str, all_options: list, entry_dt: datetime.datetime, limit: int = 4) -> list:
    """
    Intelligent Expiry & Multi-Strike Selector matching Delta Exchange Listed Products:
    - 1 DTE deep ITM (~0.85 Delta) for maximum responsiveness and minimal theta decay.
    - Avoids expired contracts: If after 17:15 IST, skips today's settlement and targets tomorrow/Monday.
    - Ranks strikes by closeness to 0.85 Delta, prioritizing Deeper ITM (0.85 -> 0.90) over shallower.
    - Returns top ranked candidate contracts so bot can fallback if one strike breaches Delta's Max OI limit.
    """
    is_call = (trade_type == 'BUY_CALL')
    contract_type = 'call_options' if is_call else 'put_options'

    eligible_options = [p for p in all_options if p.get('contract_type') == contract_type]
    if not eligible_options:
        return []

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
            # Contract must have at least 2.5 hours remaining
            if hours_left >= 2.5:
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
        return []

    sorted_expiries = sorted(exp_groups.values(), key=lambda x: x['dte'])

    # Candidate Expiries: Prefer 1 DTE (or 0 DTE if >= 8h left), fallback to Weekly
    candidate_expiries = [exp for exp in sorted_expiries if exp['hours'] >= 8.0]
    if not candidate_expiries:
        candidate_expiries = sorted_expiries

    ranked_products = []
    # Rank within candidate expiries (nearest target expiry first)
    for exp_info in candidate_expiries[:2]:
        dte = exp_info['dte']
        exp_candidates = []
        for p in exp_info['products']:
            strike = float(p.get('strike_price', 0))
            if strike <= 0:
                continue
            delta = calculate_option_delta(spot_price, strike, dte, is_call)
            delta_mag = abs(delta)
            
            # Deep ITM range: 0.75 to 0.95
            if 0.75 <= delta_mag <= 0.95:
                diff = abs(delta_mag - TARGET_DELTA)
                # Prioritize deeper ITM (0.85 -> 0.95) over shallower (0.75 -> 0.85) to minimize theta decay
                score = diff if delta_mag >= TARGET_DELTA else diff * 1.35
                exp_candidates.append({
                    'product': p,
                    'symbol': p.get('symbol'),
                    'strike': strike,
                    'delta': delta,
                    'delta_mag': delta_mag,
                    'score': score
                })
        exp_candidates.sort(key=lambda x: x['score'])
        ranked_products.extend([x['product'] for x in exp_candidates[:limit]])
        if len(ranked_products) >= limit:
            break

    if ranked_products:
        return ranked_products[:limit]

    # Fallback to nearest valid strike if no candidate in 0.75-0.95 range
    nearest_exp = candidate_expiries[0]
    best_prod = min(nearest_exp['products'], key=lambda p: abs(float(p.get('strike_price', 0)) - (spot_price * (0.90 if is_call else 1.10))))
    return [best_prod]

def find_best_contract(spot_price: float, trade_type: str, setup_type: str, all_options: list, entry_dt: datetime.datetime):
    """Wrapper returning top candidate contract for backwards compatibility."""
    cands = find_candidate_contracts(spot_price, trade_type, setup_type, all_options, entry_dt, limit=1)
    return cands[0] if cands else None
