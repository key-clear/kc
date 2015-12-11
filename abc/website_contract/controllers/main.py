# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import NotFound

from openerp import http
from openerp.http import request
from openerp.tools.translate import _

from openerp.addons.website_portal.controllers.main import website_account
from openerp.addons.website_quote.controllers.main import sale_quote


class website_account(website_account):
    @http.route(['/my/home'], type='http', auth="user", website=True)
    def account(self, **kw):
        """ Add contract details to main account page """
        response = super(website_account, self).account()
        partner = request.env.user.partner_id
        account_res = request.env['sale.subscription']
        accounts = account_res.search([
            ('partner_id.id', 'in', [partner.id, partner.commercial_partner_id.id]),
            ('state', '!=', 'cancelled'),
        ])
        response.qcontext.update({'accounts': accounts})

        return response


class website_contract(http.Controller):
    @http.route(['/my/contract/<int:account_id>/',
                 '/my/contract/<int:account_id>/<string:uuid>'], type='http', auth="public", website=True)
    def contract(self, account_id, uuid='', message='', message_class='', **kw):
        request.env['res.users'].browse(request.uid).has_group('base.group_sale_salesman')
        account_res = request.env['sale.subscription']
        if uuid:
            account = account_res.sudo().browse(account_id)
            if uuid != account.uuid or account.state == 'cancelled':
                raise NotFound()
            if request.uid == account.partner_id.user_id.id:
                account = account_res.browse(account_id)
        else:
            account = account_res.browse(account_id)

        acquirers = list(request.env['payment.acquirer'].search([('website_published', '=', True), ('registration_view_template_id', '!=', False)]))
        acc_pm = account.payment_method_id
        part_pms = account.partner_id.payment_method_ids
        inactive_options = account.sudo().recurring_inactive_lines
        display_close = account.template_id.sudo().user_closable and account.state != 'close'
        active_plan = account.template_id.sudo()
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        invoicing_period = relativedelta(**{periods[account.recurring_rule_type]: account.recurring_interval})
        limit_date = datetime.datetime.strptime(account.recurring_next_date, '%Y-%m-%d') + invoicing_period
        allow_reopen = datetime.datetime.today() < limit_date
        dummy, action = request.env['ir.model.data'].get_object_reference('sale_contract', 'sale_subscription_action')
        account_templates = account_res.sudo().search([
            ('type', '=', 'template'),
            ('user_selectable', '=', True),
            ('id', '!=', active_plan.id),
            ('state', '=', 'open'),
            ('tag_ids', 'in', account.sudo().template_id.tag_ids.ids)
        ])
        values = {
            'account': account,
            'display_close': display_close,
            'close_reasons': request.env['sale.subscription.close.reason'].search([]),
            'allow_reopen': allow_reopen,
            'inactive_options': inactive_options,
            'payment_mandatory': active_plan.payment_mandatory,
            'user': request.env.user,
            'acquirers': acquirers,
            'acc_pm': acc_pm,
            'part_pms': part_pms,
            'is_salesman': request.env['res.users'].sudo(request.uid).has_group('base.group_sale_salesman'),
            'action': action,
            'message': message,
            'message_class': message_class,
            'display_change_plan': len(account_templates) > 0,
            'pricelist': account.pricelist_id.sudo(),
        }
        render_context = {
            'json': True,
            'submit_class': 'btn btn-primary btn-sm mb8 mt8 pull-right',
            'submit_txt': 'Pay Subscription',
            'bootstrap_formatting': True
        }
        render_context = dict(values.items() + render_context.items())
        for acquirer in acquirers:
            acquirer.form = acquirer.sudo()._registration_render(account.partner_id.id, render_context)[0]
        return request.website.render("website_contract.contract", values)

    payment_succes_msg = 'message=Thank you, your payment has been validated.&message_class=alert-success'
    payment_fail_msg = 'message=There was an error with your payment, please try with another payment method or contact us.&message_class=alert-danger'

    @http.route(['/my/contract/payment/<int:account_id>/',
                 '/my/contract/payment/<int:account_id>/<string:uuid>'], type='http', auth="public", methods=['POST'], website=True)
    def payment(self, account_id, uuid=None, **kw):
        account_res = request.env['sale.subscription']
        invoice_res = request.env['account.invoice']
        get_param = ''
        if uuid:
            account = account_res.sudo().browse(account_id)
            if uuid != account.uuid:
                raise NotFound()
        else:
            account = account_res.browse(account_id)

        # no change
        if int(kw.get('pay_meth'), 0) > 0:
            account.payment_method_id = int(kw['pay_meth'])

        # we can't call _recurring_invoice because we'd miss 3DS, redoing the whole payment here
        payment_method = account.payment_method_id
        if payment_method:
            invoice_values = account_res.sudo()._prepare_invoice(account)
            new_invoice = invoice_res.sudo().create(invoice_values)
            new_invoice.compute_taxes()
            tx = account.sudo()._do_payment(payment_method, new_invoice)[0]
            if tx.html_3ds:
                return tx.html_3ds
            get_param = self.payment_succes_msg if tx.state == 'done' else self.payment_fail_msg
            if tx.state == 'done':
                account.send_success_mail(tx, new_invoice)
                msg_body = 'Manual payment succeeded. Payment reference: %s; Amount: %s.' % (tx.reference, tx.amount)
                account.message_post(body=msg_body)
            else:
                new_invoice.unlink()

        return request.redirect('/my/contract/%s/%s?%s' % (account.id, account.uuid, get_param))

    # 3DS controllers
    # transaction began as s2s but we receive a form reply
    @http.route(['/my/contract/<int:account_id>/payment/<int:tx_id>/accept/',
                 '/my/contract/<int:account_id>/payment/<int:tx_id>/decline/',
                 '/my/contract/<int:account_id>/payment/<int:tx_id>/exception/'], type='http', auth="public", website=True)
    def payment_accept(self, account_id, tx_id, **kw):
        account_res = request.env['sale.subscription']
        tx_res = request.env['payment.transaction']

        account = account_res.sudo().browse(account_id)
        tx = tx_res.sudo().browse(tx_id)

        get_param = self.payment_succes_msg if tx.state == 'done' else self.payment_fail_msg

        return request.redirect('/my/contract/%s/%s?%s' % (account.id, account.uuid, get_param))

    @http.route(['/my/contract/<int:account_id>/change'], type='http', auth="public", website=True)
    def change_contract(self, account_id, uuid=None, **kw):
        account_res = request.env['sale.subscription']
        account = account_res.sudo().browse(account_id)
        if uuid != account.uuid:
            raise NotFound()
        if account.state == 'close':
            return request.redirect('/my/contract/%s' % account_id)
        if kw.get('new_template_id'):
            new_template_id = int(kw.get('new_template_id'))
            periods = {'daily': 'Day(s)', 'weekly': 'Week(s)', 'monthly': 'Month(s)', 'yearly': 'Year(s)'}
            msg_before = [account.sudo().template_id.name,
                          str(account.recurring_total),
                          str(account.recurring_interval) + ' ' + str(periods[account.recurring_rule_type])]
            account.sudo().change_subscription(new_template_id)
            msg_after = [account.sudo().template_id.name,
                         str(account.recurring_total),
                         str(account.recurring_interval) + ' ' + str(periods[account.recurring_rule_type])]
            msg_body = request.registry['ir.ui.view'].render(request.cr, request.uid, ['website_contract.chatter_change_contract'],
                                                             values={'msg_before': msg_before, 'msg_after': msg_after},
                                                             context=request.context)
            # price options are about to change and are not propagated to existing sale order: reset the SO
            order = request.website.sudo().sale_get_order()
            if order:
                order.reset_project_id()
            account.message_post(body=msg_body)
            return request.redirect('/my/contract/%s/%s' % (account.id, account.uuid))
        account_templates = account_res.sudo().search([
            ('type', '=', 'template'),
            ('state', '=', 'open'),
            ('user_selectable', '=', True),
            ('tag_ids', 'in', account.template_id.tag_ids.ids)
        ])
        values = {
            'account': account,
            'pricelist': account.pricelist_id,
            'active_template': account.template_id,
            'inactive_templates': account_templates,
            'user': request.env.user,
        }
        return request.website.render("website_contract.change_template", values)

    @http.route(['/my/contract/<int:account_id>/close'], type='http', methods=["POST"], auth="public", website=True)
    def close_account(self, account_id, uuid=None, **kw):
        account_res = request.env['sale.subscription']

        if uuid:
            account = account_res.sudo().browse(account_id)
            if uuid != account.uuid:
                raise NotFound()
        else:
            account = account_res.browse(account_id)

        if account.sudo().template_id.user_closable:
            close_reason = request.env['sale.subscription.close.reason'].browse(int(kw.get('close_reason_id')))
            account.close_reason_id = close_reason
            if kw.get('closing_text'):
                account.message_post(_('Closing text : ') + kw.get('closing_text'))
            account.set_close()
            account.date = datetime.date.today().strftime('%Y-%m-%d')
        return request.redirect('/my/home')

    @http.route(['/my/contract/<int:account_id>/add_option'], type='http', methods=["POST"], auth="public", website=True)
    def add_option(self, account_id, uuid=None, **kw):
        option_res = request.env['sale.subscription.line.option']
        account_res = request.env['sale.subscription']
        if uuid:
            account = account_res.sudo().browse(account_id)
            if uuid != account.uuid:
                raise NotFound()
        else:
            account = account_res.browse(account_id)
        new_option_id = int(kw.get('new_option_id'))
        new_option = option_res.sudo().browse(new_option_id)
        if not new_option.price_unit or not new_option.price_unit * account.partial_recurring_invoice_ratio() or not account.template_id.partial_invoice:
            account.sudo().add_option(new_option_id)
            msg_body = request.registry['ir.ui.view'].render(request.cr, request.uid, ['website_contract.chatter_add_option'],
                                                             values={'new_option': new_option},
                                                             context=request.context)
            account.message_post(body=msg_body)
        return request.redirect('/my/contract/%s/%s' % (account.id, account.uuid))

    @http.route(['/my/contract/<int:account_id>/remove_option'], type='http', methods=["POST"], auth="public", website=True)
    def remove_option(self, account_id, uuid=None, **kw):
        remove_option_id = int(kw.get('remove_option_id'))
        option_res = request.env['sale.subscription.line.option']
        account_res = request.env['sale.subscription']
        if uuid:
            remove_option = option_res.sudo().browse(remove_option_id)
            account = account_res.sudo().browse(account_id)
            if uuid != account.uuid:
                raise NotFound()
        else:
            remove_option = option_res.browse(remove_option_id)
            account = account_res.browse(account_id)
        if remove_option.portal_access != "both" and not request.env.user.has_group('base.group_sale_salesman'):
            return request.render("website.403")
        account.sudo().remove_option(remove_option_id)
        msg_body = request.registry['ir.ui.view'].render(request.cr, request.uid, ['website_contract.chatter_remove_option'],
                                                         values={'remove_option': remove_option},
                                                         context=request.context)
        account.message_post(body=msg_body)
        return request.redirect('/my/contract/%s/%s' % (account.id, account.uuid))

    @http.route(['/my/contract/<int:account_id>/pay_option'], type='http', methods=["POST"], auth="public", website=True)
    def pay_option(self, account_id, **kw):
        order = request.website.sale_get_order(force_create=True)
        order.set_project_id(account_id)
        new_option_id = int(kw.get('new_option_id'))
        new_option = request.env['sale.subscription.line.option'].sudo().browse(new_option_id)
        account = request.env['sale.subscription'].browse(account_id)
        account.sudo().partial_invoice_line(order, new_option)

        return request.redirect("/shop/cart")

    @http.route(['/my/template/<int:template_id>'], type='http', auth="user", website=True)
    def view_template(self, template_id, **kw):
        account_res = request.env['sale.subscription']
        dummy, action = request.env['ir.model.data'].get_object_reference('sale_contract', 'sale_subscription_action_template')
        template = account_res.browse(template_id)
        values = {
            'template': template,
            'action': action
        }
        if template.type == 'template':
            return request.website.render('website_contract.preview_template', values)
        else:
            raise NotFound()


