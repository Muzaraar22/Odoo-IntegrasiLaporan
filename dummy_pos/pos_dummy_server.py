import json
import os
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request


POS_CODE = os.getenv('POS_CODE', 'POS_DUMMY')
POS_NAME = os.getenv('POS_NAME', 'PoS Dummy')
POS_TOKEN = os.getenv('POS_TOKEN', 'dummy-token')
PORT = int(os.getenv('PORT', '8071'))
ODOO_SYNC_URL = os.getenv('ODOO_SYNC_URL', 'http://web:8069/pos/api/v1/sync')


def build_payload():
    today = datetime.now().strftime('%Y-%m-%d')
    time_seed = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    suffix = 'ATAS' if 'ATAS' in POS_CODE else 'BAWAH'
    return {
        'pos_code': POS_CODE,
        'pos_name': POS_NAME,
        'business_date': today,
        'transactions': [
            {
                'transaction_id': f'{suffix}-{today.replace("-", "")}-0001',
                'transaction_date': (time_seed + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
                'items': [
                    {'product_name': 'Kopi Susu Warga', 'quantity': 2, 'unit_price': 18000},
                    {'product_name': 'Roti Bakar Cokelat', 'quantity': 1, 'unit_price': 22000},
                ],
            },
            {
                'transaction_id': f'{suffix}-{today.replace("-", "")}-0002',
                'transaction_date': (time_seed + timedelta(minutes=42)).strftime('%Y-%m-%d %H:%M:%S'),
                'items': [
                    {'product_name': 'Americano', 'quantity': 1, 'unit_price': 16000},
                ],
            },
        ],
    }


class DummyPOSHandler(BaseHTTPRequestHandler):
    def _payload(self):
        return build_payload()

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self._send_json({
                'status': 'ok',
                'service': POS_NAME,
                'pos_code': POS_CODE,
            })
            return

        if self.path == '/transactions/today':
            self._send_json(self._payload())
            return

        self._send_json({'status': 'failed', 'message': 'Not found'}, status=404)

    def do_POST(self):
        if self.path == '/sync/odoo':
            body = json.dumps(self._payload()).encode('utf-8')
            req = request.Request(
                ODOO_SYNC_URL,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'X-POS-Token': POS_TOKEN,
                },
                method='POST',
            )
            try:
                with request.urlopen(req, timeout=20) as response:
                    response_body = response.read().decode('utf-8')
                    try:
                        parsed = json.loads(response_body)
                    except json.JSONDecodeError:
                        parsed = {'raw_response': response_body}
                    self._send_json({
                        'status': 'sent',
                        'odoo_response': parsed,
                    }, status=200)
            except error.HTTPError as exc:
                error_body = exc.read().decode('utf-8', errors='ignore')
                self._send_json({
                    'status': 'failed',
                    'message': f'Odoo returned HTTP {exc.code}',
                    'detail': error_body,
                }, status=exc.code)
            except Exception as exc:
                self._send_json({
                    'status': 'failed',
                    'message': str(exc),
                }, status=500)
            return

        self._send_json({'status': 'failed', 'message': 'Not found'}, status=404)

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), DummyPOSHandler)
    print(f'{POS_NAME} listening on {PORT}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
