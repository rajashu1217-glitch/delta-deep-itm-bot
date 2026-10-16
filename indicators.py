import pandas as pd
import numpy as np
import datetime

def calculate_ema(series: pd.Series, span: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()

def calculate_ttm_squeeze(df: pd.DataFrame, length: int = 20, bb_mult: float = 2.0, kc_mult: float = 1.5):
    """
    TTM Volatility Squeeze Indicator:
    - Bollinger Bands: 20 length, 2.0 std dev
    - Keltner Channels: 20 length, 1.5 ATR multiplier
    Returns: squeeze_on (bool), squeeze_fired (bool)
    """
    df = df.copy()
    # 20 SMA
    df['sma20'] = df['close'].rolling(window=length).mean()
    # Standard deviation for Bollinger Bands
    df['std20'] = df['close'].rolling(window=length).std()
    df['bb_upper'] = df['sma20'] + (bb_mult * df['std20'])
    df['bb_lower'] = df['sma20'] - (bb_mult * df['std20'])
    
    # ATR for Keltner Channels
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr20'] = df['tr'].rolling(window=length).mean()
    
    # Keltner Channels using 20 EMA
    df['ema20'] = calculate_ema(df['close'], span=length)
    df['kc_upper'] = df['ema20'] + (kc_mult * df['atr20'])
    df['kc_lower'] = df['ema20'] - (kc_mult * df['atr20'])
    
    # Squeeze Condition
    # Squeeze ON: BB inside KC
    df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
    # Squeeze FIRED: BB expands outside KC after being inside
    df['squeeze_fired'] = (~df['squeeze_on']) & (df['squeeze_on'].shift(1) == True)
    
    return df

def get_liquidity_levels(df_15m: pd.DataFrame, current_ts: int):
    """
    Calculates:
    - Asian Range High/Low: Highest & Lowest between 00:00 UTC and 08:00 UTC
    - Previous Day High (PDH) & Previous Day Low (PDL) (00:00 UTC to 23:59 UTC)
    """
    curr_dt = datetime.datetime.fromtimestamp(current_ts, tz=datetime.timezone.utc)
    today_start = datetime.datetime.combine(curr_dt.date(), datetime.time(0, 0), tzinfo=datetime.timezone.utc)
    today_start_ts = int(today_start.timestamp())
    
    # Asian Session: 00:00 to 08:00 UTC
    asian_start_ts = today_start_ts
    asian_end_ts = today_start_ts + 8 * 3600
    
    # Yesterday: 00:00 UTC to 23:59 UTC
    yesterday_start = today_start - datetime.timedelta(days=1)
    yesterday_start_ts = int(yesterday_start.timestamp())
    yesterday_end_ts = today_start_ts
    
    asian_candles = df_15m[(df_15m['time'] >= asian_start_ts) & (df_15m['time'] < asian_end_ts)]
    prev_day_candles = df_15m[(df_15m['time'] >= yesterday_start_ts) & (df_15m['time'] < yesterday_end_ts)]
    
    asian_high = float(asian_candles['high'].max()) if not asian_candles.empty else None
    asian_low = float(asian_candles['low'].min()) if not asian_candles.empty else None
    
    pdh = float(prev_day_candles['high'].max()) if not prev_day_candles.empty else None
    pdl = float(prev_day_candles['low'].min()) if not prev_day_candles.empty else None
    
    return {
        'asian_high': asian_high,
        'asian_low': asian_low,
        'pdh': pdh,
        'pdl': pdl
    }
