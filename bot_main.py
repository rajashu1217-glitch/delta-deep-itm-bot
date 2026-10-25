import time
import datetime
import requests
import threading
import pandas as pd
from config import (
    SYMBOL_SPOT, FIXED_SIZE_BTC, TARGET_POINTS, 
    TRAILING_TRIGGER, TRAILING_LOCK_OFFSET,
    MAX_HOLDING_MINUTES, DRY_RUN, ENABLE_TELEGRAM, 
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, STATUS_INTERVAL_MINUTES,
    REVERSAL_EXPIRY_MODE, BREAKOUT_EXPIRY_MODE,
    SESSION_START_UTC, SESSION_END_UTC
)
from delta_client import DeltaClient
from strategy import evaluate_market_setup, find_best_contract, calculate_swing_sl
from indicators import calculate_ema, get_liquidity_levels

TELEGRAM_KEYBOARD = {
    "keyboard": [
        [{"text": "📊 Report / Status"}, {"text": "🔍 Check Setup Now"}],
        [{"text": "💰 Live PnL"}, {"text": "🎯 Levels & Trend"}]
    ],
    "resize_keyboard": True,
    "persistent": True
}

def send_telegram(msg: str, with_keyboard: bool = True):
    """Send real-time alert to Telegram with interactive reply buttons."""
    try:
        print(f"[ALERT] {msg.encode('ascii', 'replace').decode('ascii')}")
    except Exception:
        pass
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
            if with_keyboard:
                payload["reply_markup"] = TELEGRAM_KEYBOARD
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[Telegram Error] {e}")

