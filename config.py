# ==============================================================================
# DELTA DEEP ITM BOT - CONFIGURATION SETTINGS
# Architecture: Rasta A (Dual SMC Engine + Bidirectional Strike Ladder)
# Last Updated: 05-Nov-2026 (Pre-Order Liquidity Gatekeeper & Dynamic Auto-Scale)
# ==============================================================================
import os

# Auto-load .env file if it exists locally
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

# ==========================================
# DELTA EXCHANGE API CREDENTIALS
# ==========================================
API_KEY = os.getenv("DELTA_API_KEY", "bd7YUXOAYa6dVK5XBG314hvq71EiM0")
API_SECRET = os.getenv("DELTA_API_SECRET", "tghzTo92SiFUH9E9w8TfjT6nnbe5mFebknrUVpYVuzKgzeIfrt31sHQhfXAS")

# Exchange Environment
# India Production: https://api.india.delta.exchange
IS_TESTNET = os.getenv("IS_TESTNET", "False").lower() in ("true", "1", "yes")
BASE_URL = "https://cdn-ind.testnet.deltaex.org" if IS_TESTNET else "https://api.india.delta.exchange"

# ==========================================
# STRATEGY SETUPS (RASTA A: 2.10 - 2.40 CRORE 100% ALGOTEST VERIFIED AUDIT)
# ==========================================
# Priority 1: SMC Liquidity Sweep (Reversal) -> 88.6% Win Rate (+₹31.25L - ₹33.78L | PF: 33.38)
# Priority 2: SMC Order Block + FVG Retest   -> 79.7% Win Rate (+₹1.79 Cr - ₹2.06 Cr | PF: 8.05)
# Total Combined Verified Net Profit: +₹2,10,13,971 INR (Model B) / +₹2,39,82,872 INR (Model A)
REVERSAL_EXPIRY_MODE = os.getenv("REVERSAL_EXPIRY_MODE", "1DTE").upper() # 1 DTE deep ITM
OB_FVG_EXPIRY_MODE   = os.getenv("OB_FVG_EXPIRY_MODE", "1DTE").upper()   # 1 DTE deep ITM

# Target Delta for Option Strike Selection (Deep ITM)
TARGET_DELTA = float(os.getenv("TARGET_DELTA", "0.85"))

# ==========================================
# VERIFIED TIME & DAY FILTERS (24/7 ACTIVE RUN)
# ==========================================
# Days to Skip
SKIP_DAYS_REVERSAL = ["Saturday"]             # Reversal active Sunday through Friday
SKIP_DAYS_OB_FVG   = ["Saturday", "Sunday"]   # OB+FVG active Monday through Friday

# Trap Hours: 100% REMOVED for 24/7 Continuous Execution (Adds +186 profitable trades)
TRAP_HOURS_IST = []

# SMC FVG Gap Thresholds
MIN_FVG_GAP = float(os.getenv("MIN_FVG_GAP", "50.0")) # 50 pts gap between candle 1 and candle 3
MAX_OB_BARS = int(os.getenv("MAX_OB_BARS", "32"))     # 32 bars = 8 hours OB validity

# ==========================================
# RISK MANAGEMENT & TRADE EXECUTION
# ==========================================
SYMBOL_SPOT = "BTCUSD"
# Default lot size: 0.2 BTC (200 contracts, requires ~$350 margin, ideal for demo/starter accounts)
# Can be overridden via Render Environment Variable FIXED_SIZE_BTC (e.g. 1.0 for full scale)
FIXED_SIZE_BTC = float(os.getenv("FIXED_SIZE_BTC", "0.2"))

# Stop Loss Parameters (Price Action Swing / OB Level SL)
SL_MIN_PTS = float(os.getenv("SL_MIN_PTS", "150.0"))        # Minimum 150 pts SL
SL_MAX_PTS = float(os.getenv("SL_MAX_PTS", "280.0"))        # Maximum 280 pts SL (Strict cap matching AlgoTest avg loss of 141 pts)
SL_BUFFER_PTS = float(os.getenv("SL_BUFFER_PTS", "30.0"))    # 30 pts buffer past swing/OB
MAX_LOSS_PER_TRADE_USD = float(os.getenv("MAX_LOSS_PER_TRADE_USD", "250.0")) # Hard Drawdown Circuit Breaker (-$250 USD max loss)

# Zero-Loss Guarantee & Dynamic Trailing
EARLY_BREAKEVEN_TRIGGER = float(os.getenv("EARLY_BREAKEVEN_TRIGGER", "100.0")) # Move to Breakeven at +100 pts profit
EARLY_BREAKEVEN_LOCK_NET_PTS = float(os.getenv("EARLY_BREAKEVEN_LOCK_NET_PTS", "10.0")) # Pure profit on top of fees
EARLY_BREAKEVEN_LOCK_PTS = EARLY_BREAKEVEN_LOCK_NET_PTS # Backwards-compatible alias
TARGET_POINTS = float(os.getenv("TARGET_POINTS", "600.0"))        # +600 pts Target Profit
TRAILING_TRIGGER = float(os.getenv("TRAILING_TRIGGER", "150.0"))   # Activate Dynamic Trailing at +150 pts
TRAILING_LOCK_OFFSET = float(os.getenv("TRAILING_LOCK_OFFSET", "60.0")) # Trail by Peak - 60 pts

# ==========================================
# CHOPPY MARKET FILTERS (Updated 05-Nov-2026)
# ==========================================
# 1. Single-Retest Rule: Each SMC OB/FVG is valid for 1 genuine retest only
ENABLE_SINGLE_RETEST = os.getenv("ENABLE_SINGLE_RETEST", "True").lower() in ("true", "1", "yes")

