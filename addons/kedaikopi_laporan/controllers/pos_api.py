import json

from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response


class POSAPIController(http.Controller):
    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type='application/json',
        )

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
        result = pos_system._ingest_transactions_payload(payload, source_type='api', filename=pos_code)
        http_status = 200
        if result.get('status') == 'failed':
            http_status = 400
        elif result.get('status') == 'partial':
            http_status = 207

        return self._json_response({
            'status': result.get('status'),
            'pos_code': pos_system.code,
            'imported_count': result.get('imported_count', 0),
            'skipped_count': result.get('skipped_count', 0),
            'failed_count': result.get('failed_count', 0),
            'log_id': result.get('log_id'),
        }, status=http_status)
