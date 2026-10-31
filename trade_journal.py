import os
import sys
import pandas as pd
import datetime
import requests
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# Dynamically resolve file paths for both Windows local and Render Linux
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "trade_journal.csv")
EXCEL_FILE = os.path.join(BASE_DIR, "Trade_Journal_Master.xlsx")

# Also save directly to Desktop if running locally on Windows
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
if not os.path.exists(DESKTOP_DIR):
    DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
DESKTOP_EXCEL = os.path.join(DESKTOP_DIR, "Trade_Journal_Master.xlsx") if os.path.exists(DESKTOP_DIR) else None

INITIAL_TRADES = [
    {
        "trade_id": "TRD-001",
        "date": "2026-10-28",
        "entry_time_ist": "2026-10-28 17:45:07",
        "setup_type": "Priority 1 (SMC Sweep Reversal)",
        "side": "BUY_PUT",
        "symbol": "P-BTC-83000-291026",
        "spot_entry": 80869.0,
        "entry_premium": 2168.45,
        "exit_time_ist": "2026-10-28 19:00:51",
        "spot_exit": 80680.0,
        "exit_premium": 2378.25,
        "exit_reason": "TRAILING_SL_HIT",
        "duration_min": 75,
        "pts_move": 209.80,
        "size_btc": 1.0,
        "pnl_usd": 193.65,
        "pnl_inr": 16266.60,
        "cum_pnl_usd": 193.65,
        "cum_pnl_inr": 16266.60,
        "status": "WIN",
        "notes": "BTC swept liquidity above $80,850, rejected at 15m EMA20. Put premium surged +209.8 pts. Trailing SL locked profit at $2,378.25."
    },
    {
        "trade_id": "TRD-002",
        "date": "2026-10-29",
        "entry_time_ist": "2026-10-29 00:00:05",
        "setup_type": "Priority 1 (SMC Sweep Reversal)",
        "side": "BUY_CALL",
        "symbol": "C-BTC-79200-291026",
        "spot_entry": 80945.5,
        "entry_premium": 1837.04,
        "exit_time_ist": "2026-10-29 00:06:20",
        "spot_exit": 81027.0,
        "exit_premium": 1945.89,
        "exit_reason": "TRAILING_SL_HIT",
        "duration_min": 6,
        "pts_move": 108.85,
        "size_btc": 1.0,
        "pnl_usd": 92.65,
        "pnl_inr": 7782.60,
        "cum_pnl_usd": 286.30,
        "cum_pnl_inr": 24049.20,
        "status": "WIN",
        "notes": "Midnight session liquidity sweep. Spot surged +263 pts instantly. Trailing SL triggered at +200 pts and secured +$92.65 profit."
    },
    {
        "trade_id": "TRD-003",
        "date": "2026-10-29",
        "entry_time_ist": "2026-10-29 22:15:03",
        "setup_type": "Priority 2 (SMC OB+FVG Retest)",
        "side": "BUY_CALL",
        "symbol": "C-BTC-79600-301026",
        "spot_entry": 81391.0,
        "entry_premium": 1890.00,
        "exit_time_ist": "2026-10-29 23:11:58",
        "spot_exit": 80852.0,
        "exit_premium": 1380.00,
        "exit_reason": "SWING_SL_HIT",
        "duration_min": 56,
        "pts_move": -510.00,
        "size_btc": 0.2,
        "pnl_usd": -105.25,
        "pnl_inr": -8841.00,
        "cum_pnl_usd": 181.05,
        "cum_pnl_inr": 15208.20,
        "status": "LOSS",
        "notes": "15m Bullish OB retest (0.2 BTC lot size). Rolled into 23:00 trap hour. Disciplined Swing SL cut position at -$105.25, avoiding -$830 crash."
    },
    {
        "trade_id": "TRD-004",
        "date": "2026-10-30",
        "entry_time_ist": "2026-10-30 17:45:00",
        "setup_type": "Priority 2 (SMC OB+FVG Retest)",
        "side": "BUY_PUT",
        "symbol": "P-BTC-79600-311026",
        "spot_entry": 77432.5,
        "entry_premium": 1960.71,
        "exit_time_ist": "2026-10-30 18:42:00",
        "spot_exit": 77323.5,
        "exit_premium": 2143.62,
        "exit_reason": "DELTA_REJECTED (MAX_OI)",
        "duration_min": 57,
        "pts_move": 0.0,
        "size_btc": 0.0,
        "pnl_usd": 0.0,
        "pnl_inr": 0.0,
        "cum_pnl_usd": 181.05,
        "cum_pnl_inr": 15208.20,
        "status": "REJECTED",
        "notes": "Delta rejected order due to 100% max open interest on Strike 79600. Forward market dumped +209 pts (+$182.91 USD). Multi-strike fallback added."
    }
]

