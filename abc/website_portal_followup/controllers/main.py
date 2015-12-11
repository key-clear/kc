# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import http
from openerp.http import request
from openerp.addons.website_portal.controllers.main import website_account


class website_account_followup(website_account):
    @http.route()
    def account(self, **kw):
        response = super(website_account_followup, self).account(**kw)
        partner = request.env.user.partner_id
        context_obj = request.env['account.report.context.followup']
        report_obj = request.env['account.followup.report']
        context_id = context_obj.search([('partner_id', '=', int(partner))], limit=1)
        if not context_id:
            context_id = context_obj.with_context(lang=partner.lang).create({'partner_id': int(partner)})
        context_id = context_id.sudo() # Needed to see the unreconciled_amls
        lines = report_obj.with_context(lang=partner.lang).get_lines(context_id, public=True)
        rcontext = {
            'context': context_id.with_context(lang=partner.lang, public=True),
            'report': report_obj.with_context(lang=partner.lang),
            'lines': lines,
            'mode': 'display',
        }
        response.qcontext.update(rcontext)
        return response
