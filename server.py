import os
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from bot_main import DeltaDeepITMBot

# Initialize the Bot
bot_instance = DeltaDeepITMBot()

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        status_data = {
            "status": "online",
            "bot_state": bot_instance.state,
            "active_trade": bot_instance.active_trade,
            "message": "Delta Deep ITM Bot is running 24x7 on Render.com"
        }
        self.wfile.write(json.dumps(status_data, indent=2).encode('utf-8'))

    # UptimeRobot Free HEAD method support
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard HTTP access logs to keep terminal clean
        return

def run_http_server(port):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, StatusHandler)
    print(f"[RENDER] Web Health Server listening on port {port}...")
    httpd.serve_forever()

def keep_alive_self_ping():
    """Auto-pings itself every 10 minutes to prevent Render free tier from sleeping!"""
    import urllib.request
    import time
    time.sleep(30)
    url = os.getenv("RENDER_EXTERNAL_URL", "https://delta-btc-deep-itm-bot.onrender.com")
    while True:
        try:
            time.sleep(600) # Ping every 10 minutes
            with urllib.request.urlopen(url, timeout=15) as resp:
                print(f"[KEEP-ALIVE] Auto self-ping succeeded: status {resp.status}")
        except Exception as e:
            print(f"[KEEP-ALIVE] Ping exception: {e}")

if __name__ == "__main__":
    # 1. Start trading bot in a background thread
    bot_thread = threading.Thread(target=bot_instance.run, daemon=True)
    bot_thread.start()

    # 2. Start self-ping thread to keep Render awake 24x7
    pinger_thread = threading.Thread(target=keep_alive_self_ping, daemon=True)
    pinger_thread.start()
    
    # 3. Start HTTP server on Render's assigned port (default 10000)
    port = int(os.getenv("PORT", 10000))
    run_http_server(port)