class sale_quote_contract(sale_quote):
    @http.route([
        "/quote/<int:order_id>",
        "/quote/<int:order_id>/<token>"
    ], type='http', auth="public", website=True)
    def view(self, order_id, pdf=None, token=None, message=False, **kw):
        response = super(sale_quote_contract, self).view(order_id, pdf, token, message, **kw)
        if 'quotation' in response.qcontext:  # check if token identification was ok in super
            order = response.qcontext['quotation']
            recurring_products = True in [line.product_id.recurring_invoice for line in order.sudo().order_line]
            tx_type = 'form_save' if recurring_products else 'form'
            # re-render the payment buttons with the proper tx_type if recurring products
            if 'acquirers' in response.qcontext and tx_type != 'form':
                render_ctx = dict(request.context, submit_class='btn btn-primary', submit_txt=_('Pay & Confirm'))
                for acquirer in response.qcontext['acquirers']:
                    acquirer.button = acquirer.with_context(render_ctx).render(
                        order.name,
                        order.amount_total,
                        order.pricelist_id.currency_id.id,
                        values={
                            'return_url': '/quote/%s/%s' % (order_id, token) if token else '/quote/%s' % order_id,
                            'type': tx_type,
                            'alias_usage': _('If we store your payment information on our server, subscription payments will be made automatically.'),
                            'partner_id': order.partner_id.id,
                        })[0]
                    response.qcontext['recurring_products'] = recurring_products
        return response

    # note dbo: website_sale code
    @http.route(['/quote/<int:order_id>/transaction/<int:acquirer_id>'], type='json', auth="public", website=True)
    def payment_transaction(self, acquirer_id, order_id, **kw):
        """Let's use inheritance to change the tx type if there are recurring products in the order
        """
        response = super(sale_quote_contract, self).payment_transaction(acquirer_id, order_id)
        if isinstance(response, int):
            tx_id = response
            tx = request.env['payment.transaction'].sudo().browse(tx_id)
            order = request.env['sale.order'].sudo().browse(order_id)
            if True in [line.product_id.recurring_invoice for line in order.order_line]:
                tx.type = 'form_save'
        return response
