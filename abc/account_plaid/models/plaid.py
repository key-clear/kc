# -*- coding: utf-8 -*-
import requests
import json
import datetime
import logging

from openerp import models, api, fields
from openerp.tools.translate import _
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

_logger = logging.getLogger(__name__)

class OnlineInstitution(models.Model):
    _inherit = 'online.institution'

    type = fields.Selection(selection_add=[('plaid', 'Plaid')])

class OnlineSyncConfig(models.TransientModel):
    _inherit = 'account.journal.onlinesync.config'

    plaid_account_id = fields.Many2one('online.account', related='online_account_id', readonly=True)

class PlaidAccountJournal(models.Model):
    _inherit = 'account.journal'

    def _get_plaid_credentials(self):
        ICP_obj = self.env['ir.config_parameter'].sudo()
        login = ICP_obj.get_param('plaid_id') or self._cr.dbname
        secret = ICP_obj.get_param('plaid_secret') or ICP_obj.get_param('database.uuid')
        url = ICP_obj.get_param('plaid_service_url') or 'https://onlinesync.odoo.com/plaid/api'
        return {'login': login, 'secret': secret, 'url': url,}

    @api.multi
    def fetch(self, service, online_type, params, type_request="post"):
        if online_type != 'plaid':
            return super(PlaidAccountJournal, self).fetch(service, online_type, params, type_request=type_request)
        credentials = self._get_plaid_credentials()
        params['client_id'] = credentials['login']
        params['secret'] = credentials['secret']
        if not params['client_id'] or not params['secret']:
            raise UserError(_("You haven't configure your plaid account, please go to accounting/settings to configure it"))
        api = credentials['url']
        try:
            if type_request == "post":
                if self.online_account_id and self._context.get('patch', True):
                    if not params.get('access_token', False):
                        params['access_token'] = self.online_account_id.token
                    resp = requests.patch(api + service, params=params, timeout=20)
                else:
                    resp = requests.post(api + service, params=params, timeout=20)
            elif type_request == "get":
                #Trying to get information on institution, so we don't need to pass credential information in GET request
                resp = requests.get(api + service, timeout=20)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (400, 403):
                raise UserError(_('An error has occurred while trying to connect to plaid service') + ' ' + e.response.content)
            else:
                raise UserError(_('An error has occurred while trying to connect to plaid service') + ' ' + str(e.response.status_code))
        except Exception:
            _logger.exception('An error has occurred while trying to connect to Plaid service')
            raise UserError(_('An error has occurred while trying to connect to plaid service'))
        #Add request status code in response
        resp_json = json.loads(resp.text)
        resp_json['status_code'] = resp.status_code
        if resp_json.get('error', False):
            raise UserError(resp_json.get('error'))
        return json.dumps(resp_json)

    @api.multi
    def fetch_all_institution(self):
        try:
            resp = requests.get('https://api.plaid.com/institutions', timeout=20)
            resp.raise_for_status()
        except Exception:
            raise UserError(_('An error has occurred while trying to connect to plaid service'))
        institutions = self.env['online.institution'].search([('type', '=', 'plaid')])
        institution_name = [i.name for i in institutions]
        for institution in json.loads(resp.text):
            if institution['name'] not in institution_name:
                self.env['online.institution'].create({
                    'name': institution['name'],
                    'online_id': institution['id'],
                    'type': 'plaid',
                })
        return super(PlaidAccountJournal, self).fetch_all_institution()

class PlaidAccount(models.Model):
    _inherit = 'online.account'

    plaid_id = fields.Char("Plaid Account")
    token = fields.Char("Access Token")

    def online_sync(self):
        if (self.institution_id.type != 'plaid'):
            return super(PlaidAccount, self).online_sync()
            
        action_rec = self.env['ir.model.data'].xmlid_to_object('account.open_account_journal_dashboard_kanban')
        if action_rec:
            action = action_rec.read([])[0]

        if not self.last_sync:
            self.last_sync = str(datetime.datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT))
        if self.last_sync > str(datetime.datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)):
            return action
        # Fetch plaid.com
        # For all transactions since the last synchronization, for this journal
        params = {
            'access_token': self.token,
            'options': '{"gte": "' + self.last_sync + '", "account": "' + self.plaid_id + '"}',
        }
        ctx = dict(self._context or {})
        ctx['patch'] = False
        resp = self.journal_id.with_context(ctx).fetch("/connect/get", 'plaid', params)
        resp_json = json.loads(resp)
        # Three possible cases : no error, user error, or plaid.com error
        # There is no error
        if resp_json['status_code'] == 200:
            # Update the balance
            for account in resp_json['accounts']:
                if account['_id'] == self.plaid_id:
                    end_amount = account['balance']['current']
            # Prepare the transaction
            transactions = []
            if len(resp_json['transactions']) == 0:
                return action
            for transaction in resp_json['transactions']:
                trans = {
                    'id': transaction['_id'],
                    'date': transaction['date'],
                    'description': transaction['name'],
                    'amount': -1 * transaction['amount'],
                    'end_amount': end_amount,
                }
                if 'meta' in transaction and 'location' in transaction['meta']:
                    trans['location'] = transaction['meta']['location']
                transactions.append(trans)
            # Create the bank statement with the transactions
            return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_id)
        # Error from the user (auth, ...)
        elif resp_json['status_code'] >= 400 and resp_json['status_code'] < 500:
            subject = _("Error in synchronization")
            body = _("The synchronization of the journal %s with the plaid account %s has failed.<br>"
                     "The error message is :<br>%s") % (self.name, self.plaid_id.name, resp_json['resolve'])
            self.message_post(body=body, subject=subject)
            return action
        # Error with Plaid.com
        else:
            subject = _("Error with Plaid.com")
            body = _("The synchronization with Plaid.com failed. Please check the error : <br> %s") % resp_json
            self.message_post(body=body, subject=subject)
            return action
