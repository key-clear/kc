# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Temando Shipping",
    'description': "Send your shippings through Temando and track them online",
    'author': "Odoo SA",
    'website': "https://www.odoo.com",
    'category': 'Technical Settings',
    'version': '1.0',
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_temando.xml',
        'views/delivery_temando_view.xml',
    ],
    'demo': [
        'data/delivery_temando_demo.xml',
    ],
}
