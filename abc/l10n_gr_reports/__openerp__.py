# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) 2009 P. Christeas <p_christ@hol.gr>. All Rights Reserved

{
    'name': 'Greece - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Greece
=============================

    """,
    'author': ['P. Christeas, OpenERP SA.'],
    'website': 'http://openerp.hellug.gr/',
    'category': 'Localization/Account Charts',
    'depends': ['l10n_gr'],
    'data': [
        'account_financial_html_report.xml'
    ],
    'demo': [],
    'auto_install': True,
    'installable': True,
    'license': 'OEEL-1',
}
