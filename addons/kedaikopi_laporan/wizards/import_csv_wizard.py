import base64
import csv
import io
from datetime import datetime
from odoo import models, fields, _
from odoo.exceptions import UserError

class ImportCsvWizard(models.TransientModel):
    _name = 'import.csv.wizard'
    _description = 'Wizard Import CSV PoS'

    template_id = fields.Many2one('pos.integration.template', string='Template PoS', required=True)
    csv_file = fields.Binary(string='File CSV', required=True)
    filename = fields.Char(string='Nama File')

    # deteksi Format Tanggal
    def _parse_date(self, date_str):
        if not date_str:
            return False
        # list berbagai format tanggal yang mungkin
        possible_formats = [
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', 
            '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y',
            '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d-%m-%Y'
        ]
        for fmt in possible_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        return False

    def action_import(self):
        if not self.csv_file:
            raise UserError("Silakan unggah file CSV terlebih dahulu.")

        csv_data = base64.b64decode(self.csv_file)
        try:
            data_file = io.StringIO(csv_data.decode("utf-8"))
        except UnicodeDecodeError:
            raise UserError("Pastikan file memiliki format UTF-8 CSV.")
        
        data_file.seek(0)
        file_reader = csv.DictReader(data_file, delimiter=',')

        mapping = {}
        for line in self.template_id.line_ids:
            mapping[line.odoo_field] = line.csv_column_name

        csv_headers = file_reader.fieldnames
        for odoo_field, csv_col in mapping.items():
            if csv_col not in csv_headers:
                raise UserError(f"Kolom '{csv_col}' tidak ditemukan di CSV.")

        # ========================================================
        # PERUBAHAN: Buat cangkang Log terlebih dahulu di awal
        # ========================================================
        log_record = self.env['pos.integration.log'].create({
            'source_type': 'csv',
            'template_id': self.template_id.id,
            'filename': self.filename,
            'success_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'state': 'done'
        })

        PenjualanObj = self.env['penjualan.gabungan']
        imported_count = 0
        skipped_count = 0

        for row in file_reader:
            trans_id = row.get(mapping.get('transaction_id'))
            raw_date = row.get(mapping.get('transaction_date'))
            product = row.get(mapping.get('product_name'))
            trans_date = self._parse_date(raw_date)
            
            try:
                qty = float((row.get(mapping.get('quantity', '1.0')) or '1.0').replace(',', '.'))
                price = float((row.get(mapping.get('unit_price', '0.0')) or '0.0').replace(',', ''))
            except ValueError:
                qty, price = 1.0, 0.0

            if not trans_id or not product:
                continue 

            existing = PenjualanObj.search([('transaction_id', '=', trans_id), ('product_name', '=', product), ('source_pos', '=', self.template_id.name)])
            if existing:
                skipped_count += 1
                continue 

            PenjualanObj.create({
                'transaction_id': trans_id,
                'transaction_date': trans_date or fields.Datetime.now(), # jika gagal dibaca, pakai waktu sekarang
                'product_name': product,
                'quantity': qty,
                'unit_price': price,
                'source_pos': self.template_id.name,
                'integration_source': 'csv',
                'log_id': log_record.id # link ke ID log yang baru dibuat
            })
            imported_count += 1

        # Update hitungan final ke Log
        log_record.write({
            'success_count': imported_count,
            'skipped_count': skipped_count,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Selesai',
                'message': f'Berhasil import {imported_count} baris. Dilewati {skipped_count} baris.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
