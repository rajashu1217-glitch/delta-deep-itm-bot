# 🤖 Delta Exchange BTC Deep ITM Auto-Trading Bot
### Strategy: Liquidity Sweep + Squeeze Breakout (Model 1 Deep ITM Synthetic Delta)

---

## 📌 Overview
Yeh bot **Delta Exchange India** (`api.india.delta.exchange`) par 100% automated algorithmic option buying execute karta hai:
1. **15-Minute & 1-Hour Chart Scanner:** BTCUSD spot par 1-hour 20 EMA trend filter, 15m TTM Volatility Squeeze aur Asian Range/PDH/PDL liquidity sweeps monitor karta hai.
2. **Deep ITM Strike Selection:** Spot se exact **$7,000 Deep ITM** strike (Call ke liye Spot - $7k, Put ke liye Spot + $7k) select karta hai.
3. **Strict 1-Minute Candle Tracking:** Jaise hi 1m tick par Target 1 (+600 pts) ya Stop Loss (-300 pts) trigger hota hai, order turant execute ho jata hai.
4. **Target 1 Booking & Runner Trail:** Target 1 hit hone par 50% quantity book karta hai aur remaining 50% runner ka SL Breakeven par shift karke 15m 20 EMA par trail karta hai.
5. **Time Stop Protection:** 4 ghante (240 mins) se zyada koi trade open nahi rehta taaki theta decay na ho.

---

## 🛠️ Folder Structure
```
delta_deep_itm_bot/
├── config.py           # API Keys, Risk settings ($300 risk), Dry-run toggle
├── delta_client.py     # Delta Exchange REST API client (Orders, Balances, Candles)
├── indicators.py       # 20 EMA, TTM Squeeze, Asian Range & PDH/PDL calculations
├── strategy.py         # Signal trigger logic & Deep ITM strike resolver
├── bot_main.py         # 24/7 Live trading execution engine
├── start_bot.bat       # One-click Windows runner
└── README.md           # Documentation
```

---

## 🚀 How to Run the Bot

### Step 1: Configuration (`config.py`)
1. Open `config.py` in any text editor or VS Code.
2. Enter your Delta Exchange API credentials:
   ```python
   API_KEY = "your_delta_api_key"
   API_SECRET = "your_delta_api_secret"
   ```
3. By default, `DRY_RUN = True` (Paper Trading mode enabled) hai.
   - Pehle isko `DRY_RUN = True` par chalayein taaki bot market scan kare aur simulated orders log kare bina real paise risk kiye.
   - Jab aap satisfied ho jayein, tab `DRY_RUN = False` karke live trading activate karein!

### Step 2: Start the Bot
- Simply double-click **`start_bot.bat`** ya terminal me run karein:
  ```bash
  python bot_main.py
  ```

---

## 📱 Telegram Alerts (Optional)
Agar aapko mobile par instant alerts chahiye jab bhi bot trade open ya close kare:
1. `config.py` me `ENABLE_TELEGRAM = True` karein.
2. Apna Telegram `TELEGRAM_BOT_TOKEN` aur `TELEGRAM_CHAT_ID` daalein.
