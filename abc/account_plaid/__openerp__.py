# -*- coding: utf-8 -*-
{
    'name': "account_plaid",

    'summary': """
        Use Plaid.com to retrieve bank statements""",

    'description': """
        Use Plaid.com to retrieve bank statements.
    """,

    'author': "OpenERP s.a.",
    'website': "http://www.odoo.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['account_online_sync'],

    'data': [
        'views/plaid_views.xml',
    ],
    'init_xml': [
        'data/online.institution.csv',
    ],
    'qweb': [
        'views/plaid_templates.xml',
    ],
    'license': 'OEEL-1',
}
