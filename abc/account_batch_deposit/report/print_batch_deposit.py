# -*- coding: utf-8 -*-

import time

from openerp.osv import osv
from openerp.report import report_sxw
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

PAY_LINES_PER_PAGE = 20

class report_print_batch_deposit(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(report_print_batch_deposit, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'pages': self.get_pages,
        })

    def get_pages(self, deposit):
        """ Returns the data structure used by the template
        """
        i = 0
        payment_slices = []
        while i < len(deposit.payment_ids):
            payment_slices.append(deposit.payment_ids[i:i+PAY_LINES_PER_PAGE])
            i += PAY_LINES_PER_PAGE

        return [{
            'date': deposit.date,
            'deposit_name': deposit.name,
            'journal_name': deposit.journal_id.name,
            'payments': payments,
            'currency': deposit.currency_id,
            'total_amount': deposit.amount,
            'footer': deposit.journal_id.company_id.rml_footer,
        } for payments in payment_slices]

class print_batch_deposit(osv.AbstractModel):
    _name = 'report.account_batch_deposit.print_batch_deposit'
    _inherit = 'report.abstract_report'
    _template = 'account_batch_deposit.print_batch_deposit'
    _wrapped_report_class = report_print_batch_deposit
