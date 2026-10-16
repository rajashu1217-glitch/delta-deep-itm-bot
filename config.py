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

# Model 1: Deep ITM Synthetic Delta Settings
DEEP_ITM_OFFSET = 7000.0        # Spot - $7000 for Call, Spot + $7000 for Put
FIXED_RISK_USD = 300.0          # Risk per trade ($300 USD)
SL_POINTS = 300.0               # Stop loss points on option premium ($300)
TP1_POINTS = 600.0              # Target 1 points (+600 pts = 1:2 Risk-Reward)

# Position Sizing
FIXED_SIZE_BTC = 1.0            # 300 risk / 300 pts SL = exactly 1.0 BTC contract size
MAX_POSITION_SIZE = 1.2         # Safety cap

# Time Stop
MAX_HOLDING_MINUTES = 240       # 4 Hours max holding time to prevent theta decay

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

