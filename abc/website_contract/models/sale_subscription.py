# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta
import logging
import time
import traceback
import uuid

from openerp import api, fields, models
from openerp.exceptions import ValidationError
from openerp.osv.query import Query

_logger = logging.getLogger(__name__)


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    uuid = fields.Char('Account UUID', default=lambda s: uuid.uuid4(), copy=False, required=True)
    website_url = fields.Char('Website URL', compute='_website_url', help='The full URL to access the document through the website.')
    recurring_mandatory_lines = fields.Many2many('sale.subscription.line', compute="_compute_options")
    recurring_option_lines = fields.Many2many('sale.subscription.line', compute="_compute_options")
    recurring_inactive_lines = fields.Many2many('sale.subscription.line.option', compute="_compute_options")
    recurring_custom_lines = fields.Many2many('sale.subscription.line', compute="_compute_options")
    user_closable = fields.Boolean(string="Closable by customer", help="If checked, the user will be able to close his account from the frontend")
    payment_method_id = fields.Many2one('payment.method', 'Payment Method', help='If not set, the default payment method of the partner will be used.', domain="[('partner_id','=',partner_id)]")
    payment_mandatory = fields.Boolean('Automatic Payment', help='If set, payments will be made automatically and invoices will not be generated if payment attempts are unsuccessful.')
    # add tax calculation
    recurring_amount_tax = fields.Float('Taxes', compute="_amount_all")
    recurring_amount_total = fields.Float('Total', compute="_amount_all")
    # Fields that only matters on template
    plan_description = fields.Html(string='Plan Description', help="Describe this contract in a few lines",)
    user_selectable = fields.Boolean(string='Allow Online Order', default="True", help="""Leave this unchecked if you don't want this contract template to be available to the customer in the frontend (for a free trial, for example)""")
    option_invoice_line_ids = fields.One2many('sale.subscription.line.option', inverse_name='analytic_account_id', string='Optional Lines', copy=True)
    partial_invoice = fields.Boolean(string="Partial Invoice", help="If set, option upgrades are invoiced for the remainder of the current invoicing period.")

    _sql_constraints = [
        ('uuid_uniq', 'unique (uuid)', """UUIDs (Universally Unique IDentifier) for Sale Subscriptions should be unique!"""),
    ]

    def _set_default_value_on_column(self, cr, column_name, context=None):
        # to avoid generating a single default uuid when installing the module,
        # we need to set the default row by row for this column
        if column_name == "uuid":
            _logger.debug("Table '%s': setting default value of new column %s to unique values for each row",
                          self._table, column_name)
            cr.execute("SELECT id FROM %s WHERE uuid IS NULL" % self._table)
            acc_ids = cr.dictfetchall()
            query_list = [{'id': acc_id['id'], 'uuid': str(uuid.uuid4())} for acc_id in acc_ids]
            query = 'UPDATE ' + self._table + ' SET uuid = %(uuid)s WHERE id = %(id)s;'
            cr._obj.executemany(query, query_list)
            cr.commit()

        else:
            super(SaleSubscription, self)._set_default_value_on_column(cr, column_name, context=context)

    @api.depends('recurring_invoice_line_ids')
    def _amount_all(self):
        for account in self:
            val = val1 = 0.0
            cur = account.pricelist_id.currency_id
            for line in account.recurring_invoice_line_ids:
                val1 += line.price_subtotal
                val += line._amount_line_tax()
            account.recurring_amount_tax = cur.round(val)
            account.recurring_amount_total = account.recurring_amount_tax + account.recurring_total

    @api.depends('uuid')
    def _website_url(self):
        for account in self:
            if account.type == 'contract':
                account.website_url = '/my/contract/%s/%s' % (self.id, self.uuid)
            elif account.type == 'template':
                account.website_url = '/my/template/%s' % (self.id)

    @api.multi
    def open_website_url(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.website_url,
            'target': 'self',
        }

    def add_option(self, option_id):
        option = self.env['sale.subscription.line.option'].browse(option_id)
        if option not in self.template_id.option_invoice_line_ids:
            return False
        values = {
            'product_id': option.product_id.id,
            'analytic_account_id': self.id,
            'name': option.name,
            'sold_quantity': option.quantity,
            'uom_id': option.uom_id.id,
            'price_unit': self.pricelist_id.with_context({'uom': option.uom_id.id}).price_get(option.product_id.id, 1)[self.pricelist_id.id]
        }
        self.write({'recurring_invoice_line_ids': [(0, 0, values)]})
        return True

    def remove_option(self, option_id):
        opt_line = self.env['sale.subscription.line.option'].browse(option_id)
        if not self.template_id or opt_line not in self.template_id.option_invoice_line_ids:
            return False
        for line in self.recurring_invoice_line_ids:
            if opt_line.product_id == line.product_id:
                self.write({'recurring_invoice_line_ids': [(2, line.id)]})
                return True
        return False

    def change_subscription(self, new_template_id):
        """Change the template of a subscription
        - add the recurring_invoice_line_ids linked to the new template
        - remove the recurring_invoice_line_ids linked to the current template
        - remove lines that are not in the new template option_invoice_line_ids
        - adapt price of lines that are in the option_invoice_line_ids of both templates
        - other invoicing lines are left unchanged"""
        rec_lines_to_remove = []
        rec_lines_to_add = []
        rec_lines_to_modify = []
        modified_products = []
        new_template = self.browse(new_template_id)
        new_options = {
            line.product_id: {
                'price_unit': self.pricelist_id.with_context({'uom': line.uom_id.id}).price_get(line.product_id.id, 1)[self.pricelist_id.id],
                'uom_id': line.uom_id.id
            } for line in new_template.option_invoice_line_ids
        }
        new_mandatory = {
            line.product_id: {
                'price_unit': self.pricelist_id.with_context({'uom': line.uom_id.id}).price_get(line.product_id.id, 1)[self.pricelist_id.id],
                'uom_id': line.uom_id.id
            } for line in new_template.recurring_invoice_line_ids
        }
        # adapt prices of mandatory lines if products are the same, delete the rest
        for line in self.recurring_invoice_line_ids:
            if line.product_id in [tmp_line.product_id for tmp_line in self.template_id.recurring_invoice_line_ids]:
                if line.product_id in new_mandatory:
                    rec_lines_to_modify.append((1, line.id, new_mandatory.get(line.product_id)))
                    modified_products.append(line.product_id.id)
                else:
                    rec_lines_to_remove.append((2, line.id))
            elif line.product_id in [tmp_option.product_id for tmp_option in self.template_id.option_invoice_line_ids]:
                # remove options in the old template that are not in the new one (i.e. options that do not apply anymore)
                if line.product_id in new_options:
                    rec_lines_to_modify.append((1, line.id, new_options.get(line.product_id)))
                    modified_products.append(line.product_id.id)
                # adapt prices of options
                else:
                    rec_lines_to_remove.append((2, line.id))
        # add missing mandatory lines
        for line in new_template.recurring_invoice_line_ids:
            if line.product_id.id not in modified_products and line.product_id not in [cur_line.product_id for cur_line in self.recurring_invoice_line_ids]:
                rec_lines_to_add = [(0, 0, {
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'name': line.name,
                    'sold_quantity': line.quantity,
                    'price_unit': self.pricelist_id.with_context({'uom': line.uom_id.id}).price_get(line.product_id.id, 1)[self.pricelist_id.id],
                    'analytic_account_id': self.id,
                })]
        values = {
            'recurring_invoice_line_ids': rec_lines_to_add + rec_lines_to_modify + rec_lines_to_remove,
            'recurring_rule_type': new_template.recurring_rule_type
        }
        self.sudo().write(self.on_change_template(new_template_id).get('value', dict()))
        self.sudo().write(values)
        self.template_id = new_template

    def _compute_options(self):
        """ Set fields with filter options:
            - recurring_mandatory_lines = all the recurring lines that are recurring lines on the template
            - recurring_option_lines = all the contract lines that are option lines on the template
            - recurring_custom_lines = all the recurring lines that are not part of the template
            - recurring_inactive_lines = all the template_id's options that are not set on the contract
        """
        for account in self:
            if account.template_id:
                account.recurring_mandatory_lines = account.recurring_invoice_line_ids.filtered(lambda r: r.product_id in [inv_line.product_id for inv_line in account.sudo().template_id.recurring_invoice_line_ids])
                account.recurring_option_lines = account.recurring_invoice_line_ids.filtered(lambda r: r.product_id in [line.product_id for line in account.sudo().template_id.option_invoice_line_ids])
                account.recurring_custom_lines = account.recurring_invoice_line_ids.filtered(lambda r: r.product_id not in [opt_line.product_id for opt_line in account.sudo().template_id.option_invoice_line_ids]+[inv_line.product_id for inv_line in account.sudo().template_id.recurring_invoice_line_ids])
                account.recurring_inactive_lines = account.sudo().template_id.option_invoice_line_ids.filtered(lambda r: r.product_id not in [line.product_id for line in account.recurring_invoice_line_ids] and r.portal_access != 'invisible')

    def partial_invoice_line(self, sale_order, option_line, refund=False):
        """ Add an invoice line on the sale order for the specified option and add a discount
        to take the partial recurring period into account """
        order_line_obj = self.env['sale.order.line']
        if option_line.product_id in [line.product_id for line in sale_order.order_line]:
            return True
        values = {
            'order_id': sale_order.id,
            'product_id': option_line.product_id.id,
            'product_uom_qty': option_line.quantity,
            'product_uom': option_line.uom_id.id,
            'discount': (1 - self.partial_recurring_invoice_ratio()) * 100,
            'price_unit': self.pricelist_id.with_context({'uom': option_line.uom_id.id}).price_get(option_line.product_id.id, 1)[self.pricelist_id.id],
            'force_price': True,
            'name': option_line.name,
        }
        return order_line_obj.create(values)

    def partial_recurring_invoice_ratio(self):
        """Computes the ratio of the amount of time remaining in the current invoicing period
        over the total length of said invoicing period"""
        today = datetime.date.today()
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        invoicing_period = relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        recurring_next_invoice = fields.Date.from_string(self.recurring_next_date)
        recurring_last_invoice = recurring_next_invoice - invoicing_period
        time_to_invoice = recurring_next_invoice - today - datetime.timedelta(days=1)
        ratio = float(time_to_invoice.days) / float((recurring_next_invoice - recurring_last_invoice).days)
        return ratio

    # online payments
    @api.one
    def _do_payment(self, payment_method, invoice, two_steps_sec=True):
        tx_obj = self.env['payment.transaction']
        reference = "CONTRACT-%s-%s" % (self.id, datetime.datetime.now().strftime('%y%m%d_%H%M%S'))
        values = {
            'amount': invoice.amount_total,
            'acquirer_id': payment_method.acquirer_id.id,
            'type': 'server2server',
            'currency_id': invoice.currency_id.id,
            'reference': reference,
            'payment_method_id': payment_method.id,
            'partner_id': self.partner_id.id,
            'partner_country_id': self.partner_id.country_id.id,
            'invoice_id': invoice.id,
            'callback_eval': "self.env['sale.subscription'].reconcile_pending_transaction(%s,self,self.invoice_id)" % self.id
        }

        tx = tx_obj.create(values)

        baseurl = self.env['ir.config_parameter'].get_param('web.base.url')
        payment_secure = {'3d_secure': two_steps_sec,
                          'accept_url': baseurl + '/my/contract/%s/payment/%s/accept/' % (self.id, tx.id),
                          'decline_url': baseurl + '/my/contract/%s/payment/%s/decline/' % (self.id, tx.id),
                          'exception_url': baseurl + '/my/contract/%s/payment/%s/exception/' % (self.id, tx.id),
                          }
        tx.s2s_do_transaction(**payment_secure)
        return tx

    @api.model
    def reconcile_pending_transaction(self, contract_id, tx, invoice):
        contract = self.browse(contract_id)
        if tx.state == 'done':
            if tx.acquirer_id.journal_id:
                invoice.signal_workflow('invoice_open')
                journal = tx.acquirer_id.journal_id
                invoice.pay_and_reconcile(journal, pay_amount=tx.amount)
            contract.increment_period()
            contract.write({'state': 'open', 'date': False})
        else:
            invoice.action_cancel()
            invoice.unlink()

    @api.multi
    def _recurring_create_invoice(self, automatic=False):
        cr = self.env.cr
        invoice_ids = []
        current_date = time.strftime('%Y-%m-%d')
        imd_res = self.env['ir.model.data']
        template_res = self.env['mail.template']
        if len(self) > 0:
            contracts = self
        else:
            domain = [('recurring_next_date', '<=', current_date),
                      ('state', 'in', ['open', 'pending']),
                      ('type', '=', 'contract')]
            contracts = self.search(domain)
        if contracts:
            cr.execute('SELECT a.company_id, array_agg(sub.id) as ids FROM sale_subscription as sub JOIN account_analytic_account as a ON sub.analytic_account_id = a.id WHERE sub.id IN %s GROUP BY a.company_id', (tuple(contracts.ids),))
            for company_id, ids in cr.fetchall():
                for contract in self.with_context(dict(self.env.context, company_id=company_id, force_company=company_id)).browse(ids):
                    cr.commit()
                    # payment + invoice (only by cron)
                    if contract.template_id and contract.template_id.payment_mandatory and contract.recurring_total and automatic:
                        try:
                            payment_method = contract.payment_method_id
                            if payment_method:
                                invoice_values = self._prepare_invoice(contract)
                                new_invoice = self.env['account.invoice'].create(invoice_values)
                                new_invoice.compute_taxes()
                                tx = contract._do_payment(payment_method, new_invoice, two_steps_sec=False)[0]
                                # commit change as soon as we try the payment so we have a trace somewhere
                                cr.commit()
                                if tx.state == 'done':
                                    contract.reconcile_pending_transaction(contract.id, tx, new_invoice)
                                    contract.send_success_mail(tx, new_invoice)
                                    msg_body = 'Automatic payment succeeded. Payment reference: %s; Amount: %s.' % (tx.reference, tx.amount)
                                    contract.message_post(body=msg_body)
                                    cr.commit()
                                else:
                                    cr.rollback()
                                    amount = contract.recurring_total
                                    date_close = datetime.datetime.strptime(contract.recurring_next_date, "%Y-%m-%d") + relativedelta(days=15)
                                    close_contract = current_date >= date_close.strftime('%Y-%m-%d')
                                    email_context = self.env.context.copy()
                                    email_context.update({
                                        'payment_method': contract.payment_method_id and contract.payment_method_id.name,
                                        'renewed': False,
                                        'total_amount': amount,
                                        'email_to': contract.partner_id.email,
                                        'code': contract.code,
                                        'currency': contract.pricelist_id.currency_id.name,
                                        'date_end': contract.date,
                                        'date_close': date_close.date()
                                    })
                                    _logger.error('Fail to create recurring invoice for contract %s', contract.code)
                                    if close_contract:
                                        _, template_id = imd_res.get_object_reference('website_contract', 'email_payment_close')
                                        template = template_res.browse(template_id)
                                        template.with_context(email_context).send_mail(contract.id)
                                        _logger.debug("Sending Contract Closure Mail to %s for contract %s and closing contract", contract.partner_id.email, contract.id)
                                        msg_body = 'Automatic payment failed after multiple attempts. Contract closed automatically.'
                                        self.message_post(body=msg_body)
                                    else:
                                        _, template_id = imd_res.get_object_reference('website_contract', 'email_payment_reminder')
                                        if (datetime.datetime.today() - datetime.datetime.strptime(contract.recurring_next_date, '%Y-%m-%d')).days in [0, 3, 7, 14]:
                                            template = template_res.browse(template_id)
                                            template.with_context(email_context).send_mail(contract.id)
                                            _logger.debug("Sending Payment Failure Mail to %s for contract %s and setting contract to pending", contract.partner_id.email, contract.id)
                                            msg_body = 'Automatic payment failed. Contract set to "To Renew".'
                                            self.message_post(body=msg_body)
                                    contract.write({'state': 'close' if close_contract else 'pending'})
                                    cr.commit()
                        except Exception:
                            cr.rollback()
                            # we assume that the payment is run only once a day
                            last_tx = self.env['payment.transaction'].search([('reference', 'like', 'CONTRACT-%s-%s' % (contract.id, datetime.date.today().strftime('%y%m%d')))], limit=1)
                            error_message = "Error during renewal of contract %s (%s)" % (contract.code, 'Payment recorded: %s' % last_tx.reference if last_tx and last_tx.state == 'done' else 'No payment recorded.')
                            traceback_message = traceback.format_exc()
                            _logger.error(error_message)
                            _logger.error(traceback_message)

                    # invoice only
                    else:
                        try:
                            invoice_values = self._prepare_invoice(contract)
                            new_invoice = self.env['account.invoice'].create(invoice_values)
                            new_invoice.compute_taxes()
                            invoice_ids.append(new_invoice.id)
                            next_date = datetime.datetime.strptime(contract.recurring_next_date or current_date, "%Y-%m-%d")
                            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
                            invoicing_period = relativedelta(**{periods[contract.recurring_rule_type]: contract.recurring_interval})
                            new_date = next_date + invoicing_period
                            contract.write({'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                            if automatic:
                                cr.commit()
                        except Exception:
                            if automatic:
                                cr.rollback()
                                _logger.exception('Fail to create recurring invoice for contract %s', contract.code)
                            else:
                                raise
        return invoice_ids

    def send_success_mail(self, tx, invoice):
        imd_res = self.env['ir.model.data']
        template_res = self.env['mail.template']
        current_date = time.strftime('%Y-%m-%d')
        next_date = datetime.datetime.strptime(self.recurring_next_date or current_date, "%Y-%m-%d")
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        invoicing_period = relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        new_date = next_date + invoicing_period
        _, template_id = imd_res.get_object_reference('website_contract', 'email_payment_success')
        email_context = self.env.context.copy()
        email_context.update({
            'payment_method': self.payment_method_id.name,
            'renewed': True,
            'total_amount': tx.amount,
            'next_date': new_date.date(),
            'previous_date': self.recurring_next_date,
            'email_to': self.partner_id.email,
            'code': self.code,
            'currency': self.pricelist_id.currency_id.name,
            'date_end': self.date,
        })
        _logger.debug("Sending Payment Confirmation Mail to %s for contract %s", self.partner_id.email, self.id)
        template = template_res.browse(template_id)
        return template.with_context(email_context).send_mail(invoice.id)


class SaleSusbcriptionOption(models.Model):
    _inherit = "sale.subscription.line"
    _name = "sale.subscription.line.option"

    portal_access = fields.Selection(
        string='Portal Access',
        selection=[
            ('invisible', 'Invisible'),
            ('none', 'Restricted'),
            ('upgrade', 'Upgrade only'),
            ('both', 'Upgrade and Downgrade')],
        required=True,
        default='none',
        help="Restricted: The customer must ask a Sales Rep to add or remove this option\n"
             "Upgrade Only: The customer can add the option himself but must ask to remove it\n"
             "Upgrade and Downgrade: The customer can add or remove this option himself\n"
             "Invisible: The customer doesn't see the option; however it gets carried away when switching subscription template")
    is_authorized = fields.Boolean(compute="_compute_is_authorized", search="_search_is_authorized")

    @api.constrains('product_id', 'analytic_account_id')
    def _check_unicity(self):
        for line in self:
            for opt_line in line.analytic_account_id.option_invoice_line_ids:
                if line.product_id == opt_line.product_id and line.id != opt_line.id:
                    raise ValidationError("You cannot use the same product as an option twice for the same subscription template.")

    @api.depends('portal_access')
    def _compute_is_authorized(self):
        for option in self:
            option.is_authorized = bool(self.env['sale.subscription'].search_count([('template_id', '=', option.analytic_account_id.id)]))

    def _search_is_authorized(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise ValueError('Invalid operator: %s' % (operator,))

        SS = self.env['sale.subscription']
        tbls = (self._table, SS._table)
        query = Query(tbls, ["%s.analytic_account_id = %s.template_id" % tbls], [])
        SS._apply_ir_rules(query)

        from_clause, where_clause, where_clause_params = query.get_sql()

        self.env.cr.execute("""
            SELECT {self}.id
              FROM {from_}
             WHERE {where}
        """.format(self=self._table, from_=from_clause, where=where_clause), where_clause_params)
        ids = [i[0] for i in self.env.cr.fetchall()]

        op = 'in' if (operator == '=' and value) or (operator != '=' and not value) else 'not in'
        return [('id', op, ids)]


class SaleSubscriptionLine(models.Model):
    _inherit = "sale.subscription.line"

    def get_template_option_line(self):
        """ Return the account.analytic.invoice.line.option which has the same product_id as
        the invoice line"""
        if not self.analytic_account_id and not self.analytic_account_id.template_id:
            return False
        template = self.analytic_account_id.template_id
        return template.sudo().option_invoice_line_ids.filtered(lambda r: r.product_id == self.product_id)

    def _amount_line_tax(self):
        self.ensure_one()
        val = 0.0
        product = self.product_id
        product_tmp = product.sudo().product_tmpl_id
        for tax in product_tmp.taxes_id:
            fpos_obj = self.env['account.fiscal.position']
            partner = self.analytic_account_id.partner_id
            fpos_id = fpos_obj.get_fiscal_position(partner.id)
            fpos = fpos_obj.browse(fpos_id)
            if fpos:
                tax = fpos.map_tax(tax)
            compute_vals = tax.compute_all(self.price_unit * (1 - (self.discount or 0.0) / 100.0), self.analytic_account_id.currency_id, self.quantity, product, partner)['taxes']
            if compute_vals:
                val += compute_vals[0].get('amount', 0)
        return val