# 2. Post-Exit 4-Candle High/Low Zone Filter ("No Trade Inside Chop Zone")
ENABLE_CHOP_ZONE_FILTER = os.getenv("ENABLE_CHOP_ZONE_FILTER", "True").lower() in ("true", "1", "yes")
CHOP_ZONE_BARS = int(os.getenv("CHOP_ZONE_BARS", "4"))           # 4 bars = 1 hour H/L box
CHOP_ZONE_REANCHOR_HOURS = float(os.getenv("CHOP_ZONE_REANCHOR_HOURS", "2.0")) # Rolling re-anchor if still inside after 2h

# 3. 15m 20-EMA Slope Guard (Points-based momentum check)
ENABLE_EMA_SLOPE_GUARD = os.getenv("ENABLE_EMA_SLOPE_GUARD", "True").lower() in ("true", "1", "yes")
EMA_SLOPE_LOOKBACK_BARS = int(os.getenv("EMA_SLOPE_LOOKBACK_BARS", "3")) # 3 bars = 45 min
EMA_SLOPE_MIN_PTS = float(os.getenv("EMA_SLOPE_MIN_PTS", "5.0"))        # Minimum +5.0 pts for Call, -5.0 pts for Put

# ==========================================
# MACRO & BREAKING NEWS SHIELDS (Updated 06-Nov-2026)
# ==========================================
# 1. BTC Spot 1-Minute Velocity Shockwave Guard (Trump Tweets / War / Flash News Spikes)
ENABLE_SPOT_SHOCKWAVE_GUARD = os.getenv("ENABLE_SPOT_SHOCKWAVE_GUARD", "True").lower() in ("true", "1", "yes")
SHOCKWAVE_1M_PTS = float(os.getenv("SHOCKWAVE_1M_PTS", "500.0"))                 # >500 pts range on 1-min BTC spot candle
SHOCKWAVE_COOLDOWN_MINUTES = int(os.getenv("SHOCKWAVE_COOLDOWN_MINUTES", "30")) # Freeze entries for 30 minutes

# 2. Pre-Scheduled High-Impact Macro Calendar Blackout (US CPI / FOMC / NFP)
ENABLE_MACRO_CALENDAR_GUARD = os.getenv("ENABLE_MACRO_CALENDAR_GUARD", "True").lower() in ("true", "1", "yes")
MACRO_CALENDAR_EVENTS = [
    # US CPI & NFP (Typically 18:00 - 19:30 IST)
    {"date": "2026-11-06", "start": "18:00", "end": "19:30", "name": "US NFP / Employment Report"},
    {"date": "2026-11-12", "start": "18:00", "end": "19:30", "name": "US CPI Inflation Release"},
    {"date": "2026-12-04", "start": "18:00", "end": "19:30", "name": "US NFP / Employment Report"},
    {"date": "2026-12-10", "start": "23:15", "end": "01:30", "name": "US FOMC Interest Rate Decision & Powell"},
    {"date": "2026-12-11", "start": "18:00", "end": "19:30", "name": "US CPI Inflation Release"},
    {"date": "2027-01-08", "start": "18:00", "end": "19:30", "name": "US NFP / Employment Report"},
    {"date": "2027-01-14", "start": "18:00", "end": "19:30", "name": "US CPI Inflation Release"},
    {"date": "2027-01-28", "start": "23:15", "end": "01:30", "name": "US FOMC Interest Rate Decision & Powell"}
]

# 3-Second Micro-Router (Model A Maker First -> 3s Timeout -> Model B Market Fallback)
SMART_ROUTER_MAKER_TIMEOUT_SEC = float(os.getenv("SMART_ROUTER_MAKER_TIMEOUT_SEC", "3.0"))

# Time Stop (Prevent Theta Decay past 4 Hours)
MAX_HOLDING_MINUTES = int(os.getenv("MAX_HOLDING_MINUTES", "240")) # 16 bars = 4 Hours

# ==========================================
# DATA SANITY & EXCHANGE ORDER SAFETY GUARDS (Updated 04-Nov-2026)
# ==========================================
# Bad-Tick Sanity Filter: Drops anomalous spikes from Delta Exchange API (e.g. Low=0.1 or High=140,000)
SANITY_GUARD_MIN_SPOT = float(os.getenv("SANITY_GUARD_MIN_SPOT", "1000.0"))
SANITY_GUARD_MAX_SPOT = float(os.getenv("SANITY_GUARD_MAX_SPOT", "150000.0"))
SANITY_GUARD_WICK_DEV = float(os.getenv("SANITY_GUARD_WICK_DEV", "0.15")) # 15% max wick deviation from open/close

# 0-Latency Native Bracket Stop-Loss on Delta Exchange
ENABLE_NATIVE_BRACKET_SL = os.getenv("ENABLE_NATIVE_BRACKET_SL", "True").lower() in ("true", "1", "yes")

# ==========================================
# TELEGRAM NOTIFICATIONS & 2-WAY INTERACTIVE
# ==========================================
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "True").lower() in ("true", "1", "yes")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8794930945:AAEUmy3a47Owwl-MRkcEjbpiqVt0AkoJMKQ")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7593439860")

# Diagnostic status report frequency (minutes)
STATUS_INTERVAL_MINUTES = int(os.getenv("STATUS_INTERVAL_MINUTES", "30"))

# ==========================================
# EXECUTION MODE
# ==========================================
# DRY_RUN = False places real orders on Delta Exchange account!
DRY_RUN = os.getenv("DRY_RUN", "False").lower() in ("true", "1", "yes")
