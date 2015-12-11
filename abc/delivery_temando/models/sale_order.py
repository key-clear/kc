# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from openerp import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    temando_carrier_id = fields.Integer(string='Temando Carrier ID')
    temando_carrier_name = fields.Char(string='Temando Carrier Name')
    temando_delivery_method = fields.Char(string='Temando Delivery Method')