def load_all_trades():
    """Load existing trades or seed initial ones."""
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            return df.to_dict(orient='records')
        except Exception:
            pass
    pd.DataFrame(INITIAL_TRADES).to_csv(CSV_FILE, index=False)
    return INITIAL_TRADES

def generate_master_excel(trades=None):
    """Build a beautifully formatted institutional Excel Master Trade Journal."""
    if trades is None:
        trades = load_all_trades()

    wb = Workbook()

    # ----------------------------------------------------
    # SHEET 1: EXECUTIVE DASHBOARD
    # ----------------------------------------------------
    ws_dash = wb.active
    ws_dash.title = "Executive Summary"
    ws_dash.views.sheetView[0].showGridLines = True

    # Title Banner
    ws_dash.merge_cells("A1:G1")
    title_cell = ws_dash["A1"]
    title_cell.value = "DELTA DEEP ITM TRADING BOT - MASTER JOURNAL DASHBOARD"
    title_cell.font = Font(name="Segoe UI", size=16, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws_dash.row_dimensions[1].height = 42

    # Subtitle
    ws_dash.merge_cells("A2:G2")
    sub_cell = ws_dash["A2"]
    now_str = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S IST')
    sub_cell.value = f"Automated Institutional SMC Strategy Tracker | Auto-Updated: {now_str}"
    sub_cell.font = Font(name="Segoe UI", size=10, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws_dash.row_dimensions[2].height = 20

    # Metrics
    completed = [t for t in trades if t.get('status') in ['WIN', 'LOSS']]
    wins = [t for t in completed if t.get('status') == 'WIN']
    losses = [t for t in completed if t.get('status') == 'LOSS']
    rejected = [t for t in trades if t.get('status') == 'REJECTED']

    total_completed = len(completed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_completed * 100.0) if total_completed > 0 else 0.0

    total_pnl_usd = sum(float(t.get('pnl_usd', 0)) for t in completed)
    total_pnl_inr = sum(float(t.get('pnl_inr', 0)) for t in completed)

    gross_profit = sum(float(t.get('pnl_usd', 0)) for t in wins)
    gross_loss = abs(sum(float(t.get('pnl_usd', 0)) for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

    # KPI Top Cards
    cards = [
        ("Total Trades Formed", len(trades), "4472C4"),
        ("Executed Trades", total_completed, "2F5597"),
        ("Win Rate %", f"{win_rate:.1f}%", "385723" if win_rate >= 50 else "C00000"),
        ("Net PnL (USD)", f"${total_pnl_usd:+,.2f}", "385723" if total_pnl_usd >= 0 else "C00000"),
        ("Net PnL (INR)", f"Rs. {total_pnl_inr:+,.0f}", "385723" if total_pnl_inr >= 0 else "C00000"),
        ("Profit Factor", f"{profit_factor:.2f}", "385723" if profit_factor >= 1.5 else "7030A0")
    ]

    col_idx = 1
    for label, val, color_hex in cards:
        c_label = ws_dash.cell(row=4, column=col_idx, value=label)
        c_label.font = Font(name="Segoe UI", size=9, bold=True, color="595959")
        c_label.alignment = Alignment(horizontal="center", vertical="center")

        c_val = ws_dash.cell(row=5, column=col_idx, value=val)
        c_val.font = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
        c_val.fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        c_val.alignment = Alignment(horizontal="center", vertical="center")

        ws_dash.column_dimensions[get_column_letter(col_idx)].width = 21
        col_idx += 1

    ws_dash.row_dimensions[4].height = 24
    ws_dash.row_dimensions[5].height = 36

    # Breakdown Section
    ws_dash.cell(row=8, column=1, value="PERFORMANCE METRIC DETAILS").font = Font(name="Segoe UI", size=11, bold=True, color="1F4E79")
    breakdown_data = [
        ("Winning Trades", win_count, f"{gross_profit:+,.2f} USD (High Momentum Exits)"),
        ("Losing Trades", loss_count, f"-{gross_loss:,.2f} USD (Disciplined Swing SL Cut)"),
        ("Rejected / Filtered Trades", len(rejected), "Protected from bad fills (Auto-Fallback active)"),
        ("Average Winning Trade", f"${(gross_profit/win_count):+,.2f}" if win_count else "$0.00", "Strong asymmetric payoff"),
        ("Average Losing Trade", f"-${(gross_loss/loss_count):,.2f}" if loss_count else "$0.00", "Risk strictly bounded by SL"),
        ("Strategy Priorities", "P1 Reversal (81% WR) | P2 OB+FVG (65.5% WR)", "Institutional SMC rules")
    ]

    b_row = 9
    for m_label, m_val, m_note in breakdown_data:
        ws_dash.cell(row=b_row, column=1, value=m_label).font = Font(name="Segoe UI", size=10, bold=True)
        ws_dash.cell(row=b_row, column=2, value=str(m_val)).font = Font(name="Segoe UI", size=10)
        ws_dash.cell(row=b_row, column=3, value=m_note).font = Font(name="Segoe UI", size=10, italic=True, color="595959")
        b_row += 1

    # ----------------------------------------------------
    # SHEET 2: TRADE LOG
    # ----------------------------------------------------
    ws_log = wb.create_sheet(title="Trade Journal")
    ws_log.views.sheetView[0].showGridLines = True

    headers = [
        "Trade ID", "Date", "Entry IST", "Setup Type", "Direction", "Contract Symbol",
        "Spot Entry ($)", "Option Entry ($)", "Exit IST", "Spot Exit ($)", "Option Exit ($)",
        "Exit Reason", "Duration", "Pts Move", "Size (BTC)", "PnL ($)", "PnL (Rs.)",
        "Cum PnL ($)", "Cum PnL (Rs.)", "Status", "SMC Strategy Analysis & Notes"
    ]

    for c_i, h in enumerate(headers, start=1):
        cell = ws_log.cell(row=1, column=c_i, value=h)
        cell.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws_log.row_dimensions[1].height = 32

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    for r_i, t in enumerate(trades, start=2):
        status = str(t.get('status', ''))
        is_win = (status == "WIN")
        is_loss = (status == "LOSS")

        row_fill = PatternFill(start_color="F9FBFD" if r_i % 2 == 0 else "FFFFFF", fill_type="solid")

        row_values = [
            t.get('trade_id', f"TRD-{r_i-1:03d}"),
            t.get('date', ''),
            t.get('entry_time_ist', ''),
            t.get('setup_type', ''),
            t.get('side', ''),
            t.get('symbol', ''),
            float(t.get('spot_entry', 0.0)),
            float(t.get('entry_premium', 0.0)),
            t.get('exit_time_ist', ''),
            float(t.get('spot_exit', 0.0)),
            float(t.get('exit_premium', 0.0)),
            t.get('exit_reason', ''),
            f"{t.get('duration_min', 0)} mins",
            float(t.get('pts_move', 0.0)),
            float(t.get('size_btc', 1.0)),
            float(t.get('pnl_usd', 0.0)),
            float(t.get('pnl_inr', 0.0)),
            float(t.get('cum_pnl_usd', 0.0)),
            float(t.get('cum_pnl_inr', 0.0)),
            status,
            t.get('notes', '')
        ]

        for c_i, val in enumerate(row_values, start=1):
            cell = ws_log.cell(row=r_i, column=c_i, value=val)
            cell.font = Font(name="Segoe UI", size=9.5)
            cell.border = thin_border
            cell.fill = row_fill
            cell.alignment = Alignment(vertical="center")

            if c_i in [7, 8, 10, 11, 14, 16, 18]:
                cell.number_format = '$#,##0.00' if c_i in [7, 8, 10, 11, 16, 18] else '#,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif c_i in [17, 19]:
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif c_i in [1, 2, 3, 5, 9, 13, 15, 20]:
                cell.alignment = Alignment(horizontal="center", vertical="center")

            if c_i == 20:
                if is_win:
                    cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="274E13")
                    cell.fill = PatternFill(start_color="D9EAD3", fill_type="solid")
                elif is_loss:
                    cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="783F04")
                    cell.fill = PatternFill(start_color="FCE5CD", fill_type="solid")
                else:
                    cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="595959")
                    cell.fill = PatternFill(start_color="EFEFEF", fill_type="solid")

        ws_log.row_dimensions[r_i].height = 24

    for col in ws_log.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws_log.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 48)

    ws_log.column_dimensions["U"].width = 50

    try:
        wb.save(EXCEL_FILE)
    except PermissionError:
        print(f"[Notice] {EXCEL_FILE} is currently open in Excel.")
    if DESKTOP_EXCEL:
        try:
            wb.save(DESKTOP_EXCEL)
        except Exception as e:
            print(f"[Notice] Could not save to Desktop: {e}")
    return EXCEL_FILE

