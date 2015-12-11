# -*- coding: utf-8 -*-
{
    'name': "Odoo VOIP",

    'summary': """
        Automate calls transfers, logs and emails""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Odoo SA",
    'website': "https://www.odoo.com",
    
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Customer Relationship Management',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['voip','base','crm'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/crm_phonecall_to_phonecall_view.xml',
        'views/crm_voip.xml',
        'views/phonecall.xml',
        'views/opportunities.xml',
        'views/crm_voip_tip.xml',
        'views/res_config_view.xml',
        'views/res_partner_view.xml',
        'views/crm_phonecall_report_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',
    ],
    'js': ['static/src/js/*.js'],
    'css': ['static/src/css/*.css'],
    'qweb': ['static/src/xml/*.xml'],
    'images': ['static/description/voip.png'],
    'application' : True,
    'license': 'OEEL-1',
}