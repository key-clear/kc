# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "UPS Shipping",
    'description': "Send your shippings through UPS and track them online",
    'author': "Odoo S.A.",
    'website': "https://www.odoo.com",
    'category': 'Technical Settings',
    'version': '1.0',
    'depends': ['delivery', 'mail'],
    'data': [
        'data/delivery_ups_data.xml',
        'views/delivery_ups_view.xml'
    ],
    'demo': [
        'data/delivery_ups_demo.xml'
    ],
}
