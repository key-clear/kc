# -*- coding: utf-8 -*-
{
    'name': "SEPA Credit Transfer",
    'summary': """Export payments as SEPA Credit Transfer files""",
    'description': """
        Generate payment orders as pain.001.001.03 messages. The generated XML file can then be uploaded to your bank.

        This module follow the implementation guidelines issued by the European Payment Council.
        For more informations about the SEPA standards : http://www.iso20022.org/ and http://www.europeanpaymentscouncil.eu/
    """,
    'author': "Odoo SA",
    'category': 'Accounting &amp; Finance',
    'version': '1.0',
    'depends': ['account', 'base_iban'],
    'data': [
        'data/sepa.xml',
        'views/account_journal_dashboard_view.xml',
        'views/sepa_credit_transfer_view.xml',
        'views/account_payment.xml',
        'views/res_company_view.xml',
    ],
    'license': 'OEEL-1',
}
