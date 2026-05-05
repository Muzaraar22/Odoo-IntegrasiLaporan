{
    'name': 'Integrasi Laporan PoS',
    'version': '18.0.1.0.0',
    'summary': 'Sistem ETL untuk menggabungkan laporan CSV dari berbagai sumber PoS',
    'description': """
        Modul Integrasi Laporan Kedai Kopi Warga.
        
        Fitur utama:
        - Pembuatan template dinamis untuk berbagai format CSV (Majoo, Moka, dll).\n
        - Import dan standarisasi data transaksi PoS.\n
        - Pencegahan duplikasi data transaksi (overlap).
        - Sistem log untuk pemantauan proses import.
    """,
    'category': 'Sales',
    'author': 'Kelompok 4 - SI Kedai Kopi Warga',
    'website': '',
    'depends': ['base'], # Modul dasar yang dibutuhkan
    'data': [
        # File security dan views (XML) akan didaftarkan di sini nanti
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/template_views.xml',
        'views/penjualan_views.xml',
        'wizards/import_csv_wizard_views.xml',
        'views/log_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True, # True akan muncul di halaman depan "Aplikasi"
    'auto_install': False,
}