class DeltaDeepITMBot:
    def __init__(self):
        self.client = DeltaClient()
        self.state = "IDLE"  # IDLE, IN_TRADE_LEG1, IN_TRADE_RUNNER
        self.active_trade = {}
        
        # Dual-Quota Independent Trackers
        self.last_bo_trade_date = None   # 1 Breakout / Breakdown per day
        self.last_rev_trade_date = None  # 1 Reversal per day (NEVER blocked by breakout!)
        
        self.last_status_report_ts = 0

    def run(self):
        print("="*75)
        print("  Delta Exchange BTC Deep ITM Bot (Dual-Quota Master Setup)")
        print("  Architecture: 1 Breakout/Down per day + 1 Independent Reversal per day")
        
        # Auto-detect Public IP for easy Delta Whitelist verification
        try:
            import urllib.request
            public_ip = urllib.request.urlopen('https://api.ipify.org', timeout=5).read().decode('utf-8')
        except Exception:
            public_ip = "Unknown"

        print(f"  Public Outbound IP: {public_ip}")
        print(f"  Expiry Modes: Breakout = {BREAKOUT_EXPIRY_MODE} (No Theta Decay) | Reversal = {REVERSAL_EXPIRY_MODE}")
        print(f"  SL: Dynamic Swing High/Low | Trailing SL: +{TRAILING_TRIGGER} pts | Target: +{TARGET_POINTS} pts")
        print(f"  Mode: {'PAPER TRADING (DRY_RUN)' if DRY_RUN else 'LIVE TRADING ON DELTA EXCHANGE'}")
        print("="*75)

        # 1. Start Interactive 2-Way Telegram Command Listener
        if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            tg_thread = threading.Thread(target=self.run_telegram_listener, daemon=True)
            tg_thread.start()

        send_telegram(
            f"🤖 DELTA BOT STARTED!\n"
            f"Strategy: Dual-Quota (BO Weekly + Reversal {REVERSAL_EXPIRY_MODE})\n"
            f"Mode: {'DRY RUN (Paper)' if DRY_RUN else 'LIVE REAL ORDERS'}\n"
            f"🌐 Bot Public IP: {public_ip}\n"
            f"Trading Sessions: London + NY (13:30 to 02:30 IST)\n"
            f"Waiting for 15-minute candle close confirmation...\n\n"
            f"💡 Niche diye gaye buttons se kisi bhi waqt live status/audit report le sakte hain!"
        )

        last_checked_15m_boundary = 0

        while True:
            try:
                now_ts = int(time.time())
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                now_ist = now_dt + datetime.timedelta(hours=5, minutes=30)

                # ==========================================
                # 1. SETUP SCANNER (At 15-Minute Candle Close)
                # ==========================================
                is_15m_close = (now_dt.minute % 15 == 0 and now_dt.second <= 15)

                if is_15m_close:
                    current_15m_boundary = (now_ts // 900) * 900
                    if current_15m_boundary > last_checked_15m_boundary:
                        last_checked_15m_boundary = current_15m_boundary
                        self._scan_and_execute_setup(now_ts, now_dt, now_ist)

                # ==========================================
                # 2. ACTIVE TRADE MANAGER (Live In-Place Updates)
                # ==========================================
                if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"]:
                    self._manage_active_trade(now_ts, now_dt, now_ist)

                # ==========================================
                # 3. PERIODIC DIAGNOSTIC HEARTBEAT REPORT
                # ==========================================
                if (now_ts - self.last_status_report_ts) >= (STATUS_INTERVAL_MINUTES * 60):
                    self.last_status_report_ts = now_ts
                    self._send_status_heartbeat(now_ts, now_dt, now_ist)

                time.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user.")
                break
            except Exception as e:
                print(f"[Bot Loop Exception] {e}")
                time.sleep(10)

    # =========================================================================
    # 2-WAY INTERACTIVE TELEGRAM COMMAND SYSTEM & DETAILED SETUP AUDIT
    # =========================================================================
    def run_telegram_listener(self):
        """Dedicated background thread polling Telegram for user button clicks and questions."""
        print("[Telegram Listener] Interactive listener started...")
        last_update_id = 0
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        
        while True:
            try:
                params = {"offset": last_update_id + 1, "timeout": 10}
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        msg = update.get("message", {})
                        chat_id = str(msg.get("chat", {}).get("id"))
                        text = msg.get("text", "").strip()
                        if chat_id == str(TELEGRAM_CHAT_ID) and text:
                            threading.Thread(target=self.handle_telegram_command, args=(text,), daemon=True).start()
            except Exception as e:
                time.sleep(2)
            time.sleep(1)

    def generate_audit_status_report(self) -> str:
        """Generates exact 5-condition PASS/FAIL audit report matching verification specs."""
        now_ts = int(time.time())
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_dt + datetime.timedelta(hours=5, minutes=30)
        today_date = now_ist.date()

        # If already in a trade, return real-time position audit
        if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"]:
            t = self.active_trade
            sym = t['symbol']
            minutes_held = (now_ts - t['entry_time_ts']) // 60
            opt_candles = self.client.get_candles(f"MARK:{sym}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
            curr_prem = float(opt_candles[-1]['close']) if opt_candles else t['entry_premium']
            diff = round((curr_prem - t['entry_premium']) * t['size'], 2)
            pct = round((curr_prem - t['entry_premium']) / t['entry_premium'] * 100, 2) if t['entry_premium'] > 0 else 0.0
            icon = "🟢" if diff >= 0 else "🔴"
            spot_now = self.client.get_spot_price(SYMBOL_SPOT)
            spot_diff = spot_now - t['btc_spot_entry'] if t['trade_type'] == 'BUY_CALL' else t['btc_spot_entry'] - spot_now

            return (
                f"📊 LIVE ACTIVE TRADE AUDIT\n"
                f"====================================\n"
                f"Contract:      {sym} ({t['trade_type']})\n"
                f"Setup Type:    {t['setup_type']}\n"
                f"Spot Entry:    ${t['btc_spot_entry']:,.1f} ➔ Now: ${spot_now:,.1f} ({spot_diff:+,.1f} pts)\n"
                f"Option Prem:   ${t['entry_premium']:,.2f} ➔ Now: ${curr_prem:,.2f}\n"
                f"Unrealized:    {icon} ${diff:+,.2f} USD ({pct:+.2f}%)\n"
                f"Duration:      {minutes_held} mins / {MAX_HOLDING_MINUTES} mins max\n"
                f"Active SL:     ${t['sl_prem']:,.2f} ({'TRAILING LOCKED' if t['trailing_active'] else 'Swing SL'})\n"
                f"Target (+600): ${t['tp1_prem']:,.2f} (50% book + EMA trail)\n"
                f"====================================\n"
                f"Daily Quotas:  BO: {'1/1 (Done)' if self.last_bo_trade_date == today_date else '0/1 (Ready)'} | "
                f"REV: {'1/1 (Done)' if self.last_rev_trade_date == today_date else '0/1 (Ready)'}\n"
                f"Audit Status:  RUNNING LIVE RISK MANAGEMENT"
            )

        # Market scanning mode: evaluate 5 conditions
        c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
        c_15m = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 12 * 3600, end_ts=now_ts)

        if not c_1h or not c_15m:
            return "⚠️ Market candles fetching failed. Please check internet connection."

        df_1h = pd.DataFrame(c_1h)
        df_15m = pd.DataFrame(c_15m)
        df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
        df_15m['ema20'] = calculate_ema(df_15m['close'], 20)
        levels = get_liquidity_levels(df_15m, now_ts)

        last_15m = df_15m.iloc[-1]
        latest_1h = df_1h.iloc[-1]

        # 1. Trading hours (08:00 to 21:00 UTC)
        hour_utc = now_dt.hour
        r1_pass = (SESSION_START_UTC <= hour_utc <= SESSION_END_UTC)
        r1_txt = f"PASS ({now_dt.strftime('%H:%M')} UTC | 08:00 - 21:00 UTC)" if r1_pass else f"FAIL (Outside 08:00 - 21:00 UTC Window)"

        # 2. 1H Trend Bias
        trend_1h = 1 if latest_1h['close'] > latest_1h['ema20'] else -1
        r2_txt = f"PASS (Bullish +1 | 1H EMA: ${latest_1h['ema20']:,.1f})" if trend_1h == 1 else f"PASS (Bearish -1 | 1H EMA: ${latest_1h['ema20']:,.1f})"

        # 3. 15m Signal Candle
        c_open = float(last_15m['open'])
        c_close = float(last_15m['close'])
        c_high = float(last_15m['high'])
        c_low = float(last_15m['low'])
        is_green = c_close > c_open
        is_red = c_close < c_open
        r3_pass = (trend_1h == 1 and is_green) or (trend_1h == -1 and is_red)
        r3_txt = f"PASS ({'Green Candle' if is_green else 'Red Candle'})" if r3_pass else f"WAITING ({'Red against Bull trend' if trend_1h == 1 else 'Green against Bear trend'})"

        # 4. 15m 20-EMA Alignment
        ema15_val = float(last_15m['ema20'])
        r4_pass = (c_close > ema15_val) if trend_1h == 1 else (c_close < ema15_val)
        r4_txt = f"PASS (Close ${c_close:,.1f} > 15m EMA ${ema15_val:,.1f})" if (c_close > ema15_val) else f"PASS (Close ${c_close:,.1f} < 15m EMA ${ema15_val:,.1f})"
        if not r4_pass:
            r4_txt = f"WAITING (Close ${c_close:,.1f} vs 15m EMA ${ema15_val:,.1f})"

        # 5. SMC Levels
        al = levels.get('asian_low', 0)
        ah = levels.get('asian_high', 0)
        pdl = levels.get('pdl', 0)
        pdh = levels.get('pdh', 0)
        support = min([x for x in [al, pdl] if x])
        resistance = max([x for x in [ah, pdh] if x])

        dist_res = resistance - c_close
        dist_sup = c_close - support

        trade_type, setup_type = evaluate_market_setup(df_1h, df_15m, levels, hour_utc)

        if trade_type:
            setup_status = f"🔥 100% MATCH! {setup_type} ({trade_type}) forming right now!"
        else:
            setup_status = (
                f"⏳ NO SETUP YET (Inside SMC Range)\n"
                f"   • Resistance: ${resistance:,.1f} (Breakout need: +{dist_res:.1f} pts)\n"
                f"   • Support:    ${support:,.1f} (Reversal need: Sweep -{dist_sup:.1f} pts & Reclaim)"
            )

        bo_q = "1 / 1 (Done)" if self.last_bo_trade_date == today_date else "0 / 1 (Ready)"
        rev_q = "1 / 1 (Done)" if self.last_rev_trade_date == today_date else "0 / 1 (Ready - Never Blocked)"

        report = (
            f"📋 DETAILED SETUP LOGIC AUDIT & STATUS\n"
            f"====================================\n"
            f"Timestamp (IST):  {now_ist.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Current Spot:     ${c_close:,.1f} USD\n"
            f"15m Candle OHLC:  O: {c_open:.0f} | H: {c_high:.0f} | L: {c_low:.0f} | C: {c_close:.0f}\n"
            f"Candle Direction: {'🟢 GREEN (Close > Open)' if is_green else '🔴 RED (Close < Open)'}\n"
            f"------------------------------------\n"
            f"SETUP CONDITIONS VERIFICATION:\n"
            f"1. Active Hours:  {r1_txt}\n"
            f"2. 1H Trend Bias: {r2_txt}\n"
            f"3. 15m Signal:    {r3_txt}\n"
            f"4. 15m EMA20:     {r4_txt}\n"
            f"5. SMC Trigger:   {setup_status}\n"
            f"------------------------------------\n"
            f"DAILY QUOTAS:     Breakout: {bo_q} | Reversal: {rev_q}\n"
            f"BOT STATE:        {self.state} (Scanning every 15m close)"
        )
        return report

    def handle_telegram_command(self, text: str):
        """Processes user clicks on Telegram buttons and questions in chat."""
        t_lower = text.lower().strip()
        print(f"[Telegram User Message] {text}")

        # 1. REPORT / STATUS BUTTON
        if any(k in t_lower for k in ["report", "status", "/status", "/report"]):
            report = self.generate_audit_status_report()
            send_telegram(report)
            return

        # 2. CHECK SETUP BUTTON
        if any(k in t_lower for k in ["check", "setup", "/check"]):
            report = self.generate_audit_status_report()
            send_telegram(f"🔍 REAL-TIME SETUP AUDIT:\n\n{report}")
            return

        # 3. PNL BUTTON
        if any(k in t_lower for k in ["pnl", "/pnl", "profit", "loss"]):
            today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%d-%b-%Y")
            if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"]:
                report = self.generate_audit_status_report()
                send_telegram(report)
            else:
                send_telegram(
                    f"💰 TODAY'S PNL REPORT ({today_str})\n"
                    f"------------------------------------\n"
                    f"Active Trade:    None (IDLE)\n"
                    f"Breakout Quota:  {'1 Done' if self.last_bo_trade_date == datetime.datetime.now(datetime.timezone.utc).date() else '0 Done (1 Available)'}\n"
                    f"Reversal Quota:  {'1 Done' if self.last_rev_trade_date == datetime.datetime.now(datetime.timezone.utc).date() else '0 Done (1 Available)'}\n"
                    f"Status:          Bot waiting for 15m confirmation to trade."
                )
            return

        # 4. LEVELS & TREND BUTTON
        if any(k in t_lower for k in ["level", "trend", "/levels", "support", "resistance"]):
            now_ts = int(time.time())
            c_15m = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 12 * 3600, end_ts=now_ts)
            c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
            if c_15m and c_1h:
                df_1h = pd.DataFrame(c_1h)
                df_15m = pd.DataFrame(c_15m)
                df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
                levels = get_liquidity_levels(df_15m, now_ts)
                spot = float(c_15m[-1]['close'])
                al = levels.get('asian_low', 0)
                ah = levels.get('asian_high', 0)
                pdl = levels.get('pdl', 0)
                pdh = levels.get('pdh', 0)
                sup = min([x for x in [al, pdl] if x])
                res = max([x for x in [ah, pdh] if x])
                trend = "BULLISH 🟢" if df_1h.iloc[-1]['close'] > df_1h.iloc[-1]['ema20'] else "BEARISH 🔴"
                send_telegram(
                    f"🎯 KEY SMC LEVELS & TREND\n"
                    f"------------------------------------\n"
                    f"Current Spot:      ${spot:,.1f}\n"
                    f"1H Trend:          {trend} (1H 20-EMA: ${df_1h.iloc[-1]['ema20']:,.1f})\n"
                    f"Asian Range:       High: ${ah:,.1f} | Low: ${al:,.1f}\n"
                    f"Previous Day (PD): High: ${pdh:,.1f} | Low: ${pdl:,.1f}\n"
                    f"Resistance:        ${res:,.1f} (+{res - spot:.1f} pts)\n"
                    f"Support:           ${sup:,.1f} (-{spot - sup:.1f} pts)\n"
                    f"------------------------------------\n"
                    f"Breakout Trigger: 15m close above ${res:,.1f}\n"
                    f"Reversal Trigger: Sweep below ${sup:,.1f} + Green reclaim"
                )
            return

        # 5. GENERAL CHAT / QUESTIONS IN CHAT
        report = self.generate_audit_status_report()
        ans = (
            f"🤖 Bot Response:\n\n"
            f"Aapne poocha: \"{text}\"\n\n"
            f"📌 Current Market Situation:\n"
            f"{report}\n\n"
            f"💡 Trade Kab Aayega?\n"
            f"• Breakout: Jab 15m candle Resistance ke upar close ho.\n"
            f"• Reversal: Jab Support ke neeche liquidity sweep karke green candle reclaim kare."
        )
        send_telegram(ans)

    # =========================================================================
    # SETUP SCANNER & ORDER EXECUTION
    # =========================================================================
    def _scan_and_execute_setup(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        today_date = now_ist.date()

        # Fetch market candles
        c_1h = self.client.get_candles(SYMBOL_SPOT, resolution="1h", start_ts=now_ts - 36 * 3600, end_ts=now_ts)
        c_15m = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 12 * 3600, end_ts=now_ts)

        if not c_1h or not c_15m:
            return

        df_1h = pd.DataFrame(c_1h)
        df_15m = pd.DataFrame(c_15m)

        df_1h['ema20'] = calculate_ema(df_1h['close'], 20)
        df_15m['ema20'] = calculate_ema(df_15m['close'], 20)

        levels = get_liquidity_levels(df_15m, now_ts)

        trade_type, setup_type = evaluate_market_setup(df_1h, df_15m, levels, now_dt.hour)
        if not trade_type:
            return

        # DUAL-QUOTA ENFORCEMENT:
        if setup_type == 'BREAKOUT':
            if self.last_bo_trade_date == today_date:
                return  # Daily breakout quota already used
            if self.state != "IDLE":
                return  # Can't enter breakout if already in an active trade

        elif setup_type == 'REVERSAL':
            if self.last_rev_trade_date == today_date:
                return  # Daily reversal quota already used
            # Reversal Priority: Reversal is NOT blocked if a breakout was completed earlier today!
            if self.state != "IDLE":
                print("[REVERSAL PRIORITY] Reversal formed while trade active! Closing previous trade to prioritize Reversal...")
                curr_open = float(c_15m[-1]['close'])
                self._close_position(curr_open, "REVERSED_BY_SMC_SWEEP", now_ist)

        # Setup Confirmed!
        spot_open = float(c_15m[-1]['close'])
        print(f"\n[SIGNAL CONFIRMED] {setup_type}: {trade_type} at Spot ${spot_open:,.1f}")

        # Calculate Price Action Swing Stop Loss
        sl_dist = calculate_swing_sl(df_15m, trade_type, spot_open, buffer=30.0)

        # Fetch active Delta Exchange options
        options = self.client.get_all_option_products()
        contract = find_best_contract(spot_open, trade_type, setup_type, options, now_dt)
        if not contract:
            print("[Error] No matching option contract found on Delta Exchange.")
            return

        symbol = contract['symbol']
        prod_id = contract['id']
        strike = float(contract.get('strike_price', 0))

        opt_candles = self.client.get_candles(f"MARK:{symbol}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
        entry_premium = float(opt_candles[-1]['close']) if opt_candles else float(contract.get('mark_price', 0))

        # Place Order
        order_res = self.client.place_order(product_id=prod_id, size=FIXED_SIZE_BTC, side="buy", order_type="market_order")
        print(f"[ORDER EXECUTED] {symbol} | Response: {order_res}")

        # Update Quota Tracker
        if setup_type == 'BREAKOUT':
            self.last_bo_trade_date = today_date
        elif setup_type == 'REVERSAL':
            self.last_rev_trade_date = today_date

        self.state = "IN_TRADE_LEG1"
        self.active_trade = {
            "symbol": symbol,
            "product_id": prod_id,
            "trade_type": trade_type,
            "setup_type": setup_type,
            "strike": strike,
            "size": FIXED_SIZE_BTC,
            "entry_time_ts": now_ts,
            "entry_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
            "entry_premium": entry_premium,
            "btc_spot_entry": spot_open,
            "sl_dist": sl_dist,
            "sl_prem": entry_premium - sl_dist,
            "tp1_prem": entry_premium + TARGET_POINTS,
            "peak_profit": 0.0,
            "trailing_active": False,
            "tp1_booked_prem": 0.0
        }

        msg = (
            f"🚀 NEW TRADE EXECUTED ({setup_type})!\n"
            f"Symbol: {symbol} ({trade_type})\n"
            f"Strike: ${strike:,.0f} (Deep ITM Delta ~0.85)\n"
            f"Spot Entry: ${spot_open:,.1f}\n"
            f"Entry Premium: ${entry_premium:,.2f}\n"
            f"PA Swing SL: ${self.active_trade['sl_prem']:,.2f} (-{sl_dist:.0f} pts)\n"
            f"Target (+{TARGET_POINTS:.0f}): ${self.active_trade['tp1_prem']:,.2f}\n"
            f"Trailing SL: Auto-activates after +{TRAILING_TRIGGER:.0f} pts profit!\n"
            f"Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        send_telegram(msg)

    def _manage_active_trade(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        t = self.active_trade
        sym = t['symbol']
        prod_id = t['product_id']
        minutes_held = (now_ts - t['entry_time_ts']) // 60

        opt_candles = self.client.get_candles(f"MARK:{sym}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
        if not opt_candles:
            return

        latest_c = opt_candles[-1]
        curr_low = float(latest_c['low'])
        curr_high = float(latest_c['high'])
        curr_open = float(latest_c['open'])
        curr_close = float(latest_c['close'])

        running_gain = curr_high - t['entry_premium']
        if running_gain > t['peak_profit']:
            t['peak_profit'] = running_gain

        # ==========================================
        # DYNAMIC TRAILING SL (After +200 pts)
        # ==========================================
        if t['peak_profit'] >= TRAILING_TRIGGER:
            trailing_sl = (t['entry_premium'] + t['peak_profit']) - TRAILING_LOCK_OFFSET
            if trailing_sl > t['sl_prem']:
                t['sl_prem'] = trailing_sl
                if not t['trailing_active']:
                    t['trailing_active'] = True
                    send_telegram(f"🛡️ TRAILING SL ACTIVATED on {sym}! Profit reached +{t['peak_profit']:.0f} pts. New SL locked at ${trailing_sl:,.2f}.")

        # ==========================================
        # LEG 1: CHECKING SL & TARGET
        # ==========================================
        if self.state == "IN_TRADE_LEG1":
            # 1. Stop Loss Hit
            if curr_low <= t['sl_prem']:
                exit_prem = t['sl_prem'] if curr_open > t['sl_prem'] else curr_open
                reason = "TRAILING_SL_HIT" if t['trailing_active'] else "SWING_SL_HIT"
                self._close_position(exit_prem, reason, now_ist)
                return

            # 2. Target Hit (+600 pts) -> Book 50%, runner trails on 15m EMA20
            if curr_high >= t['tp1_prem']:
                print(f"[TARGET HIT] Reached ${t['tp1_prem']}! Booking 50%...")
                self.client.place_order(product_id=prod_id, size=t['size'] * 0.5, side="sell", order_type="market_order")
                t['sl_prem'] = t['entry_premium'] # Move to Breakeven
                t['tp1_booked_prem'] = t['tp1_prem']
                self.state = "IN_TRADE_RUNNER"
                send_telegram(f"✅ TARGET BOOKED on {sym} at ${t['tp1_prem']} (+50% booked)! Runner trailing on 15m 20 EMA with Breakeven SL.")
                return

        # ==========================================
        # LEG 2: RUNNER TRAILING WITH 15m 20 EMA
        # ==========================================
        elif self.state == "IN_TRADE_RUNNER":
            if curr_low <= t['sl_prem']:
                runner_exit = t['sl_prem'] if curr_open > t['sl_prem'] else curr_open
                avg_exit = round(0.5 * t['tp1_booked_prem'] + 0.5 * runner_exit, 2)
                self._close_position(avg_exit, "RUNNER_BREAKEVEN", now_ist)
                return

            if now_dt.minute % 15 == 0 and now_dt.second <= 15:
                spot_c = self.client.get_candles(SYMBOL_SPOT, resolution="15m", start_ts=now_ts - 3600, end_ts=now_ts)
                if spot_c and len(spot_c) >= 20:
                    df_spot = pd.DataFrame(spot_c)
                    df_spot['ema20'] = calculate_ema(df_spot['close'], 20)
                    last_spot = df_spot.iloc[-1]
                    is_call = (t['trade_type'] == 'BUY_CALL')
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
        
        self.client.place_order(product_id=t['product_id'], size=remaining_size, side="sell", order_type="market_order")

        entry_prem = t['entry_premium']
        gross_pnl = (exit_premium - entry_prem) * t['size']
        spot_exit = self.client.get_spot_price(SYMBOL_SPOT)
        fees = (t['btc_spot_entry'] + spot_exit) * t['size'] * 0.0001
        net_pnl = round(gross_pnl - fees, 2)

        icon = "🟢" if net_pnl >= 0 else "🔴"
        msg = (
            f"🏁 TRADE CLOSED ({reason})!\n"
            f"Symbol: {t['symbol']} ({t['setup_type']})\n"
            f"Entry: ${entry_prem:,.2f} -> Exit: ${exit_premium:,.2f}\n"
            f"{icon} Net PnL: ${net_pnl:+,.2f} USD\n"
            f"Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        send_telegram(msg)

        self.state = "IDLE"
        self.active_trade = {}

    def _send_status_heartbeat(self, now_ts: int, now_dt: datetime.datetime, now_ist: datetime.datetime):
        today_date = now_ist.date()
        bo_status = "1 / 1 (Done)" if self.last_bo_trade_date == today_date else "0 / 1 (Ready)"
        rev_status = "1 / 1 (Done)" if self.last_rev_trade_date == today_date else "0 / 1 (Ready - Never Blocked)"

        if self.state in ["IN_TRADE_LEG1", "IN_TRADE_RUNNER"]:
            t = self.active_trade
            sym = t['symbol']
            minutes_held = (now_ts - t['entry_time_ts']) // 60
            opt_candles = self.client.get_candles(f"MARK:{sym}", resolution="1m", start_ts=now_ts - 180, end_ts=now_ts)
            curr_prem = float(opt_candles[-1]['close']) if opt_candles else t['entry_premium']
            diff = round((curr_prem - t['entry_premium']) * t['size'], 2)
            pct = round((curr_prem - t['entry_premium']) / t['entry_premium'] * 100, 2) if t['entry_premium'] > 0 else 0.0
            icon = "🟢" if diff >= 0 else "🔴"
            
            report = (
                f"📊 LIVE POSITION ({t['setup_type']})\n"
                f"------------------------------------\n"
                f"Contract: {sym} ({t['trade_type']})\n"
                f"Entry: ${t['entry_premium']:,.2f} | Current: ${curr_prem:,.2f}\n"
                f"Running PnL: {icon} ${diff:+,.2f} USD ({pct:+.2f}%)\n"
                f"Duration: {minutes_held} mins (Max: {MAX_HOLDING_MINUTES}m)\n"
                f"Active SL: ${t['sl_prem']:,.2f} | Target: ${t['tp1_prem']:,.2f}\n"
                f"Trailing: {'ACTIVE' if t['trailing_active'] else 'Waiting (+200 pts)'}\n"
                f"------------------------------------\n"
                f"Daily Quotas: BO: {bo_status} | REV: {rev_status}\n"
                f"Time: {now_ist.strftime('%H:%M:%S IST')}"
            )
        else:
            spot_p = self.client.get_spot_price(SYMBOL_SPOT)
            report = (
                f"💓 DELTA BOT HEARTBEAT\n"
                f"------------------------------------\n"
                f"Status: SCANNING FOR SETUPS\n"
                f"BTC Spot: ${spot_p:,.1f}\n"
                f"Breakout Quota: {bo_status}\n"
                f"Reversal Quota: {rev_status}\n"
                f"Time: {now_ist.strftime('%d-%b-%Y %H:%M:%S IST')}"
            )
        send_telegram(report)

if __name__ == "__main__":
    bot = DeltaDeepITMBot()
    bot.run()
