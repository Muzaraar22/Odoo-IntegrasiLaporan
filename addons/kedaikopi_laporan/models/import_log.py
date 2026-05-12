from odoo import models, fields

class PosIntegrationLog(models.Model):
    _name = 'pos.integration.log'
    _description = 'Riwayat Import CSV'
    _order = 'import_date desc'

    import_date = fields.Datetime(string='Waktu Import', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Diimpor Oleh', default=lambda self: self.env.user, readonly=True)
    pos_system_id = fields.Many2one('pos.system', string='Sistem PoS', readonly=True)
    source_type = fields.Selection([
        ('csv', 'CSV'),
        ('api', 'API'),
    ], string='Jenis Integrasi', default='csv', readonly=True)
    template_id = fields.Many2one('pos.integration.template', string='Template', readonly=True)
    filename = fields.Char(string='Nama File', readonly=True)
    success_count = fields.Integer(string='Sukses (Baris)', readonly=True)
    skipped_count = fields.Integer(string='Dilewati/Duplikat (Baris)', readonly=True)
    failed_count = fields.Integer(string='Gagal (Baris)', readonly=True)
    error_message = fields.Text(string='Pesan Error', readonly=True)
    
    # status Log
    state = fields.Selection([
        ('done', 'Selesai'),
        ('partial', 'Sebagian Berhasil'),
        ('failed', 'Gagal'),
        ('undone', 'Dibatalkan (Undo)')
    ], string='Status', default='done', readonly=True)

    # hapus Massal
    def action_undo_import(self):
        for record in self:
            # cari semua data penjualan yang terikat dengan ID log
            penjualan_terkait = self.env['penjualan.gabungan'].search([('log_id', '=', record.id)])
            penjualan_terkait.unlink()
            record.write({
                'state': 'undone',
                'success_count': 0,
                'skipped_count': 0,
                'failed_count': 0,
            })

