# -*- coding: utf-8 -*-
{
    'name': 'Batch Deposit',
    'version': '1.0',
    'author': 'Odoo SA',
    'category': 'Generic Modules/Accounting',
    'description': """
Batch Deposit
=============
Batch deposits allows you to group received checks before you deposit them to the bank.
The amount deposited to your bank will then appear as a single transaction on your bank statement.
When you proceed with the reconciliation, simply select the corresponding batch deposit to reconcile the payments.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'depends' : ['account_accountant'],
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'data/batch_deposit.xml',
        'report/print_batch_deposit.xml',
        'views/batch_deposit.xml',
        'views/batch_deposit_view.xml',
        'views/account_journal_view.xml',
        'views/account_journal_dashboard_view.xml',
    ],
    'qweb': [
        "static/src/xml/account_reconciliation.xml",
    ],
    'test': [],
    'installable': True,
    'license': 'OEEL-1',
}
