# -*- coding: utf-8 -*-
{
  'name': "Sale Ebay",

  'summary': """
  Publish your products on eBay""",

  'description': """
Publish your products on eBay
==============================================================

The eBay integrator gives you the opportunity to manage your Odoo's products on eBay.

Key Features
------------
* Publish products on eBay
* Revise, relist, end items on eBay
* Integration with the stock moves
* Automatic creation of sales order and invoices

  """,

  'author': "Odoo SA",
  'website': "https://www.odoo.com",

  # Categories can be used to filter modules in modules listing
  # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
  # for the full list
  'category': 'Sales',
  'version': '1.0',

  # any module necessary for this one to work correctly
  'depends': ['base', 'sale', 'stock', 'delivery', 'document'],
  'external_dependencies': {'python': ['ebaysdk']},

  # always loaded
  'data': [
      'security/ir.model.access.csv',

      'views/product.xml',
      'views/res_config.xml',
      'views/res_partner.xml',
      'views/ebay_category.xml',
      'views/stock_picking.xml',
      'views/data_template.xml',
      'sale_ebay_cron.xml',
      'ebay_data.xml',
      'data/product_data.xml'
  ],
  # only loaded in demonstration mode
  'demo': [
  ],
  'js': ['static/src/js/*.js'],
  'css': ['static/src/css/*.css'],
  'qweb': ['static/src/xml/*.xml'],
  'application': False,
    'license': 'OEEL-1',
}
