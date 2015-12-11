# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mass Mailing Themes',
    'summary': 'Design gorgeous mails with 8 high quality themes',
    'description': """
Design gorgeous mails with 8 high quality themes
    """,
    'version': '1.0',
    'sequence': 110,
    'website': 'https://www.odoo.com/page/mailing',
    'category': 'Marketing',
    'depends': [
        'mass_mailing',
    ],
    'data': [
        'theme_list.xml',
        'airmail_snippets.xml',
        'cleave_snippets.xml',
        'go_snippets.xml',
        'narrative_snippets.xml',
        'neopolitan_snippets.xml',
        'skyline_snippets.xml',
        'sunday_snippets.xml',
        'zenflat_snippets.xml',
    ],
    'qweb': [],
    'demo': [
    ],
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
