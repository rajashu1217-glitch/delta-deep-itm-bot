# 🤖 Delta Exchange BTC Deep ITM Auto-Trading Bot
### Strategy: Liquidity Sweep + Squeeze Breakout (Model 1 Deep ITM Synthetic Delta)
### Backtested Performance: +$84,293.76 USD Net PnL (296 Trades)

---

## 📌 Overview & Fixed Strategy Logic
Yeh bot **Delta Exchange** par automated Deep ITM option trading execute karta hai:
1. **1-Hour Trend Filter:** BTCUSD spot par 1-hour 20 EMA se overall trend (Bullish/Bearish) filter hota hai.
2. **15-Minute Squeeze & Liquidity Scanner:** 15m TTM Volatility Squeeze aur Asian Range (05:30 - 13:30 IST) / PDH / PDL levels monitor karta hai.
3. **Multi-Trigger Entry (Deadlock Free):**
   - **Support Sweep:** Uptrend me Asian Low / PDL sweep karke green candle close hone par BUY CALL.
   - **Momentum Breakout:** Uptrend me agar market bina deep pullback ke pump ho raha hai, toh Asian High / PDH breakout hone par BUY CALL.
   - **Resistance Sweep / Breakdown:** Downtrend me Asian High sweep ya Asian Low breakdown par BUY PUT.
4. **Deep ITM Strike Selection:** Spot se exact **$7,000 Deep ITM** strike (Delta ~1.0) select karta hai.
5. **Target & SL:**
   - Target 1: **+600 pts** (50% book karke remaining 50% breakeven SL par trail karta hai).
   - Stop Loss: **-300 pts** fixed risk ($300).
   - Time Stop: **4 Hours (240 mins)** max duration to prevent theta decay.

---

## 🛠️ Files & Folders
* `bot_main.py`: Core trading loop with live tracking & Telegram diagnostics.
* `strategy.py`: 15m Multi-path institutional trigger engine & deep ITM contract matcher.
* `indicators.py`: 20 EMA, TTM Squeeze, Asian Range & PDH/PDL calculations.
* `delta_client.py`: Delta Exchange REST API client (Demo Testnet & Production).
* `server.py`: Lightweight web server with auto-ping keep-alive for Render.com.
* `render.yaml`: Render deployment configuration.
* `start_bot.bat`: Windows one-click local runner.
* `.env`: API keys and Telegram credentials.
