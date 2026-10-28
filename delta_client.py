import time
import hmac
import hashlib
import json
import requests
import datetime
from config import BASE_URL, API_KEY, API_SECRET, DRY_RUN

class DeltaClient:
    def __init__(self, base_url=BASE_URL, api_key=API_KEY, api_secret=API_SECRET, dry_run=DRY_RUN):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.dry_run = dry_run
        self.session = requests.Session()

    def _generate_signature(self, method: str, path: str, payload_str: str, timestamp_str: str) -> str:
        message = method.upper() + timestamp_str + path + payload_str
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, path: str, params: dict = None, data: dict = None, auth: bool = True):
        url = self.base_url + path
        timestamp = str(int(time.time()))
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        query_str = ""
        if params:
            # Build URL encoded query string for signature
            query_str = "?" + requests.compat.urlencode(params)
            url += query_str

        body_str = json.dumps(data) if data else ""

        if auth and not self.dry_run:
            sig = self._generate_signature(method, path + query_str, body_str, timestamp)
            headers['api-key'] = self.api_key
            headers['timestamp'] = timestamp
            headers['signature'] = sig

        try:
            if method.upper() == 'GET':
                resp = self.session.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                resp = self.session.post(url, headers=headers, data=body_str, timeout=10)
            elif method.upper() == 'DELETE':
                resp = self.session.delete(url, headers=headers, data=body_str, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[API Error] {resp.status_code} on {path}: {resp.text}")
                return resp.json()
        except Exception as e:
            print(f"[Network Exception] {e} on {url}")
            return None

    # ==========================================
    # PUBLIC MARKET DATA METHODS
    # ==========================================
    def get_candles(self, symbol: str, resolution: str = "1m", start_ts: int = None, end_ts: int = None):
        """Fetch historical candles (1m, 15m, 1h)."""
        path = "/v2/history/candles"
        params = {"symbol": symbol, "resolution": resolution}
        if start_ts is not None:
            params["start"] = start_ts
        if end_ts is not None:
            params["end"] = end_ts

        res = self._request('GET', path, params=params, auth=False)
        if res and res.get('success', False):
            candles = res.get('result', [])
            candles.sort(key=lambda x: x['time'])
            return candles
        return []

    def get_spot_price(self, symbol: str = "BTCUSD") -> float:
        """Fetch latest live 1-min open price for spot symbol."""
        now = int(time.time())
        candles = self.get_candles(symbol, resolution="1m", start_ts=now - 300, end_ts=now)
        if candles:
            return float(candles[-1]['open'])
        return 0.0

    def get_all_option_products(self):
        """Fetch all listed option contracts from Delta."""
        path = "/v2/products"
        res = self._request('GET', path, auth=False)
        if res and res.get('success', False):
            all_prods = res.get('result', [])
            options = [p for p in all_prods if p.get('contract_type') in ['call_options', 'put_options'] and p.get('underlying_asset', {}).get('symbol') == 'BTC']
            return options
        return []

    # ==========================================
    # PRIVATE TRADING METHODS
    # ==========================================
    def place_order(self, product_id: int, size: float, side: str, order_type: str = "market_order", limit_price: float = None, stop_price: float = None, reduce_only: bool = False):
        """
        Place Market, Limit, or Stop-Loss Order.
        side: 'buy' or 'sell'
        reduce_only: True ensures an exit order never opens a new/short position.
        """
        if self.dry_run:
            print(f"[DRY RUN SIMULATION] Placed {order_type.upper()} {side.upper()} | Product ID: {product_id} | Size: {size} BTC | ReduceOnly: {reduce_only}")
            return {"success": True, "result": {"id": f"sim_{int(time.time())}", "status": "filled", "average_fill_price": str(limit_price or 0.0), "size": int(round(size * 1000))}}

        path = "/v2/orders"
        data = {
            "product_id": product_id,
            "size": int(round(size * 1000)), # Note: Delta contract lot multiplier (1 BTC = 1000 lots)
            "side": side.lower(),
            "order_type": order_type.lower()
        }
        if reduce_only:
            data["reduce_only"] = True
        if limit_price is not None:
            data["limit_price"] = str(limit_price)
        if stop_price is not None:
            data["stop_price"] = str(stop_price)

        return self._request('POST', path, data=data, auth=True)

    def cancel_order(self, order_id: str, product_id: int):
        """Cancel an open order."""
        if self.dry_run:
            print(f"[DRY RUN SIMULATION] Cancelled Order ID: {order_id}")
            return {"success": True}

        path = "/v2/orders"
        data = {"id": order_id, "product_id": product_id}
        return self._request('DELETE', path, data=data, auth=True)

    def get_wallet_balances(self):
        """Fetch available margin in USD/USDT."""
        if self.dry_run:
            return {"success": True, "result": [{"asset_symbol": "USD", "available_balance": "10000.0"}]}
        path = "/v2/wallet/balances"
        return self._request('GET', path, auth=True)

    def get_available_usd_balance(self) -> float:
        """Fetch available USD cash margin."""
        if self.dry_run:
            return 10000.0
        res = self.get_wallet_balances()
        if res and res.get('success', False):
            for item in res.get('result', []):
                if item.get('asset_symbol') == 'USD':
                    return float(item.get('available_balance', 0.0))
        return 0.0

    def get_open_position(self, product_id: int) -> dict:
        """Fetch open position details for a specific product."""
        if self.dry_run:
            return {}
        path = f"/v2/positions?product_id={product_id}"
        res = self._request('GET', path, auth=True)
        if res and res.get('success', False):
            result = res.get('result', {})
            if isinstance(result, dict) and int(result.get('size', 0)) != 0:
                return result
            elif isinstance(result, list) and len(result) > 0:
                return result[0]
        return {}
