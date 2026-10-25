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
# India Testnet/Demo: https://cdn-ind.testnet.deltaex.org
# India Production:   https://api.india.delta.exchange
IS_TESTNET = os.getenv("IS_TESTNET", "False").lower() in ("true", "1", "yes")
BASE_URL = "https://cdn-ind.testnet.deltaex.org" if IS_TESTNET else "https://api.india.delta.exchange"

# ==========================================
# STRATEGY EXPIRY CONFIGURATION (Option A vs Option B)
# ==========================================
# BREAKOUT: Always Weekly Friday Expiry (3 to 7 DTE) to completely prevent theta decay
BREAKOUT_EXPIRY_MODE = "WEEKLY"

# REVERSAL: "1DTE" (Option A: Capital efficient, 82.9% WR) or "WEEKLY" (Option B: All Weekly, 90.8% WR)
REVERSAL_EXPIRY_MODE = os.getenv("REVERSAL_EXPIRY_MODE", "1DTE").upper()

# Target Delta for Option Strike Selection
TARGET_DELTA = float(os.getenv("TARGET_DELTA", "0.85"))  # 0.80 to 0.90 Deep ITM range

# ==========================================
# RISK MANAGEMENT & TRADE EXECUTION
# ==========================================
SYMBOL_SPOT = "BTCUSD"
FIXED_SIZE_BTC = float(os.getenv("FIXED_SIZE_BTC", "1.0"))  # 1.0 BTC option lot size

# Stop Loss Parameters (Price Action Swing SL)
SL_MIN_PTS = float(os.getenv("SL_MIN_PTS", "150.0"))        # Minimum 150 pts SL
SL_MAX_PTS = float(os.getenv("SL_MAX_PTS", "500.0"))        # Maximum 500 pts SL
SL_BUFFER_PTS = float(os.getenv("SL_BUFFER_PTS", "30.0"))    # 30 pts buffer past swing

# Target & Trailing SL
TARGET_POINTS = float(os.getenv("TARGET_POINTS", "600.0"))  # +600 pts Target Profit
TRAILING_TRIGGER = float(os.getenv("TRAILING_TRIGGER", "200.0")) # Activate Trailing SL at +200 pts
TRAILING_LOCK_OFFSET = float(os.getenv("TRAILING_LOCK_OFFSET", "100.0")) # Trail by Peak - 100 pts

# Time Stop (Prevent Theta Decay past 4 Hours)
MAX_HOLDING_MINUTES = int(os.getenv("MAX_HOLDING_MINUTES", "240")) # 16 bars = 4 Hours

# Trading Window (London + New York Sessions in UTC)
SESSION_START_UTC = int(os.getenv("SESSION_START_UTC", "8"))  # 13:30 IST
SESSION_END_UTC = int(os.getenv("SESSION_END_UTC", "21"))     # 02:30 IST

# ==========================================
# TELEGRAM NOTIFICATIONS
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
