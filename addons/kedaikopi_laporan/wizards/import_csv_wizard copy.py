import base64
import csv
import io
from odoo import models, fields, _
from odoo.exceptions import UserError

# membaca file Excel/CSV, mencocokkan template, dan mencegah duplikasi
class ImportCsvWizard(models.TransientModel):
    _name = 'import.csv.wizard'
    _description = 'Wizard Import CSV PoS'

    template_id = fields.Many2one('pos.integration.template', string='Template PoS', required=True)
    csv_file = fields.Binary(string='File CSV', required=True)
    filename = fields.Char(string='Nama File')

    def action_import(self):
        if not self.csv_file:
            raise UserError("Silakan unggah file CSV terlebih dahulu.")

        # decode file CSV yang diunggah
        csv_data = base64.b64decode(self.csv_file)
        try:
            data_file = io.StringIO(csv_data.decode("utf-8"))
        except UnicodeDecodeError:
            raise UserError("Pastikan file yang diunggah memiliki format UTF-8 CSV.")
        
        data_file.seek(0)
        file_reader = csv.DictReader(data_file, delimiter=',')

        # buat Kamus (Dictionary) dari Template
        mapping = {}
        for line in self.template_id.line_ids:
            mapping[line.odoo_field] = line.csv_column_name

        # validasi nama kolom di CSV sesuai dengan template
        csv_headers = file_reader.fieldnames
        for odoo_field, csv_col in mapping.items():
            if csv_col not in csv_headers:
                raise UserError(f"Kolom '{csv_col}' tidak ditemukan di file CSV yang diunggah. Periksa kembali template Anda.")

        PenjualanObj = self.env['penjualan.gabungan']
        imported_count = 0
        skipped_count = 0

        # looping baris per baris isi CSV
        for row in file_reader:
            trans_id = row.get(mapping.get('transaction_id'))
            trans_date = row.get(mapping.get('transaction_date'))
            product = row.get(mapping.get('product_name'))
            
            # konversi teks ke angka (untuk harga dan qty)
            try:
                qty_str = row.get(mapping.get('quantity', '1.0')) or '1.0'
                price_str = row.get(mapping.get('unit_price', '0.0')) or '0.0'
                # hapus karakter non-angka  (seperti Rp atau koma)
                qty = float(qty_str.replace(',', '.'))
                price = float(price_str.replace(',', ''))
            except ValueError:
                qty, price = 1.0, 0.0

            if not trans_id or not product:
                continue # lewati baris jika data penting kosong

            # pencegahan duplikasi
            existing = PenjualanObj.search([
                ('transaction_id', '=', trans_id),
                ('product_name', '=', product)
            ])

            if existing:
                skipped_count += 1
                continue # Lewati dan jangan masukkan ke database

            # msukkan data bersih ke database utama
            PenjualanObj.create({
                'transaction_id': trans_id,
                'transaction_date': trans_date,
                'product_name': product,
                'quantity': qty,
                'unit_price': price,
                'source_pos': self.template_id.name
            })
            imported_count += 1
        
        # logging
        self.env['pos.integration.log'].create({
            'template_id': self.template_id.id,
            'filename': self.filename,
            'success_count': imported_count,
            'skipped_count': skipped_count,
        })

        # notifikasi hijau di pojok kanan atas
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Selesai',
                'message': f'Berhasil import {imported_count} baris. Dilewati {skipped_count} baris (Duplikat/Overlap).',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


