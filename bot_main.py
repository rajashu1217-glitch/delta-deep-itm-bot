import time
import datetime
import requests
import pandas as pd
from config import (
    SYMBOL_SPOT, FIXED_SIZE_BTC, SL_POINTS, TP1_POINTS, 
    MAX_HOLDING_MINUTES, DRY_RUN, ENABLE_TELEGRAM, 
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
from delta_client import DeltaClient
from strategy import evaluate_market_setup, find_best_deep_itm_contract
from indicators import calculate_ema

def send_telegram(msg: str):
    """Send real-time alert to Telegram."""
    try:
        print(f"[ALERT] {msg.encode('ascii', 'replace').decode('ascii')}")
    except Exception:
        pass
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        except Exception as e:
            print(f"[Telegram Error] {e}")

class DeltaDeepITMBot:
    def __init__(self):
        self.client = DeltaClient()
        self.state = "IDLE"  # "IDLE", "IN_TRADE_LEG1", "IN_TRADE_RUNNER"
        self.active_trade = {}
        print("="*65)
        print("[INIT] DELTA EXCHANGE BTC DEEP ITM OPTION BUYING BOT INITIALIZED")
        print(f"Mode: {'DRY RUN (PAPER TRADING)' if DRY_RUN else 'LIVE TRADING'}")
        print(f"Risk per Trade: $300 USD | Fixed Size: {FIXED_SIZE_BTC} BTC")
        print(f"SL: -{SL_POINTS} pts | TP1: +{TP1_POINTS} pts (1:2 RR)")
        print("="*65)

    def run(self):
        last_checked_candle_ts = 0

        while True:
            try:
                now_ts = int(time.time())
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                now_ist = now_dt + datetime.timedelta(hours=5, minutes=30)

                # ==========================================
                # 1. SETUP SCANNER (Runs at 15m Candle Close)
                # ==========================================
                # 15m candles close at :00, :15, :30, :45
                is_15m_close = (now_dt.minute % 15 == 0) and (now_dt.second <= 15)

                if self.state == "IDLE" and is_15m_close:
                    current_15m_boundary = (now_ts // 900) * 900
                    if current_15m_boundary > last_checked_candle_ts:
                        last_checked_candle_ts = current_15m_boundary
                        self._scan_and_execute_setup(now_ts, now_dt, now_ist)

                # ==========================================
                # 2. 1-MINUTE ACTIVE TRADE MANAGER
                # ==========================================
                if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"]:
                    self._manage_active_trade(now_ts, now_dt, now_ist)

                # Sleep 5 seconds before next tick
                time.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user.")
                break
            except Exception as e:
                print(f"[Bot Loop Exception] {e}")
                time.sleep(10)

    def _scan_and_execute_setup(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        print(f"\n[{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}] Checking 15m & 1h market setup...")
        
        # Fetch 1h and 15m spot candles
        c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
        c_15m = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 12 * 3600, end_ts=now_ts)

        if not c_1h or not c_15m:
            print("[Warning] Incomplete candles returned from exchange.")
            return

        df_1h = pd.DataFrame(c_1h)
        df_15m = pd.DataFrame(c_15m)

        trade_type = evaluate_market_setup(df_1h, df_15m)
        if not trade_type:
            print("Setup status: Neutral / No trigger found.")
            return

        # Setup Confirmed!
        spot_open = float(c_15m[-1]['close'])
        print(f"[SIGNAL] VALID SETUP DETECTED: {trade_type} at Spot ${spot_open:,.1f}")

        # Fetch active options from Delta
        all_options = self.client.get_all_option_products()
        selected_prod = find_best_deep_itm_contract(spot_open, trade_type, all_options, now_dt)

        if not selected_prod:
            print("[Error] No suitable Deep ITM option contract found.")
            return

        prod_id = selected_prod['id']
        symbol = selected_prod['symbol']
        strike = selected_prod['strike_price']

        # Fetch exact 1m open price of this option
        opt_candles = self.client.get_candles(f"MARK:{symbol}", resolution="1m", start_ts=now_ts - 120, end_ts=now_ts)
        entry_premium = float(opt_candles[-1]['open']) if opt_candles else (7000.0 + spot_open * 0.01)

        # Execute Entry Order at 1m Open Tick
        order_res = self.client.place_order(product_id=prod_id, size=FIXED_SIZE_BTC, side="buy", order_type="market_order")

        # Set Trade State
        self.state = "IN_TRADE_LEG1"
        self.active_trade = {
            "symbol": symbol,
            "product_id": prod_id,
            "trade_type": trade_type,
            "strike": strike,
            "entry_time_ts": now_ts,
            "entry_ist": now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            "entry_premium": entry_premium,
            "size": FIXED_SIZE_BTC,
            "sl_prem": round(entry_premium - SL_POINTS, 2),
            "tp1_prem": round(entry_premium + TP1_POINTS, 2),
            "btc_spot_entry": spot_open
        }

        msg = (
            f"🎯 NEW TRADE OPENED!\n"
            f"Type: {trade_type} | Symbol: {symbol}\n"
            f"Strike: ${strike} | Entry Prem: ${entry_premium}\n"
            f"Stop Loss: ${self.active_trade['sl_prem']} (-$300)\n"
            f"Target 1: ${self.active_trade['tp1_prem']} (+$600 / 1:2 RR)\n"
            f"Time: {self.active_trade['entry_ist']}"
        )
        send_telegram(msg)

    def _manage_active_trade(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        t = self.active_trade
        sym = t['symbol']
        prod_id = t['product_id']

        # Check holding duration
        minutes_held = (now_ts - t['entry_time_ts']) // 60

        # Fetch latest 1-min mark candle of the option
        opt_candles = self.client.get_candles(f"MARK:{sym}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
        if not opt_candles:
            return

        latest_c = opt_candles[-1]
        curr_low = float(latest_c['low'])
        curr_high = float(latest_c['high'])
        curr_open = float(latest_c['open'])

        # ==========================================
        # LEG 1: CHECKING HARD SL & TP1
        # ==========================================
        if self.state == "IN_TRADE_LEG1":
            # 1. Stop Loss Hit (-300 pts)
            if curr_low <= t['sl_prem']:
                exit_prem = t['sl_prem'] if curr_open > t['sl_prem'] else curr_open
                self._close_position(exit_prem, "STOP_LOSS", now_ist)
                return

            # 2. Target 1 Hit (+600 pts)
            if curr_high >= t['tp1_prem']:
                print(f"[TP1] TARGET 1 HIT at ${t['tp1_prem']}! Booking 50% quantity...")
                # Close 50% size (0.5 BTC)
                self.client.place_order(product_id=prod_id, size=t['size'] * 0.5, side="sell", order_type="market_order")
                
                # Move SL to Breakeven
                t['sl_prem'] = t['entry_premium']
                t['tp1_booked_prem'] = t['tp1_prem']
                self.state = "IN_TRADE_RUNNER"

                send_telegram(f"✅ TARGET 1 BOOKED on {sym} at ${t['tp1_prem']} (+50% / +$300 gain)! Runner 50% trailing with Breakeven SL (${t['entry_premium']}).")
                return

        # ==========================================
        # LEG 2: RUNNER TRAILING WITH 15m 20 EMA
        # ==========================================
        elif self.state == "IN_TRADE_RUNNER":
            # Breakeven SL hit
            if curr_low <= t['sl_prem']:
                runner_exit = t['sl_prem'] if curr_open > t['sl_prem'] else curr_open
                avg_exit = round(0.5 * t['tp1_booked_prem'] + 0.5 * runner_exit, 2)
                self._close_position(avg_exit, "RUNNER_BREAKEVEN", now_ist)
                return

            # Check 15m candle close for 20 EMA trail
            if now_dt.minute % 15 == 0 and now_dt.second <= 15:
                spot_c = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 3600, end_ts=now_ts)
                if spot_c and len(spot_c) >= 20:
                    df_spot = pd.DataFrame(spot_c)
                    df_spot['ema20'] = calculate_ema(df_spot['close'], 20)
                    last_spot = df_spot.iloc[-1]
                    is_call = (t['trade_type'] == 'BUY_CALL')
                    
                    # Exit runner if close breaks 20 EMA
                    if (is_call and last_spot['close'] < last_spot['ema20']) or (not is_call and last_spot['close'] > last_spot['ema20']):
                        runner_exit = curr_open
                        avg_exit = round(0.5 * t['tp1_booked_prem'] + 0.5 * runner_exit, 2)
                        self._close_position(avg_exit, "RUNNER_EMA_TRAIL", now_ist)
                        return

        # ==========================================
        # 3. TIME STOP: 4 HOURS (240 MINUTES)
        # ==========================================
        if minutes_held >= MAX_HOLDING_MINUTES:
            self._close_position(curr_open, "TIME_STOP_4H", now_ist)

    def _close_position(self, exit_premium: float, reason: str, now_ist: datetime.datetime):
        t = self.active_trade
        remaining_size = t['size'] if self.state == "IN_TRADE_LEG1" else t['size'] * 0.5
        
        # Place closing order
        self.client.place_order(product_id=t['product_id'], size=remaining_size, side="sell", order_type="market_order")

        entry_prem = t['entry_premium']
        gross_pnl = (exit_premium - entry_prem) * t['size']
        # Delta 0.01% fee on spot
        spot_exit = self.client.get_spot_price(SYMBOL_SPOT)
        fees = (t['btc_spot_entry'] + spot_exit) * t['size'] * 0.0001
        net_pnl = round(gross_pnl - fees, 2)

        msg = (
            f"🏁 TRADE CLOSED ({reason})!\n"
            f"Symbol: {t['symbol']}\n"
            f"Entry: ${entry_prem} -> Exit: ${exit_premium}\n"
            f"Net PnL: ${net_pnl} USD\n"
            f"Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        send_telegram(msg)

        # Reset bot state
        self.state = "IDLE"
        self.active_trade = {}

if __name__ == "__main__":
    bot = DeltaDeepITMBot()
    bot.run()
