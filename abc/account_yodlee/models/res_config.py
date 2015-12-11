# -*- coding: utf-8 -*-
import requests
import json
from openerp import api, fields, models
from openerp.exceptions import UserError
from openerp.tools.translate import _

# TODO: To remove in v10
class YodleeConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    yodlee_service_url = fields.Char("Yodlee Service URL", default=lambda self: self.env['ir.config_parameter'].get_param('yodlee_service_url') or 'https://rest.developer.yodlee.com/services/srest/restserver/v1.0')
    yodlee_id = fields.Char("Yodlee ID", default=lambda self: self.env['ir.config_parameter'].get_param('yodlee_id'))
    yodlee_secret = fields.Char("yodlee Secret", default=lambda self: self.env['ir.config_parameter'].get_param('yodlee_secret'))
    yodlee_user_login = fields.Char('Yodlee User Login', related='company_id.yodlee_user_login')
    yodlee_user_password = fields.Char('Yodlee User Password', related='company_id.yodlee_user_password')
    yodlee_new_user_login = fields.Char('Yodlee User Login')
    yodlee_new_user_password = fields.Char('Yodlee User Password')
    yodlee_new_user_email = fields.Char('Yodlee User Email')

    def sanetize_yodlee_url(self, url):
        if url and url[len(url)-1:] == '/':
            return url[:len(url)-1]
        else:
            return url

    @api.multi
    def set_yodlee_info(self):
        self.env['ir.config_parameter'].set_param('yodlee_service_url', self.sanetize_yodlee_url(self.yodlee_service_url or ''), groups=["base.group_erp_manager"])
        self.env['ir.config_parameter'].set_param('yodlee_id', self.yodlee_id or '', groups=["base.group_erp_manager"])
        self.env['ir.config_parameter'].set_param('yodlee_secret', self.yodlee_secret or '', groups=["base.group_erp_manager"])

    @api.multi
    def create_new_yodlee_user(self):
        # This method create a new user for yodlee
        if not self.yodlee_service_url or not self.yodlee_id or not self.yodlee_secret or not self.yodlee_new_user_email or not self.yodlee_new_user_login or not self.yodlee_new_user_password:
            raise UserError(_('Please fill all fields related to yodlee first!'))

        login = {
            'cobrandLogin': self.yodlee_id,
            'cobrandPassword': self.yodlee_secret,
        }
        url = self.sanetize_yodlee_url(self.yodlee_service_url)
        try:
            resp = requests.post(url + '/authenticate/coblogin', params=login, timeout=3)
        except Exception:
            raise UserError(_('An error has occurred while trying to connect to yodlee service'))
        resp_json = json.loads(resp.text)
        if 'cobrandConversationCredentials' not in resp_json:
            raise UserError(_('Incorrect Yodlee login/password, please check your credentials'))

        params = {
            'cobSessionToken': resp_json['cobrandConversationCredentials']['sessionToken'],
            'userCredentials.loginName': self.yodlee_new_user_login,
            'userCredentials.password': self.yodlee_new_user_password,
            'userCredentials.objectInstanceType': 'com.yodlee.ext.login.PasswordCredentials',
            'userProfile.emailAddress': self.yodlee_new_user_email
        }
        try:
            resp = requests.post(url + '/jsonsdk/UserRegistration/register3', params=params, timeout=3)
        except Exception:
            raise UserError(_('An error has occurred while trying to connect to yodlee service'))
        resp_json = json.loads(resp.text)
        if resp_json.get('errorOccurred', False) == 'true':
            raise UserError(('An error occured: '+resp_json.get('exceptionType', 'Unknown Error') + '\nMessage: ' +resp_json.get('message', '')))
        else:
            self.yodlee_user_login = self.yodlee_new_user_login
            self.yodlee_user_password = self.yodlee_new_user_password