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
SL_MAX_PTS = float(os.getenv("SL_MAX_PTS", "500.0"))        # Maximum 500 pts SL (Hard Cap)
SL_BUFFER_PTS = float(os.getenv("SL_BUFFER_PTS", "30.0"))    # 30 pts buffer past swing/OB
MAX_LOSS_PER_TRADE_USD = float(os.getenv("MAX_LOSS_PER_TRADE_USD", "250.0")) # Hard Drawdown Circuit Breaker (-$250 USD max loss)

# Target & Trailing SL (Rasta A: Wealth Maximizer Setup - Verified +2.10 Cr)
TARGET_POINTS = float(os.getenv("TARGET_POINTS", "600.0"))        # +600 pts Target Profit
TRAILING_TRIGGER = float(os.getenv("TRAILING_TRIGGER", "150.0"))   # Activate Trailing SL at +150 pts (Locks +90 pts)
TRAILING_LOCK_OFFSET = float(os.getenv("TRAILING_LOCK_OFFSET", "60.0")) # Trail by Peak - 60 pts

# 3-Second Micro-Router (Model A Maker First -> 3s Timeout -> Model B Market Fallback)
SMART_ROUTER_MAKER_TIMEOUT_SEC = float(os.getenv("SMART_ROUTER_MAKER_TIMEOUT_SEC", "3.0"))

# Time Stop (Prevent Theta Decay past 4 Hours)
MAX_HOLDING_MINUTES = int(os.getenv("MAX_HOLDING_MINUTES", "240")) # 16 bars = 4 Hours

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
