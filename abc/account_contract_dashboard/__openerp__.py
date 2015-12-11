# -*- coding: utf-8 -*-

{
    'name': 'Account Contract Dashboard',
    'version': '1.0',
    'depends': ['sale_contract_asset', 'account_deferred_revenue'],
    'author': 'Odoo S.A.',
    'description': """
Accounting Contract Dashboard
========================
It adds dashboards to :
1) Analyse the recurrent revenue and other metrics for contracts
2) Analyse the contracts modifications by salesman and compute their value.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'category': 'Accounting & Finance',
    'data': [
        'views/account_contract_dashboard_report_view.xml',
        'templates/assets.xml',
    ],
    'demo': [
        #if any, demo data should be created using yml files, in the same flavour then in account_asset
        #'demo/account_contract_dashboard_demo.xml',
    ],
    'qweb': [
        "static/src/xml/account_contract_dashboard.xml",
    ],
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}