def record_trade_exit(trade_data: dict):
    """Called automatically by bot_main.py when any trade exits."""
    trades = load_all_trades()

    trade_num = len(trades) + 1
    trade_id = f"TRD-{trade_num:03d}"

    # Calculate cumulative PnL
    prev_cum_usd = float(trades[-1].get('cum_pnl_usd', 0.0)) if trades else 0.0
    prev_cum_inr = float(trades[-1].get('cum_pnl_inr', 0.0)) if trades else 0.0

    pnl_usd = float(trade_data.get('pnl_usd', 0.0))
    pnl_inr = float(trade_data.get('pnl_inr', pnl_usd * 84.0))

    cum_usd = round(prev_cum_usd + pnl_usd, 2)
    cum_inr = round(prev_cum_inr + pnl_inr, 2)

    new_trade = {
        "trade_id": trade_id,
        "date": trade_data.get('date', datetime.datetime.now().strftime('%Y-%m-%d')),
        "entry_time_ist": trade_data.get('entry_time_ist', ''),
        "setup_type": trade_data.get('setup_type', ''),
        "side": trade_data.get('side', ''),
        "symbol": trade_data.get('symbol', ''),
        "spot_entry": float(trade_data.get('spot_entry', 0.0)),
        "entry_premium": float(trade_data.get('entry_premium', 0.0)),
        "exit_time_ist": trade_data.get('exit_time_ist', ''),
        "spot_exit": float(trade_data.get('spot_exit', 0.0)),
        "exit_premium": float(trade_data.get('exit_premium', 0.0)),
        "exit_reason": trade_data.get('exit_reason', ''),
        "duration_min": int(trade_data.get('duration_min', 0)),
        "pts_move": float(trade_data.get('pts_move', 0.0)),
        "size_btc": float(trade_data.get('size_btc', 1.0)),
        "pnl_usd": pnl_usd,
        "pnl_inr": pnl_inr,
        "cum_pnl_usd": cum_usd,
        "cum_pnl_inr": cum_inr,
        "status": trade_data.get('status', 'WIN' if pnl_usd >= 0 else 'LOSS'),
        "notes": trade_data.get('notes', '')
    }

    trades.append(new_trade)
    pd.DataFrame(trades).to_csv(CSV_FILE, index=False)
    generate_master_excel(trades)
    print(f"[Trade Journal] Logged {trade_id} ({new_trade['symbol']}) with PnL: ${pnl_usd:+,.2f} USD")
    return new_trade

