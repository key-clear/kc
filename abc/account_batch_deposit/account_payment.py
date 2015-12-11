# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError

class account_payment(models.Model):
    _inherit = "account.payment"

    batch_deposit_id = fields.Many2one('account.batch.deposit', ondelete='set null')

    @api.multi
    def write(self, vals):
        result = super(account_payment, self).write(vals)
        # Mark a batch deposit as reconciled if all its payments are reconciled
        for rec in self:
            if vals.get('state') and rec.batch_deposit_id:
                if all(payment.state == 'reconciled' for payment in rec.batch_deposit_id.payment_ids):
                    rec.batch_deposit_id.state = 'reconciled'
        return result

    @api.model
    def create_batch_deposit(self, active_ids):
        # Since this method is called via a client_action_multi, we need to make sure the received records are what we expect
        payments = self.browse(active_ids).filtered(lambda r: r.payment_method_id.code == 'batch_deposit' and r.state != 'reconciled' and not r.batch_deposit_id)

        if len(payments) == 0:
            raise UserError(_("Payments to print as a deposit slip must have 'Batch Deposit' selected as payment method, "
                              "not be part of an existing batch deposit and not have already been reconciled"))

        if any(payment.journal_id != payments[0].journal_id for payment in payments):
            raise UserError(_("All payments to print as a deposit slip must belong to the same journal."))

        deposit = self.env['account.batch.deposit'].create({
            'journal_id': payments[0].journal_id.id,
            'payment_ids': [(4, payment.id, None) for payment in payments],
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.batch.deposit",
            "views": [[False, "form"]],
            "res_id": deposit.id,
        }
