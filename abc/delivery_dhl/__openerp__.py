# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "DHL Shipping",
    'description': "Send your shippings through DHL and track them online",
    'author': "Odoo SA",
    'website': "https://www.odoo.com",
    'category': 'Technical Settings',
    'version': '1.0',
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_dhl_data.xml',
        'views/delivery_dhl_view.xml',
    ],
    'demo': [
        'data/delivery_dhl_demo_data.xml'
    ],
}
