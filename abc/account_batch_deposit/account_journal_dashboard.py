# -*- coding: utf-8 -*-

from openerp import models, api, _

class account_journal(models.Model):
    _inherit = "account.journal"

    @api.multi
    def open_action_batch_deposit(self):
        ctx = self._context.copy()
        ctx.update({'journal_id': self.id, 'default_journal_id': self.id})
        return {
            'name': _('Create Batch Deposit'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.batch.deposit',
            'context': ctx,
        }
