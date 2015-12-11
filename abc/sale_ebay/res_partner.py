# -*- coding: utf-8 -*-

from openerp import models, fields


class res_partner(models.Model):
    _inherit = "res.partner"

    ebay_id = fields.Char('eBay User ID')
