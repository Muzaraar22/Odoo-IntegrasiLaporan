import json
from datetime import datetime
from urllib import error, request

from odoo import api, fields, models


class POSSystem(models.Model):
    _name = 'pos.system'
    _description = 'Sistem PoS Eksternal'
    _order = 'name'

    name = fields.Char(string='Nama PoS', required=True)
    code = fields.Char(string='Kode PoS', required=True, index=True)
    floor = fields.Selection([
        ('atas', 'Lantai Atas'),
        ('bawah', 'Lantai Bawah'),
        ('lainnya', 'Lainnya'),
    ], string='Lokasi', default='lainnya', required=True)
    sync_endpoint_url = fields.Char(string='URL Endpoint PoS')
    auto_sync_enabled = fields.Boolean(string='Auto Sync Aktif', default=False)
    sync_time = fields.Char(string='Jam Sync Harian', default='21:00', help='Format HH:MM, contoh 21:00')
    last_auto_sync_key = fields.Char(string='Penanda Sync Harian', readonly=True)
    api_token = fields.Char(string='Token API', required=True)
    active = fields.Boolean(string='Aktif', default=True)
    last_sync_at = fields.Datetime(string='Sinkronisasi Terakhir', readonly=True)
    last_status = fields.Selection([
        ('idle', 'Belum Sinkronisasi'),
        ('success', 'Berhasil'),
        ('partial', 'Sebagian Berhasil'),
        ('failed', 'Gagal'),
    ], string='Status Terakhir', default='idle', readonly=True)

    _sql_constraints = [
        ('unique_pos_code', 'unique(code)', 'Kode PoS harus unik.'),
    ]

    @api.model
    def _parse_sync_time(self, sync_time):
        if not sync_time:
            return None
        try:
            hour_str, minute_str = sync_time.split(':', 1)
            hour = int(hour_str)
            minute = int(minute_str)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                return None
            return hour, minute
        except (ValueError, AttributeError):
            return None

    @api.model
    def _json_payload(self, raw_data):
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode('utf-8')
        return json.loads(raw_data or '{}')

    def _create_sync_log(self, source_type='api', filename=False, state='done', error_message=False):
        self.ensure_one()
        log_vals = {
            'source_type': source_type,
            'pos_system_id': self.id,
            'filename': filename or self.code,
            'success_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'state': state,
        }
        if error_message:
            log_vals['error_message'] = error_message
        return self.env['pos.integration.log'].sudo().create(log_vals)

    def _ingest_transactions_payload(self, payload, source_type='api', filename=False):
        self.ensure_one()
        if not isinstance(payload, dict):
            log = self._create_sync_log(
                source_type=source_type,
                filename=filename or self.code,
                state='failed',
                error_message='Payload transaksi harus berupa object JSON.',
            )
            self.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            return {
                'status': 'failed',
                'log_id': log.id,
                'imported_count': 0,
                'skipped_count': 0,
                'failed_count': 1,
            }

        filename = filename or payload.get('pos_code') or self.code

        if payload.get('pos_code') and payload.get('pos_code') != self.code:
            log = self._create_sync_log(
                source_type=source_type,
                filename=filename,
                state='failed',
                error_message='Kode PoS pada payload tidak sesuai dengan sistem PoS tujuan.',
            )
            self.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            return {
                'status': 'failed',
                'log_id': log.id,
                'imported_count': 0,
                'skipped_count': 0,
                'failed_count': 1,
            }

        transactions = payload.get('transactions')
        if not isinstance(transactions, list):
            log = self._create_sync_log(
                source_type=source_type,
                filename=filename,
                state='failed',
                error_message="Field 'transactions' wajib berupa list.",
            )
            self.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            return {
                'status': 'failed',
                'log_id': log.id,
                'imported_count': 0,
                'skipped_count': 0,
                'failed_count': 1,
            }

        log = self._create_sync_log(source_type=source_type, filename=filename)
        imported_count = 0
        skipped_count = 0
        failed_count = 0
        error_messages = []
        Penjualan = self.env['penjualan.gabungan'].sudo()

        for transaction in transactions:
            transaction_id = transaction.get('transaction_id')
            transaction_date = self._parse_transaction_date(transaction.get('transaction_date'))
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
                    'source_pos': self.name,
                    'pos_system_id': self.id,
                    'integration_source': source_type,
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
        self.write({
            'last_sync_at': fields.Datetime.now(),
            'last_status': last_status,
        })

        return {
            'status': 'success' if state == 'done' else state,
            'log_id': log.id,
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
        }

    @api.model
    def _parse_transaction_date(self, value):
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

    def _fetch_remote_transactions(self):
        self.ensure_one()
        if not self.sync_endpoint_url:
            raise ValueError('URL endpoint PoS belum diisi.')

        headers = {'Accept': 'application/json'}
        if self.api_token:
            headers['X-POS-Token'] = self.api_token

        req = request.Request(self.sync_endpoint_url, headers=headers, method='GET')
        with request.urlopen(req, timeout=30) as response:
            raw_body = response.read().decode('utf-8')
        return self._json_payload(raw_body)

    def action_sync_now(self):
        results = []
        for pos in self:
            try:
                payload = pos._fetch_remote_transactions()
                result = pos._ingest_transactions_payload(payload, source_type='api', filename=payload.get('pos_code') or pos.code)
            except error.HTTPError as exc:
                error_body = exc.read().decode('utf-8', errors='ignore')
                pos._create_sync_log(
                    source_type='api',
                    filename=pos.code,
                    state='failed',
                    error_message=f'HTTP {exc.code}: {error_body[:500]}',
                )
                pos.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
                result = {'status': 'failed', 'imported_count': 0, 'skipped_count': 0, 'failed_count': 1}
            except Exception as exc:
                pos._create_sync_log(
                    source_type='api',
                    filename=pos.code,
                    state='failed',
                    error_message=str(exc),
                )
                pos.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
                result = {'status': 'failed', 'imported_count': 0, 'skipped_count': 0, 'failed_count': 1}
            results.append(result)

        total_imported = sum(item.get('imported_count', 0) for item in results)
        total_skipped = sum(item.get('skipped_count', 0) for item in results)
        total_failed = sum(item.get('failed_count', 0) for item in results)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Selesai',
                'message': f'Import {total_imported} baris, dilewati {total_skipped} baris, gagal {total_failed} baris.',
                'type': 'success' if total_failed == 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    @api.model
    def _cron_auto_sync_pos_systems(self):
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        today_key = now.strftime('%Y-%m-%d')
        current_minutes = now.hour * 60 + now.minute
        systems = self.sudo().search([
            ('active', '=', True),
            ('auto_sync_enabled', '=', True),
            ('sync_endpoint_url', '!=', False),
        ])

        for system in systems:
            parsed_time = system._parse_sync_time(system.sync_time)
            if not parsed_time:
                continue

            sync_minutes = parsed_time[0] * 60 + parsed_time[1]
            if current_minutes < sync_minutes:
                continue
            if system.last_auto_sync_key == today_key:
                continue

            try:
                payload = system._fetch_remote_transactions()
                system._ingest_transactions_payload(payload, source_type='api', filename=payload.get('pos_code') or system.code)
            except error.HTTPError as exc:
                error_body = exc.read().decode('utf-8', errors='ignore')
                system._create_sync_log(
                    source_type='api',
                    filename=system.code,
                    state='failed',
                    error_message=f'HTTP {exc.code}: {error_body[:500]}',
                )
                system.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            except Exception as exc:
                system._create_sync_log(
                    source_type='api',
                    filename=system.code,
                    state='failed',
                    error_message=str(exc),
                )
                system.write({'last_sync_at': fields.Datetime.now(), 'last_status': 'failed'})
            finally:
                system.write({'last_auto_sync_key': today_key})
