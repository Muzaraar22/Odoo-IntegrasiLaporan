from odoo import models, fields

class PosIntegrationTemplate(models.Model):
    _name = 'pos.integration.template'
    _description = 'Template Mapping CSV PoS'

    name = fields.Char(string='Nama Sumber PoS', required=True, help="Contoh: Majoo, MokaPOS")
    
    # Relasi ke detail kolom (One2many)
    line_ids = fields.One2many('pos.integration.template.line', 'template_id', string='Mapping Kolom')

class PosIntegrationTemplateLine(models.Model):
    _name = 'pos.integration.template.line'
    _description = 'Detail Mapping Kolom'

    template_id = fields.Many2one('pos.integration.template', string='Template', required=True, ondelete='cascade')
    
    # Kolom baku yang kita sediakan di database Odoo
    odoo_field = fields.Selection([
        ('transaction_date', 'Tanggal Transaksi'),
        ('transaction_id', 'ID Transaksi / Struk'),
        ('product_name', 'Nama Produk'),
        ('quantity', 'Kuantitas (Qty)'),
        ('unit_price', 'Harga Satuan'),
    ], string='Target Kolom (Odoo)', required=True)
    
    # nama kolom yang ada di file CSV (harus diketik persis sesuai header CSV)
    csv_column_name = fields.Char(string='Nama Kolom di CSV', required=True, help="Harus sama persis dengan header CSV, misal: 'Tanggal Penjualan'")