# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Uruguay - Accounts Reports',
    'version': '1.1',
    'author': 'Uruguay l10n Team & Guillem Barba',
    'category': 'Localization/Account Reports',
    'website': 'https://launchpad.net/openerp-uruguay',
    'description': """
        Accounting reports for Uruguay

""",
    'depends': [
        'l10n_uy',
    ],
    'data': [
        'account_financial_report.xml',
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
