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

    def log_message(self, format, *args):
        # Suppress standard HTTP access logs to keep terminal clean
        return

def run_http_server(port):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, StatusHandler)
    print(f"[RENDER] Web Health Server listening on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    # 1. Start trading bot in a background thread
    bot_thread = threading.Thread(target=bot_instance.run, daemon=True)
    bot_thread.start()
    
    # 2. Start HTTP server on Render's assigned port (default 10000)
    port = int(os.getenv("PORT", 10000))
    run_http_server(port)
