# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Fedex Shipping",
    'description': "Send your shippings through Fedex and track them online",
    'author': "Odoo SA",
    'website': "https://www.odoo.com",
    'category': 'Technical Settings',
    'version': '1.0',
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_fedex.xml',
        'views/delivery_fedex.xml',
    ],
    'demo': [
        'data/delivery_fedex_demo.xml'
    ],
    'license': 'OEEL-1',
}