def get_journal_summary_text() -> str:
    """Returns quick text summary of journal for Telegram."""
    trades = load_all_trades()
    completed = [t for t in trades if t.get('status') in ['WIN', 'LOSS']]
    wins = [t for t in completed if t.get('status') == 'WIN']
    losses = [t for t in completed if t.get('status') == 'LOSS']
    total_usd = sum(float(t.get('pnl_usd', 0)) for t in completed)
    total_inr = sum(float(t.get('pnl_inr', 0)) for t in completed)

    return (
        f"📒 MASTER TRADE JOURNAL SNAPSHOT\n"
        f"------------------------------------\n"
        f"Total Formed:    {len(trades)} Trades\n"
        f"Executed Trades: {len(completed)} (Wins: {len(wins)} | Loss: {len(losses)})\n"
        f"Win Rate:        {(len(wins)/len(completed)*100.0 if completed else 0):.1f}%\n"
        f"Net Profit USD:  ${total_usd:+,.2f} USD\n"
        f"Net Profit INR:  Rs. {total_inr:+,.0f}\n"
        f"------------------------------------\n"
        f"Master Excel file niche bheji ja rahi hai... ⬇️"
    )

def send_journal_telegram_file(caption: str = ""):
    """Sends the master Excel file directly into Telegram."""
    from config import ENABLE_TELEGRAM, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if not (ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return

    excel_path = None
    for p in [DESKTOP_EXCEL, EXCEL_FILE]:
        if p and os.path.exists(p):
            try:
                with open(p, 'rb'):
                    excel_path = p
                    break
            except Exception:
                continue

    if not excel_path:
        print("[Telegram Notice] Excel file is currently open in Excel.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    cap = caption or "📒 DELTA BOT MASTER TRADE JOURNAL (Auto-Updated Excel File)"
    try:
        with open(excel_path, 'rb') as f:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': cap}, files={'document': f}, timeout=25)
    except Exception as e:
        print(f"[Telegram Document Error] {e}")

if __name__ == "__main__":
    generate_master_excel()
