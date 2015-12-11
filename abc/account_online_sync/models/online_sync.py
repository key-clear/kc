# -*- coding: utf-8 -*-
import datetime

from openerp import api, fields, models
from openerp.tools.translate import _

"""
This module manage an "online account" for a journal. It can't be used in standalone,
other module have to be install (like Plaid or Yodlee). Theses modules must be given
for the online_account reference field. They manage how the bank statement are retrived
from a web service.
"""

class OnlineAccount(models.Model):
    """
    This class is used as an interface.
    It is used to save the state of the current online accout.
    """
    _name = 'online.account'

    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    journal_id = fields.Many2one('account.journal', required=True, string='Journal')
    last_sync = fields.Date("Last synchronization")
    institution_id = fields.Many2one('online.institution', related='journal_id.online_institution_id', store=True, string='Institution')

    @api.multi
    def online_sync(self):
        # This method must be implemented by plaid and yodlee services
        raise "Unimplemented"


class OnlineInstitution(models.Model):
    """
    This class represent an instution. The user can choice any of them.
    Create a record of this model allow the user to pick it.
    The fields are :
    - name = the displayed name
    - online_id = the name of the instution for the webservice
    - type = The type of service used behind, yodlee or plaid"
    """
    _name = 'online.institution'
    _order = 'type, name'

    name = fields.Char(required=True)
    online_id = fields.Char("Id", required=True)
    type = fields.Selection([], required=True)

    _sql_constraints = [
        ('name_unique', 'unique(online_id,type)', 'There can be only one record by bank')
    ]

class OnlineSyncConfig(models.TransientModel):
    _name = 'account.journal.onlinesync.config'

    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True)
    online_institution_id = fields.Many2one(related='journal_id.online_institution_id', string="Online Institution")
    online_account_id = fields.Many2one(related='journal_id.online_account_id', string="Online Account")
    online_id = fields.Char(related='online_institution_id.online_id', string="ID of the Online Institution")
    online_type = fields.Selection(related='online_institution_id.type', string="Type of the Online Institution", readonly=True)

    @api.multi
    def online_sync(self):
        return self.online_account_id.online_sync()

    @api.multi
    def remove_online_account(self):
        self.journal_id.remove_online_account()

    @api.model
    def default_get(self, fields):
        rec = super(OnlineSyncConfig, self).default_get(fields)
        context = dict(self._context or {})
        rec.update({
            'journal_id': context.get('active_id', False),
            # 'online_account_id': self.env['account.journal'].browse(context.get('active_id', False)).online_account_id.id,
        })
        return rec

    @api.multi
    def fetch_all_institution(self):
        self.journal_id.fetch_all_institution()

class AccountJournal(models.Model):
    _inherit = "account.journal"

    next_synchronization = fields.Datetime("Next synchronization", compute='_compute_next_synchronization')
    online_institution_id = fields.Many2one('online.institution', string="Online Institution")
    online_account_id = fields.Many2one('online.account', string='Online Account')
    online_id = fields.Char(related='online_institution_id.online_id', string="ID of the Online Institution", store=True)
    online_type = fields.Selection(related='online_institution_id.type', string="Type of the Online Institution", readonly=True)

    @api.multi
    def remove_online_account(self):
        account = self.online_account_id
        self.online_account_id = False
        self.write({'online_account_id': False})
        account.unlink()

    @api.multi
    def save_online_account(self, vals, online_institution_id):
        if self.online_account_id:
            self.remove_online_account()
        self.online_institution_id = online_institution_id
        online_account_id = self.env['online.account'].create(vals)
        self.online_account_id = online_account_id.id
        return online_account_id.online_sync()

    @api.multi
    def fetch(self, service, online_type, params, type_request="post"):
        # This method must be implemented by plaid and yodlee services
        raise "Unimplemented"

    @api.multi
    def fetch_all_institution(self):
        # This method must be implemented by plaid and yodlee services
        return True

    @api.one
    def _compute_next_synchronization(self):
        self.next_synchronization = self.env['ir.cron'].search([('name', '=', 'online.sync.gettransaction.cron')], limit=1).nextcall

    @api.multi
    def get_journal_dashboard_datas(self):
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        if self.online_account_id:
            res['show_import'] = False
        return res

    @api.model
    def launch_online_sync(self):
        for journal in self.search([('online_account_id', '!=', False)]):
            journal.online_account_id.online_sync()

    @api.multi
    def online_sync(self):
        return self.online_account_id.online_sync()

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.model
    def online_sync_bank_statement(self, transactions, journal):
        """
         build a bank statement from a list of transaction and post messages is also post in the online_account of the journal.
         :param transactions: A list of transactions that will be created in the new bank statement.
             The format is : [{
                 'id': online id,                  (unique ID for the transaction)
                 'date': transaction date,         (The date of the transaction)
                 'description': transaction description,  (The description)
                 'amount': transaction amount,     (The amount of the transaction. Negative for debit, positive for credit)
                 'end_amount': total amount on the account
                 'location': optional field used to find the partner (see _find_partner for more info)
             }, ...]
         :param journal: The journal (account.journal) of the new bank statement

         Return: True if there is no new bank statement or an action to the new bank statement if it exists.
        """
        # Since the synchronization succeeded, set it as the bank_statements_source of the journal
        journal.bank_statements_source = 'online_sync'

        all_lines = self.env['account.bank.statement.line'].search([('journal_id', '=', journal.id),
                                                                    ('date', '>=', journal.online_account_id.last_sync)])
        total = 0
        lines = []
        last_date = journal.online_account_id.last_sync
        end_amount = 0
        for transaction in transactions:
            if all_lines.search_count([('online_id', '=', transaction['id'])]) > 0:
                continue
            line = {
                'date': transaction['date'],
                'name': transaction['description'],
                'amount': transaction['amount'],
                'online_id': transaction['id'],
            }
            total += transaction['amount']
            end_amount = transaction['end_amount']
            # Partner from address
            if 'location' in transaction:
                line['partner_id'] = self._find_partner(transaction['location'])
            # Get the last date
            if not last_date or transaction['date'] > last_date:
                last_date = transaction['date']
            lines.append((0, 0, line))

        # For first synchronization, an opening bank statement line is created to fill the missing bank statements
        all_statement = self.search_count([('journal_id', '=', journal.id)])
        if all_statement == 0 and end_amount - total != 0:
            lines.append((0, 0, {
                'date': datetime.datetime.now(),
                'name': _("Opening statement : first synchronization"),
                'amount': end_amount - total,
            }))
            total = end_amount

        # If there is no new transaction, the bank statement is not created
        if lines:
            self.create({'journal_id': journal.id, 'line_ids': lines, 'balance_end_real': end_amount, 'balance_start': end_amount - total})
        journal.online_account_id.last_sync = last_date
        return journal.action_open_reconcile()

    @api.model
    def _find_partner(self, location):
        """
        Return a recordset of partner if the address of the transaction exactly match the address of a partner
        location : a dictionary of type:
                   {'state': x, 'address': y, 'city': z, 'zip': w}
                   state and zip are optional

        """
        partners = self.env['res.partner']
        domain = []
        if 'address' in location and 'city' in location:
            domain.append(('street', '=', location['address']))
            domain.append(('city', '=', location['city']))
            if 'state' in location:
                domain.append(('state_id.name', '=', location['state']))
            if 'zip' in location:
                domain.append(('zip', '=', location['zip']))
            return partners.search(domain, limit=1)
        return partners

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    online_id = fields.Char("Online Identifier")
