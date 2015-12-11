# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright (C) 2011 Thamini S.à.R.L (<http://www.thamini.com>)
# Copyright (C) 2011 ADN Consultants S.à.R.L (<http://www.adn-luxembourg.com>)
# Copyright (C) 2014 ACSONE SA/NV (<http://acsone.eu>)
{
    'name': 'Luxembourg - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Luxembourg
================================
    """,
    'author': ['OpenERP SA, ADN, ACSONE SA/NV'],
    'website': 'https://www.odoo.com',
    'category': 'Localization/Account Charts',
    'depends': ['l10n_lu'],
    'data': [
        'account_financial_html_report_mensuel.xml',
    ],
    'demo': [],
    'auto_install': True,
    'installable': True,
    'license': 'OEEL-1',
}
