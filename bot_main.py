import time
import datetime
import threading
import requests
import pandas as pd
from config import (
    SYMBOL_SPOT, FIXED_SIZE_BTC, SL_POINTS, TP1_POINTS, 
    MAX_HOLDING_MINUTES, DRY_RUN, ENABLE_TELEGRAM, 
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ONE_TRADE_PER_DAY, CLOSE_FULL_AT_TP1
)
from delta_client import DeltaClient
from strategy import evaluate_market_setup, find_best_deep_itm_contract
from indicators import calculate_ema, get_liquidity_levels

def send_telegram(msg: str, with_keyboard: bool = True):
    """Send message to Telegram and optionally attach Report button."""
    try:
        print(f"[ALERT] {msg.encode('ascii', 'replace').decode('ascii')}")
    except Exception:
        pass
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": msg
            }
            if with_keyboard:
                payload["reply_markup"] = {
                    "keyboard": [[{"text": "📊 Report / Status"}]],
                    "resize_keyboard": True
                }
            resp = requests.post(url, json=payload, timeout=10).json()
            if resp.get('ok'):
                return resp['result']['message_id']
        except Exception as e:
            print(f"[Telegram Send Error] {e}")
    return None

def edit_telegram(msg: str, message_id: int):
    """Edit an existing Telegram message in-place to avoid chat spam!"""
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and message_id:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": message_id,
                "text": msg
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[Telegram Edit Error] {e}")

