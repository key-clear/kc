# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models
from datetime import timedelta


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    payment_next_action = fields.Text('Next Action', copy=False, company_dependent=True,
                                      help="Note regarding the next action.")
    payment_next_action_date = fields.Date('Next Action Date', copy=False, company_dependent=True,
                                           help="The date before which no action should be taken.")
    unreconciled_aml_ids = fields.One2many('account.move.line', 'partner_id', domain=['&', ('reconciled', '=', False), '&',
                                           ('account_id.deprecated', '=', False), '&', ('account_id.internal_type', '=', 'receivable')])

    def get_partners_in_need_of_action(self, overdue_only=False):
        result = self.ids
        today = fields.Date.context_today(self)
        partners = self.search(['|', ('payment_next_action_date', '=', False), ('payment_next_action_date', '<=', today)])
        domain = partners.get_followup_lines_domain(today, overdue_only=overdue_only, only_unblocked=True)
        for line in self.env['account.move.line'].read_group(domain, ['partner_id'], ['partner_id']):
            if line.get('partner_id', False):
                result.append(line['partner_id'][0])
        return self.browse(result)

    def get_followup_lines_domain(self, date, overdue_only=False, only_unblocked=False):
        domain = super(ResPartner, self).get_followup_lines_domain(date, overdue_only=overdue_only, only_unblocked=only_unblocked)
        overdue_domain = ['|', '&', ('date_maturity', '!=', False), ('date_maturity', '<=', date), '&', ('date_maturity', '=', False), ('date', '<=', date)]
        if not overdue_only:
            domain += ['|', '&', ('next_action_date', '=', False)] + overdue_domain + ['&', ('next_action_date', '!=', False), ('next_action_date', '<=', date)]
        return domain

    @api.multi
    def update_next_action(self):
        """Updates the next_action_date of the right account move lines"""
        today = fields.datetime.now()
        next_action_date = today + timedelta(days=self.env.user.company_id.days_between_two_followups)
        next_action_date = next_action_date.strftime('%Y-%m-%d')
        today = fields.Date.context_today(self)
        domain = self.get_followup_lines_domain(today)
        aml = self.env['account.move.line'].search(domain)
        aml.write({'next_action_date': next_action_date})