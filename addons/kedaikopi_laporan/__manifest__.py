{
    'name': 'Integrasi Laporan PoS',
    'version': '18.0.1.0.0',
    'summary': 'Sistem integrasi PoS terpusat untuk laporan CSV dan API',
    'description': """
        Modul Integrasi Laporan Kedai Kopi Warga.
        
        Fitur utama:
        - Pembuatan template dinamis untuk berbagai format CSV (Majoo, Moka, dll).\n
        - Import dan standarisasi data transaksi PoS.\n
        - Penerimaan sinkronisasi JSON dari PoS Lantai Atas dan PoS Lantai Bawah.\n
        - Pencegahan duplikasi data transaksi (overlap).\n
        - Sistem log untuk pemantauan proses import dan API sync.
    """,
    'category': 'Sales',
    'author': 'Kelompok 4 - SI Kedai Kopi Warga',
    'website': '',
    'depends': ['base'], # Modul dasar yang dibutuhkan
    'data': [
        # File security dan views (XML) akan didaftarkan di sini nanti
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/pos_system_data.xml',
        'data/pos_auto_sync_cron.xml',
        'views/template_views.xml',
        'views/penjualan_views.xml',
        'views/pos_system_views.xml',
        'wizards/import_csv_wizard_views.xml',
        'views/log_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True, # True akan muncul di halaman depan "Aplikasi"
    'auto_install': False,
}
