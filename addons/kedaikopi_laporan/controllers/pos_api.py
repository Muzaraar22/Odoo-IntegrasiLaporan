import json
from datetime import datetime

from odoo import fields, http
from odoo.http import request
from werkzeug.wrappers import Response


class POSAPIController(http.Controller):
    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type='application/json',
        )

    def _parse_date(self, value):
        if not value:
            return fields.Datetime.now()
        possible_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%d-%m-%Y %H:%M:%S',
            '%d-%m-%Y %H:%M',
            '%d-%m-%Y',
        ]
        for fmt in possible_formats:
            try:
                return datetime.strptime(value, fmt).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        return fields.Datetime.now()

    @http.route('/pos/api/v1/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health(self, **kwargs):
        return self._json_response({
            'status': 'ok',
            'service': 'odoo-pos-middleware',
            'version': 'v1',
        })

    @http.route('/pos/api/v1/sync', type='http', auth='public', methods=['POST'], csrf=False)
    def sync_transactions(self, **kwargs):
        raw_body = request.httprequest.get_data(as_text=True)
        try:
            payload = json.loads(raw_body or '{}')
        except json.JSONDecodeError:
            return self._json_response({
                'status': 'failed',
                'message': 'Payload harus berupa JSON valid.',
            }, status=400)

        pos_code = payload.get('pos_code')
        token = request.httprequest.headers.get('X-POS-Token')
        PosSystem = request.env['pos.system'].sudo()
        pos_system = PosSystem.search([
            ('code', '=', pos_code),
            ('api_token', '=', token),
            ('active', '=', True),
        ], limit=1)

        Log = request.env['pos.integration.log'].sudo()
        if not pos_system:
            Log.create({
                'source_type': 'api',
                'filename': pos_code or 'UNKNOWN_POS',
                'state': 'failed',
                'error_message': 'Token, kode PoS, atau status aktif tidak valid.',
            })
            return self._json_response({
                'status': 'failed',
                'message': 'Token, kode PoS, atau status aktif tidak valid.',
            }, status=401)

        transactions = payload.get('transactions')
        if not isinstance(transactions, list):
            log = Log.create({
                'source_type': 'api',
                'pos_system_id': pos_system.id,
                'filename': pos_code,
                'state': 'failed',
                'error_message': "Field 'transactions' wajib berupa list.",
            })
            pos_system.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            return self._json_response({
                'status': 'failed',
                'message': "Field 'transactions' wajib berupa list.",
                'log_id': log.id,
            }, status=400)

        log = Log.create({
            'source_type': 'api',
            'pos_system_id': pos_system.id,
            'filename': pos_code,
            'success_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'state': 'done',
        })

        imported_count = 0
        skipped_count = 0
        failed_count = 0
        error_messages = []
        Penjualan = request.env['penjualan.gabungan'].sudo()

        for transaction in transactions:
            transaction_id = transaction.get('transaction_id')
            transaction_date = self._parse_date(transaction.get('transaction_date'))
            items = transaction.get('items')

            if not transaction_id or not isinstance(items, list) or not items:
                failed_count += 1
                error_messages.append('Transaksi dilewati karena ID atau item kosong.')
                continue

            for item in items:
                product_name = item.get('product_name')
                if not product_name:
                    failed_count += 1
                    error_messages.append(f"Item pada transaksi {transaction_id} tidak memiliki nama produk.")
                    continue

                try:
                    quantity = float(item.get('quantity', 1.0))
                    unit_price = float(item.get('unit_price', 0.0))
                except (TypeError, ValueError):
                    failed_count += 1
                    error_messages.append(f"Qty/harga tidak valid pada transaksi {transaction_id}.")
                    continue

                existing = Penjualan.search([
                    ('transaction_id', '=', transaction_id),
                    ('product_name', '=', product_name),
                ], limit=1)
                if existing:
                    skipped_count += 1
                    continue

                Penjualan.create({
                    'transaction_id': transaction_id,
                    'transaction_date': transaction_date,
                    'product_name': product_name,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'source_pos': pos_system.name,
                    'pos_system_id': pos_system.id,
                    'integration_source': 'api',
                    'log_id': log.id,
                })
                imported_count += 1

        state = 'done'
        last_status = 'success'
        if failed_count and imported_count:
            state = 'partial'
            last_status = 'partial'
        elif failed_count and not imported_count:
            state = 'failed'
            last_status = 'failed'

        log.write({
            'success_count': imported_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'state': state,
            'error_message': '\n'.join(error_messages[:10]),
        })
        pos_system.write({
            'last_sync_at': fields.Datetime.now(),
            'last_status': last_status,
        })

        return self._json_response({
            'status': 'success' if state == 'done' else state,
            'pos_code': pos_system.code,
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'log_id': log.id,
        })
