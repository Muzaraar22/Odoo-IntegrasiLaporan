from odoo import models, fields

class PosIntegrationLog(models.Model):
    _name = 'pos.integration.log'
    _description = 'Riwayat Import CSV'
    _order = 'import_date desc' # urutkan dari yang paling baru

    import_date = fields.Datetime(string='Waktu Import', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Diimpor Oleh', default=lambda self: self.env.user, readonly=True)
    template_id = fields.Many2one('pos.integration.template', string='Template', readonly=True)
    filename = fields.Char(string='Nama File', readonly=True)
    success_count = fields.Integer(string='Sukses (Baris)', readonly=True)
    skipped_count = fields.Integer(string='Dilewati/Duplikat (Baris)', readonly=True)