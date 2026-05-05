from odoo import models, fields, api

class PenjualanGabungan(models.Model):
    _name = 'penjualan.gabungan'
    _description = 'Data Transaksi Penjualan Gabungan'

    transaction_id = fields.Char(string='ID Transaksi', required=True, index=True)
    transaction_date = fields.Datetime(string='Tanggal Transaksi', required=True)
    product_name = fields.Char(string='Nama Produk', required=True)
    quantity = fields.Float(string='Kuantitas (Qty)', required=True, default=1.0)
    unit_price = fields.Float(string='Harga Satuan', required=True)
    
    # Total harga  dihitung otomatis oleh Odoo (Qty * Harga Satuan)
    total_price = fields.Float(string='Total Harga', compute='_compute_total_price', store=True)
    source_pos = fields.Char(string='Sumber PoS', help="Diambil otomatis dari nama template, misal: Majoo")

    # mencegah duplikasi
    # Kombinasi ID Struk dan Nama Produk tidak boleh dimasukkan dua kali
    _sql_constraints = [
        ('unique_transaction_product', 
         'unique(transaction_id, product_name)', 
         'Data transaksi ini sudah pernah diunggah! Tidak boleh overlap.')
    ]

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price