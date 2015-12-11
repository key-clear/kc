# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Switzerland - Accounting Reports',
    'version': '1.1',
    'category': 'Localization/Account Reports',
    'author': 'Odoo S.A.',
    'description': """
        Accounting reports for Switzerland
    """,
    'depends': [
        'l10n_ch',
    ],
    'data': [
        'account_financial_report.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'https://www.odoo.com/page/accounting',
    'license': 'OEEL-1',
}
