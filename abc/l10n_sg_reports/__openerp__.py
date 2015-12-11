# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Singapore - Accounting Reports',
    'version': '1.1',
    'author': 'Tech Receptives',
    'website': 'http://www.techreceptives.com',
    'category': 'Localization/Account Report',
    'description': """
Accounting reports for Singapore
================================
    """,
    'depends': [
        'l10n_sg'
    ],
    'data': [
        'account_financial_html_report.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
