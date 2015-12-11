# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Subscription Management (without frontend)',
    'version': '1.1',
    'category': 'Sales Management',
    'description': """
This module allows you to manage susbcriptions.
Features:
    - Create & edit susbcriptions
    - Modify subscriptions with sales orders
    - Generate invoice automatically at fixed intervals
""",
    'author': 'Camptocamp / Odoo',
    'depends': ['sale'],
    'data': [
        'security/sale_contract_security.xml',
        'security/ir.model.access.csv',
        'views/sale_contract_view.xml',
        'data/sale_contract_cron.xml',
        'data/sale_contract_data.xml',
        'report/sale_contract_report_view.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
