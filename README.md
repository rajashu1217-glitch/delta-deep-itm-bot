# 🤖 Delta Exchange BTC Deep ITM Auto-Trading Bot (Option A Master Setup)
### Strategy: Dual-Quota Institutional Setup (Breakout Weekly + Reversal 1DTE)
### Verified Backtested Performance: +$30,811.69 USD Net PnL (557 Trades | 71.99% Win Rate)

---

## 📌 Architecture & Strategy Rules (100% Verified)
Yeh bot **Delta Exchange India** par automated institutional Deep ITM option trading execute karta hai:

1. **Dual-Quota Engine (Independent Setups):**
   - **Breakout Setup (1 trade/day):** Weekly Friday Expiration (3 to 7 DTE) to eliminate theta decay.
   - **Reversal Setup (1 trade/day):** 1 DTE / 0 DTE Expiration for high-capital efficiency & sharp liquidity sweeps.
   - Reversal setup Breakout se block nahi hota; dono independent daily quotas par chalte hain.

2. **1-Hour Trend Bias Filter:**
   - 1H Close > 1H 20-EMA ➔ Bullish Trend (Only BUY CALL allowed).
   - 1H Close < 1H 20-EMA ➔ Bearish Trend (Only BUY PUT allowed).

3. **15-Minute Entry Confirmation:**
   - **Reversal (SMC Liquidity Sweep):** Asian Low/PDL sweep + Green Reclaim + Close > 15m EMA20.
   - **Breakout (Level Continuation):** Asian High/PDH breakout + Green Close + Close > 15m EMA20.

4. **Deep ITM Strike Selection (~0.85 Delta):**
   - Live Delta Exchange option chain se closest to 0.85 Delta (0.80 - 0.90 range) select karta hai taaki option spot ki tarah 1:1 move kare.

5. **Dynamic Risk Management & Profit Booking:**
   - **Price Action Swing SL:** Last 4 candles (1H) High/Low ± 30 pts buffer (Capped 150 - 500 pts).
   - **Dynamic Trailing SL:** Auto-activates at **+200 pts profit**, trailing 100 pts behind peak.
   - **Target 1 (+600 pts):** Books 50% profit, moves SL to Breakeven (Entry).
   - **Runner Trail:** Remaining 50% position trails until 15m candle closes opposite to 15m 20-EMA.
   - **Time Stop:** 4 Hours (240 mins / 16 bars) maximum duration.

---

## 📊 Backtested Performance Bifurcation (Option A)
* **Breakout Leg:** 481 Trades | 338 Wins (70.3% Win Rate) | **+$15,584.26 USD** Net
* **Reversal Leg:** 76 Trades | 63 Wins (82.9% Win Rate) | **+$15,227.43 USD** Net
* **Total Performance:** 557 Trades | 401 Wins | **71.99% Win Rate** | **+$30,811.69 USD** Net

---

## 🛠️ Files & Folders
* `bot_main.py`: Core trading loop with dual-quota state machine & live Telegram diagnostics.
* `strategy.py`: Institutional SMC sweep/breakout evaluator, Black-Scholes Delta scanner, swing SL calculator.
* `indicators.py`: 20 EMA, Asian Range (05:30 - 13:30 IST), and PDH/PDL liquidity levels.
* `delta_client.py`: Delta Exchange REST API client (Demo Testnet & Production).
* `server.py`: Lightweight web server with auto-ping keep-alive for Render.com 24x7 hosting.
* `render.yaml`: Render deployment configuration.
* `start_bot.bat`: Windows one-click local runner.
* `requirements.txt`: Python package dependencies.
* `.env`: API keys and Telegram credentials.