class DeltaDeepITMBot:
    def __init__(self):
        self.client = DeltaClient()
        self.state = "IDLE"  # "IDLE", "IN_TRADE_LEG1", "IN_TRADE_RUNNER"
        self.active_trade = {}
        self.last_traded_date = None
        self.live_msg_id = None
        
        print("="*65)
        print("[INIT] DELTA EXCHANGE BTC DEEP ITM OPTION BUYING BOT INITIALIZED")
        print(f"Mode: {'DRY RUN (PAPER TRADING)' if DRY_RUN else 'LIVE TRADING'}")
        print(f"Risk per Trade: $300 USD | Fixed Size: {FIXED_SIZE_BTC} BTC")
        print(f"SL: -{SL_POINTS} pts | TP1: +{TP1_POINTS} pts (1:2 RR)")
        print(f"1 Trade Per Day Rule: {'ENABLED' if ONE_TRADE_PER_DAY else 'DISABLED'}")
        print("="*65)

        # Start interactive Telegram command listener thread
        if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN:
            self.listener_thread = threading.Thread(target=self._telegram_listener, daemon=True)
            self.listener_thread.start()
            print("[Telegram] Interactive command listener started (supports /report, /status, button).")

    def _telegram_listener(self):
        """Background thread listening for user commands like /report or button tap."""
        last_update_id = 0
        get_updates_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        
        while True:
            try:
                params = {"offset": last_update_id + 1, "timeout": 20}
                res = requests.get(get_updates_url, params=params, timeout=25).json()
                if res.get('ok'):
                    for update in res.get('result', []):
                        last_update_id = update['update_id']
                        msg = update.get('message', {})
                        text = msg.get('text', '').strip()
                        sender_chat = str(msg.get('chat', {}).get('id', ''))
                        
                        # Only respond to authorized user chat ID
                        if sender_chat == str(TELEGRAM_CHAT_ID):
                            lower = text.lower()
                            if any(cmd in lower for cmd in ['report', 'status', 'pnl', '/report', '/status', '/start']):
                                self._handle_user_report_request()
            except Exception as e:
                time.sleep(5)
            time.sleep(1)

    def _handle_user_report_request(self):
        """Generates instant report or explains why no setup is triggered right now."""
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_dt + datetime.timedelta(hours=5, minutes=30)
        
        if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"] and self.active_trade:
            t = self.active_trade
            sym = t['symbol']
            now_ts = int(time.time())
            minutes_held = (now_ts - t['entry_time_ts']) // 60
            
            # Fetch latest mark price
            ticker = self.client._request('GET', f'/v2/tickers/{sym}', auth=False)
            curr_prem = t['entry_premium']
            if ticker and ticker.get('result'):
                curr_prem = float(ticker['result'].get('mark_price', curr_prem))
                
            diff = round((curr_prem - t['entry_premium']) * t['size'], 2)
            pct = round((curr_prem - t['entry_premium']) / t['entry_premium'] * 100, 2) if t['entry_premium'] > 0 else 0.0
            icon = "🟢" if diff >= 0 else "🔴"
            
            report = (
                f"📊 LIVE POSITION REPORT\n"
                f"------------------------------------\n"
                f"Contract: {sym}\n"
                f"Type: {t['trade_type']} | Strike: ${t['strike']}\n"
                f"Entry Price: ${t['entry_premium']:,.2f}\n"
                f"Current Price: ${curr_prem:,.2f}\n"
                f"{icon} Running PnL: {diff:+,.2f} USD ({pct:+.2f}%)\n"
                f"Target 1 (+600): ${t['tp1_prem']:,.2f}\n"
                f"Stop Loss (-300): ${t['sl_prem']:,.2f}\n"
                f"Holding Time: {minutes_held}m / Max {MAX_HOLDING_MINUTES}m\n"
                f"Checked At: {now_ist.strftime('%H:%M:%S IST')}"
            )
            send_telegram(report)
        else:
            # No open position: generate Market Diagnostics
            diagnostics = self._get_market_diagnostics(now_dt, now_ist)
            send_telegram(diagnostics)

    def _get_market_diagnostics(self, now_dt: datetime.datetime, now_ist: datetime.datetime) -> str:
        """Analyzes market condition and explains why no setup is triggered."""
        now_ts = int(time.time())
        c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
        c_1m = self.client.get_candles(SYMBOL_SPOT, resolution="1m", start_ts=now_ts - 24 * 3600, end_ts=now_ts)
        
        if not c_1h or not c_1m:
            return "⚠️ Market data temporarily unavailable from exchange. Reconnecting..."
            
        df_1h = pd.DataFrame(c_1h)
        df_1m = pd.DataFrame(c_1m)
        
        df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
        latest_1h = df_1h.iloc[-1]
        is_bullish = latest_1h['close'] > latest_1h['ema20']
        trend_str = "🟢 BULLISH (Above 20 EMA)" if is_bullish else "🔴 BEARISH (Below 20 EMA)"
        
        levels = get_liquidity_levels(df_1m, now_ts)
        last_1m = df_1m.iloc[-1]
        spot = float(last_1m['close'])
        
        ah = levels.get('asian_high', 'N/A')
        al = levels.get('asian_low', 'N/A')
        
        # Determine why setup hasn't triggered
        reason = []
        if ONE_TRADE_PER_DAY and self.last_traded_date == now_ist.date():
            reason.append("• 1 Trade Per Day Rule: Today's trade quota is already completed. Next trade allowed tomorrow.")
        else:
            if is_bullish:
                reason.append(f"• 1h Trend is Bullish: Waiting for a liquidity sweep below Asian Low (${al}) with green candle close above Asian Low to BUY CALL.")
            else:
                reason.append(f"• 1h Trend is Bearish: Waiting for a liquidity sweep above Asian High (${ah}) with red candle close below Asian High to BUY PUT.")
                
        reason_str = "\n".join(reason)
        quota_str = "1 / 1 (Completed for today)" if (self.last_traded_date == now_ist.date()) else "0 / 1 (Ready to trade)"
        
        diag_msg = (
            f"🔍 MARKET SCAN STATUS (NO OPEN POSITION)\n"
            f"------------------------------------\n"
            f"💰 BTC Spot: ${spot:,.2f}\n"
            f"📈 1-Hour Trend: {trend_str}\n"
            f"   (1h 20 EMA: ${latest_1h['ema20']:,.2f})\n"
            f"🎯 Setup: Asian Liquidity Sweep (SMC Pure)\n"
            f"🌏 Asian Session Range (05:30 - 13:30 IST):\n"
            f"   • High: ${ah}\n"
            f"   • Low:  ${al}\n"
            f"🎯 Today's Quota: {quota_str}\n"
            f"------------------------------------\n"
            f"📋 Why No Trade Right Now?\n"
            f"{reason_str}\n"
            f"------------------------------------\n"
            f"⏳ Bot automatically evaluates setup at each 1-minute candle close (:00)."
        )
        return diag_msg

    def run(self):
        last_checked_candle_ts = 0

        while True:
            try:
                now_ts = int(time.time())
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                now_ist = now_dt + datetime.timedelta(hours=5, minutes=30)

                # ==========================================
                # 1. SETUP SCANNER (Runs at 1-Minute Candle Close)
                # ==========================================
                is_1m_close = (now_dt.second <= 6)

                if self.state == "IDLE" and is_1m_close:
                    current_1m_boundary = (now_ts // 60) * 60
                    if current_1m_boundary > last_checked_candle_ts:
                        last_checked_candle_ts = current_1m_boundary
                        self._scan_and_execute_setup(now_ts, now_dt, now_ist)

                # ==========================================
                # 2. ACTIVE TRADE MANAGER (Live In-Place Updates)
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
        if ONE_TRADE_PER_DAY and self.last_traded_date == now_ist.date():
            print(f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}] 1-Trade-Per-Day rule active: already completed today's trade. Scanning will resume tomorrow.")
            return

        print(f"\n[{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}] Checking 1-minute & 1-hour market setup...")
        
        # Fetch 1h and 1m spot candles
        c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
        c_1m = self.client.get_candles(SYMBOL_SPOT, resolution="1m", start_ts=now_ts - 24 * 3600, end_ts=now_ts)

        if not c_1h or not c_1m:
            print("[Warning] Incomplete candles returned from exchange.")
            return

        df_1h = pd.DataFrame(c_1h)
        df_1m = pd.DataFrame(c_1m)

        trade_type = evaluate_market_setup(df_1h, df_1m)
        if not trade_type:
            print("Setup status: Neutral / No trigger found.")
            return

        # Setup Confirmed!
        spot_open = float(c_1m[-1]['close'])
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
        entry_premium = float(opt_candles[-1]['open']) if opt_candles else (5000.0 + spot_open * 0.01)

        # Execute Entry Order
        order_res = self.client.place_order(product_id=prod_id, size=FIXED_SIZE_BTC, side="buy", order_type="market_order")

        if not order_res or not order_res.get('success', False):
            err_code = 'No response'
            if order_res and isinstance(order_res, dict):
                err_code = order_res.get('error', {}).get('code', str(order_res))
            print(f"[Order Failed] Delta API rejected order: {err_code}")
            send_telegram(f"⚠️ SIGNAL DETECTED ({trade_type}) BUT ORDER REJECTED BY DELTA!\nReason: {err_code}\nPlease check your Delta Exchange API Key / IP Whitelist settings.")
            return

        # Set Trade State
        self.state = "IN_TRADE_LEG1"
        self.last_traded_date = now_ist.date()
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

        # Send initial live trade message and store message_id for in-place edits (ZERO SPAM!)
        msg = (
            f"🎯 NEW TRADE OPENED!\n"
            f"------------------------------------\n"
            f"Type: {trade_type} | Symbol: {symbol}\n"
            f"Strike: ${strike} | Entry Prem: ${entry_premium:,.2f}\n"
            f"Stop Loss: ${self.active_trade['sl_prem']} (-$300)\n"
            f"Target 1: ${self.active_trade['tp1_prem']} (+$600 / 1:2 RR)\n"
            f"Time: {self.active_trade['entry_ist']}\n"
            f"------------------------------------\n"
            f"🔄 Live PnL will update in-place in this message below..."
        )
        self.live_msg_id = send_telegram(msg)

    def _manage_active_trade(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        t = self.active_trade
        sym = t['symbol']
        prod_id = t['product_id']

        minutes_held = (now_ts - t['entry_time_ts']) // 60

        # SAFETY CHECK: Detect if user manually closed position on Delta Exchange UI
        actual_pos = self.client.get_open_position(prod_id)
        if actual_pos <= 0:
            print(f"[MANUAL CLOSE DETECTED] Position on {sym} was closed manually on Delta UI! Returning to IDLE.")
            manual_msg = (
                f"⚠️ POSITION MANUALLY CLOSED\n"
                f"------------------------------------\n"
                f"Contract: {sym}\n"
                f"Action: Closed manually by user on Delta Exchange UI.\n"
                f"Status: Bot safely returned to IDLE (No duplicate orders will be placed)."
            )
            if self.live_msg_id:
                edit_telegram(manual_msg, self.live_msg_id)
            send_telegram(manual_msg)
            self.state = "IDLE"
            self.active_trade = {}
            self.live_msg_id = None
            return

        opt_candles = self.client.get_candles(f"MARK:{sym}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
        if not opt_candles:
            return

        latest_c = opt_candles[-1]
        curr_low = float(latest_c['low'])
        curr_high = float(latest_c['high'])
        curr_open = float(latest_c['open'])

        # UPDATE LIVE MESSAGE IN-PLACE EVERY 20 SECONDS (ZERO SPAM!)
        last_pnl_alert = t.get('last_pnl_alert_ts', 0)
        if now_ts - last_pnl_alert >= 20 and self.live_msg_id:
            t['last_pnl_alert_ts'] = now_ts
            curr_diff = round((curr_open - t['entry_premium']) * t['size'], 2)
            pct = round((curr_open - t['entry_premium']) / t['entry_premium'] * 100, 2) if t['entry_premium'] > 0 else 0.0
            icon = "🟢" if curr_diff >= 0 else "🔴"
            
            updated_msg = (
                f"🎯 ACTIVE TRADE (LIVE IN-PLACE TRACKING)\n"
                f"------------------------------------\n"
                f"Contract: {sym}\n"
                f"Entry Price: ${t['entry_premium']:,.2f}\n"
                f"Current Price: ${curr_open:,.2f}\n"
                f"{icon} Running PnL: {curr_diff:+,.2f} USD ({pct:+.2f}%)\n"
                f"Target 1: ${t['tp1_prem']:,.2f} | SL: ${t['sl_prem']:,.2f}\n"
                f"Held: {minutes_held}m / Max {MAX_HOLDING_MINUTES}m\n"
                f"Last Tick: {now_ist.strftime('%H:%M:%S IST')}"
            )
            edit_telegram(updated_msg, self.live_msg_id)

        # 1. Stop Loss Hit (-300 pts)
        if curr_low <= t['sl_prem']:
            exit_prem = t['sl_prem'] if curr_open > t['sl_prem'] else curr_open
            self._close_position(exit_prem, "STOP_LOSS_HIT", now_ist)
            return

        # 2. Target 1 Hit (+600 pts)
        if curr_high >= t['tp1_prem']:
            if CLOSE_FULL_AT_TP1:
                print(f"[TP1] TARGET 1 HIT at ${t['tp1_prem']}! Booking 100% quantity...")
                exit_prem = t['tp1_prem'] if curr_open < t['tp1_prem'] else curr_open
                self._close_position(exit_prem, "TARGET_1_HIT", now_ist)
                return
            else:
                print(f"[TP1] TARGET 1 HIT at ${t['tp1_prem']}! Booking 50% quantity...")
                self.client.place_order(product_id=prod_id, size=t['size'] * 0.5, side="sell", order_type="market_order", reduce_only=True)
                t['sl_prem'] = t['entry_premium']
                t['tp1_booked_prem'] = t['tp1_prem']
                self.state = "IN_TRADE_RUNNER"
                send_telegram(f"✅ TARGET 1 BOOKED on {sym} at ${t['tp1_prem']} (+50% / +$300 gain)! Runner 50% trailing with Breakeven SL (${t['entry_premium']}).")
                return

        # 3. Time Stop (4 Hours)
        if minutes_held >= MAX_HOLDING_MINUTES:
            self._close_position(curr_open, "TIME_STOP_4H", now_ist)

    def _close_position(self, exit_premium: float, reason: str, now_ist: datetime.datetime):
        t = self.active_trade
        remaining_size = t['size'] if self.state == "IN_TRADE_LEG1" else t['size'] * 0.5
        
        # Check actual open position from Delta before sending exit order
        actual_pos = self.client.get_open_position(t['product_id'])
        if actual_pos > 0:
            close_sz = min(remaining_size, actual_pos)
            # Place closing order with reduce_only=True so it NEVER opens a short position!
            self.client.place_order(product_id=t['product_id'], size=close_sz, side="sell", order_type="market_order", reduce_only=True)

        entry_prem = t['entry_premium']
        gross_pnl = (exit_premium - entry_prem) * t['size']
        spot_exit = self.client.get_spot_price(SYMBOL_SPOT)
        fees = (t['btc_spot_entry'] + spot_exit) * t['size'] * 0.0001
        net_pnl = round(gross_pnl - fees, 2)

        icon = "✅" if net_pnl >= 0 else "🛑"
        final_msg = (
            f"🏁 TRADE CLOSED ({reason})!\n"
            f"------------------------------------\n"
            f"Symbol: {t['symbol']}\n"
            f"Entry: ${entry_prem:,.2f} -> Exit: ${exit_premium:,.2f}\n"
            f"{icon} Net PnL: {net_pnl:+,.2f} USD\n"
            f"Closed At: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        
        # Update the live message to final status, then send fresh closing alert
        if self.live_msg_id:
            edit_telegram(final_msg, self.live_msg_id)
        send_telegram(final_msg)

        # Reset bot state
        self.state = "IDLE"
        self.active_trade = {}
        self.live_msg_id = None

if __name__ == "__main__":
    bot = DeltaDeepITMBot()
    bot.run()
