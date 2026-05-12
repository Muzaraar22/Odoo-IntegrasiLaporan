from odoo import fields, models


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
