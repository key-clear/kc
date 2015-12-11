# -*- coding: utf-8 -*-
from openerp import fields, models, api

# TODO: To remove in v10
class PlaidConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    def _default_plaid_id(self):
        return self.env['ir.config_parameter'].get_param('plaid_id')

    def _default_plaid_secret(self):
        return self.env['ir.config_parameter'].get_param('plaid_secret')

    plaid_id = fields.Char("Plaid ID", default=_default_plaid_id, compute='_compute_plaid_id', inverse='_inverse_plaid_id')
    plaid_secret = fields.Char("Plaid Secret", default=_default_plaid_secret, compute='_compute_plaid_secret', inverse='_inverse_plaid_secret')

    @api.one
    def _compute_plaid_id(self):
        self.plaid_id = self.env['ir.config_parameter'].get_param('plaid_id', self.plaid_id)

    @api.one
    def _inverse_plaid_id(self):
        if self.plaid_id:
            self.env['ir.config_parameter'].set_param('plaid_id', self.plaid_id, groups=["base.group_erp_manager"])

    @api.one
    def _compute_plaid_secret(self):
        self.plaid_secret = self.env['ir.config_parameter'].get_param('plaid_secret', self.plaid_secret)

    @api.one
    def _inverse_plaid_secret(self):
        if self.plaid_secret:
            self.env['ir.config_parameter'].set_param('plaid_secret', self.plaid_secret, groups=["base.group_erp_manager"])
