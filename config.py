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

# DELTA EXCHANGE API CREDENTIALS
# ==========================================
# Get your API keys from: Delta Exchange India -> Settings -> API Keys
API_KEY = os.getenv("DELTA_API_KEY", "YOUR_DELTA_API_KEY_HERE")
API_SECRET = os.getenv("DELTA_API_SECRET", "YOUR_DELTA_API_SECRET_HERE")

# Exchange Environment
# India Testnet/Demo: https://cdn-ind.testnet.deltaex.org
# India Production:   https://api.india.delta.exchange
IS_TESTNET = os.getenv("IS_TESTNET", "True").lower() in ("true", "1", "yes")
BASE_URL = "https://cdn-ind.testnet.deltaex.org" if IS_TESTNET else "https://api.india.delta.exchange"

# ==========================================
# STRATEGY & RISK MANAGEMENT PARAMETERS
# ==========================================
SYMBOL_SPOT = "BTCUSD"

# Low-Loss 1-Trade-Per-Day Deep ITM Settings (AlgoTest Verified)
DEEP_ITM_OFFSET = float(os.getenv("DEEP_ITM_OFFSET", "5000.0"))
FIXED_RISK_USD = float(os.getenv("FIXED_RISK_USD", "300.0"))
SL_POINTS = float(os.getenv("SL_POINTS", "300.0"))
TP1_POINTS = float(os.getenv("TP1_POINTS", "600.0"))
ONE_TRADE_PER_DAY = os.getenv("ONE_TRADE_PER_DAY", "True").lower() in ("true", "1", "yes")
CLOSE_FULL_AT_TP1 = os.getenv("CLOSE_FULL_AT_TP1", "True").lower() in ("true", "1", "yes")

# Position Sizing
FIXED_SIZE_BTC = float(os.getenv("FIXED_SIZE_BTC", "1.0"))
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "1.2"))

# Time Stop
MAX_HOLDING_MINUTES = int(os.getenv("MAX_HOLDING_MINUTES", "240"))

# New York Session Filter (13:00 to 21:00 UTC = 6:30 PM to 2:30 AM IST)
NY_SESSION_ONLY = os.getenv("NY_SESSION_ONLY", "False").lower() in ("true", "1", "yes")
NY_START_UTC = int(os.getenv("NY_START_UTC", "13")) # 6:30 PM IST
NY_END_UTC = int(os.getenv("NY_END_UTC", "21"))     # 2:30 AM IST

# ==========================================
# TELEGRAM NOTIFICATIONS (OPTIONAL)
# ==========================================
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "False").lower() in ("true", "1", "yes")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# ==========================================
# EXECUTION MODE
# ==========================================
# If DRY_RUN is True, the bot scans live market & simulates orders without placing real funds!
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")

