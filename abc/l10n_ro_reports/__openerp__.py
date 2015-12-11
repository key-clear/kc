# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Romania - Accounting Reports',
    'version': '1.1',
    'category': 'Localization/Account Reports',
    'author': 'ERPsystems Solutions',
    'description': """
        Accounting reports for Romania
    """,
    'depends': [
        'l10n_ro',
    ],
    'data': [
        'account_financial_html_report.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'http://www.erpsystems.ro',
    'license': 'OEEL-1',
}
