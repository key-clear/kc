# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Accounting Reports',
    'version': '1.1',
    'category': 'Localization/Account Reports',
    'author': 'Odoo SA',
    'description': """
        Accounting reports for Belgium
    """,
    'depends': [
        'l10n_be', 'account_reports',
    ],
    'data': [
        'account_financial_report.xml',
        'report_vat_statement.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'https://www.odoo.com/page/accounting',
    'license': 'OEEL-1',
}
