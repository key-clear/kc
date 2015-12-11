from openerp import api, fields, models


class PaymentAcquirer(models.Model):
    _name = 'payment.acquirer'
    _inherit = 'payment.acquirer'

    journal_id = fields.Many2one('account.journal', 'Accounting Journal',
                                 help="Account journal used for automatic payment reconciliation "
                                 "if you use automatic payment.")


class PaymentTransaction(models.Model):
    _name = 'payment.transaction'
    _inherit = 'payment.transaction'

    invoice_id = fields.Many2one('account.invoice', 'Invoice')
