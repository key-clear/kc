# -*- coding: utf-8 -*-
{
    'name': "VOIP Core",

    'summary': """
        Technical core for all the modules using the VOIP system.""",

    'description': """
        Technical core for all the modules using the VOIP system. 
        Contains the library needed in order to make the VOIP usable by other modules.
    """,

    'author': "Odoo S.A.",
    'website': "https://www.odoo.com",

    'price': 399,
    'currency': 'EUR',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Hidden/Dependency',
    'version': '1.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/voip_view.xml',
        'views/res_users_view.xml',
    ],
    'js': ['static/src/js/*.js'],
    'css': ['static/src/css/*.css'],
    'qweb': ['static/src/xml/*.xml'],
    'application' : False,
    'license': 'OEEL-1',
}