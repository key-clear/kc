# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Brazilian - Accounting Reports',
    'version': '1.1',
    'category': 'Localization/Account Reports',
    'author': 'Odoo S.A.',
    'description': """
        Accounting reports for Brazilian
    """,
    'depends': [
        'l10n_br',
    ],
    'data': [
        'account_financial_report.xml',
    ],
    'installable': True,
    'auto_install': True,
    'website': 'http://openerpbrasil.org',
    'license': 'OEEL-1',
}
