# -*- coding: utf-8 -*-

from openerp import models, fields, api, tools
from openerp.tools.translate import _
from openerp.exceptions import UserError
import time
from datetime import datetime
from datetime import timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

# ----------------------------------------------------------
# Models
# ----------------------------------------------------------


class crm_phonecall(models.Model):
    _name = "crm.phonecall"

    _order = "sequence, id"

    name = fields.Char('Call Summary', required=True)
    date = fields.Datetime('Date')
    user_id = fields.Many2one('res.users', 'Responsible')
    partner_id = fields.Many2one('res.partner', 'Contact')
    company_id = fields.Many2one('res.company', 'Company')
    description = fields.Text('Description')
    duration = fields.Float('Duration', help="Duration in minutes and seconds.")
    partner_phone = fields.Char('Phone')
    partner_mobile = fields.Char('Mobile')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High')
        ], string='priority')
    team_id = fields.Many2one('crm.team', 'Sales Team', select=True,
        help="Sales team to which Case belongs to.")
    categ_id = fields.Many2one('crm.phonecall.category', 'Category')
    in_queue = fields.Boolean('In Call Queue', default=True)
    sequence = fields.Integer('Sequence', select=True,
        help="Gives the sequence order when displaying a list of Phonecalls.")
    start_time = fields.Integer("Start time")
    state = fields.Selection([
        ('pending', 'Not Held'),
        ('cancel', 'Cancelled'),
        ('open', 'To Do'),
        ('done', 'Held'),
        ], string='Status', readonly=True, track_visibility='onchange',
        help='The status is set to To Do, when a case is created.\n'
             'When the call is over, the status is set to Held.\n'
             'If the call is not applicable anymore, the status can be set to Cancelled.')
    opportunity_id = fields.Many2one('crm.lead', 'Lead/Opportunity', ondelete='cascade', track_visibility='onchange')

    _defaults = {
        'date': fields.Datetime.now(),
        'priority': '1',
        'state':  'open',
        'user_id': lambda self, cr, uid, ctx: uid,
        'team_id': lambda self, cr, uid, ctx: self.pool['crm.team']._get_default_team_id(cr, uid, context=ctx),
        'active': 1
    }

    @api.onchange('partner_id')
    def on_change_partner_id(self):
        self.ensure_one()
        if self.partner_id:
            partner = self.env['res.partner'].browse(self.partner_id.id)
            self.partner_phone = partner.phone
            self.partner_mobile = partner.mobile

    def write(self, cr, uid, ids, values, context=None):
        return super(crm_phonecall, self).write(cr, uid, ids, values, context=context)

    def schedule_another_phonecall(self, cr, uid, ids, schedule_time, call_summary,
                                   user_id=False, team_id=False, categ_id=False, context=None):
        model_data = self.pool.get('ir.model.data')
        phonecall_dict = {}
        if not categ_id:
            try:
                res_id = model_data._get_id(cr, uid, 'crm', 'categ_phone2')
                categ_id = model_data.browse(cr, uid, res_id, context=context).res_id
            except ValueError:
                pass
        for call in self.browse(cr, uid, ids, context=context):
            if(call.state != "done"):
                call.state = "cancel"
                call.in_queue = False
            if not team_id:
                team_id = call.team_id and call.team_id.id or False
            if not user_id:
                user_id = call.user_id and call.user_id.id or False
            if not schedule_time:
                schedule_time = call.date
            vals = {
                'name': call_summary,
                'user_id': user_id or False,
                'categ_id': categ_id or False,
                'description': False,
                'date': schedule_time,
                'team_id': team_id or False,
                'partner_id': call.partner_id and call.partner_id.id or False,
                'partner_phone': call.partner_phone,
                'partner_mobile': call.partner_mobile,
                'priority': call.priority,
                'opportunity_id': call.opportunity_id and call.opportunity_id.id or False,
            }
            new_id = self.create(cr, uid, vals, context=context)
            phonecall_dict[call.id] = new_id
        return phonecall_dict

    def on_change_opportunity(self, cr, uid, ids, opportunity_id, context=None):
            values = {}
            if opportunity_id:
                opportunity = self.pool.get('crm.lead').browse(cr, uid, opportunity_id, context=context)
                values = {
                    'team_id': opportunity.team_id and opportunity.team_id.id or False,
                    'partner_phone': opportunity.phone,
                    'partner_mobile': opportunity.mobile,
                    'partner_id': opportunity.partner_id and opportunity.partner_id.id or False,
                }
            return {'value': values}

    def redirect_phonecall_view(self, cr, uid, phonecall_id, context=None):
        model_data = self.pool.get('ir.model.data')
        # Select the view
        tree_view = model_data.get_object_reference(cr, uid, 'crm', 'crm_case_phone_tree_view')
        form_view = model_data.get_object_reference(cr, uid, 'crm', 'crm_case_phone_form_view')
        search_view = model_data.get_object_reference(cr, uid, 'crm', 'view_crm_case_phonecalls_filter')
        value = {
                'name': _('Phone Call'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'crm.phonecall',
                'res_id' : int(phonecall_id),
                'views': [(form_view and form_view[1] or False, 'form'), (tree_view and tree_view[1] or False, 'tree'), (False, 'calendar')],
                'type': 'ir.actions.act_window',
                'search_view_id': search_view and search_view[1] or False,
        }
        return value

    def action_button_to_opportunity(self, cr, uid, ids, context=None):
        if len(ids) != 1:
            raise UserError(_('It\'s only possible to convert one phone call at a time.'))

        opportunity_dict = {}
        opportunity = self.pool.get('crm.lead')
        for call in self.browse(cr, uid, ids, context=context):
            opportunity_id = opportunity.browse(cr, uid, call.opportunity_id.id)
            if not opportunity_id:
                opportunity_id = opportunity.create(cr, uid, {
                    'name': call.name,
                    'partner_id': call.partner_id.id,
                    'mobile': call.partner_mobile or call.partner_id.mobile,
                    'team_id': call.team_id and call.team_id.id or False,
                    'description': call.description or False,
                    'priority': call.priority,
                    'type': 'opportunity',
                    'phone': call.partner_phone or call.partner_id.phone,
                    'email_from': call.partner_id.email,
                })
            call.opportunity_id = opportunity_id
            opportunity_dict[call.id] = opportunity_id
        return self.pool.get('crm.lead').redirect_opportunity_view(cr, uid, opportunity_dict[ids[0]], context)

    @api.multi
    def init_call(self):
        self.start_time = int(time.time())

    @api.multi
    def hangup_call(self):
        stop_time = int(time.time())
        duration = float(stop_time - self.start_time)
        self.duration = float(duration/60.0)
        self.state = "done"
        return {"duration": self.duration}

    @api.multi
    def rejected_call(self):
        self.state = "pending"

    @api.multi
    def remove_from_queue(self):
        self.in_queue = False
        if(self.state == "open"):
            self.state = "cancel"
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
        }

    @api.one
    def get_info(self):
        return {"id": self.id,
                "description": self.description,
                "name": self.name,
                "state": self.state,
                "date": self.date,
                "duration": self.duration,
                "partner_id": self.partner_id.id,
                "partner_name": self.partner_id.name,
                "partner_image_small": self.partner_id.image_small,
                "partner_email": self.partner_id.email,
                "partner_title": self.partner_id.title.name,
                "partner_phone": self.partner_phone or self.partner_mobile or self.opportunity_id.phone or self.opportunity_id.partner_id.phone or self.opportunity_id.partner_id.mobile or False,
                "opportunity_name": self.opportunity_id.name,
                "opportunity_id": self.opportunity_id.id,
                "opportunity_priority": self.opportunity_id.priority,
                "opportunity_planned_revenue": self.opportunity_id.planned_revenue,
                "opportunity_title_action": self.opportunity_id.title_action,
                "opportunity_date_action": self.opportunity_id.date_action,
                "opportunity_company_currency": self.opportunity_id.company_currency.id,
                "opportunity_probability": self.opportunity_id.probability,
                "max_priority": self.opportunity_id._fields['priority'].selection[-1][0]}

    @api.model
    def get_list(self):
        date_today = datetime.now()
        return {"phonecalls": self.search([
            ('in_queue', '=', True),
            ('user_id', '=', self.env.user[0].id),
            ('date', '<=', date_today.strftime(DEFAULT_SERVER_DATE_FORMAT))],
            order='sequence,id')
            .get_info()}


class crm_lead(models.Model):
    _inherit = "crm.lead"
    in_call_center_queue = fields.Boolean("Is in the Call Queue", compute='compute_is_call_center')

    @api.one
    def compute_is_call_center(self):
        phonecall = self.env['crm.phonecall'].search([('opportunity_id','=',self.id),('in_queue','=',True),('state','!=','done'),('user_id','=',self.env.user[0].id)])
        if phonecall:
            self.in_call_center_queue = True
        else:
            self.in_call_center_queue = False

    @api.multi
    def create_call_in_queue(self):
        for opp in self:
            phonecall = self.env['crm.phonecall'].create({
                'name': opp.name,
                'duration': 0,
                'user_id': self.env.user[0].id,
                'opportunity_id': opp.id,
                'partner_id': opp.partner_id.id,
                'state': 'open',
                'partner_phone': opp.phone or opp.partner_id.phone,
                'partner_mobile': opp.partner_id.mobile,
                'in_queue': True,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
        }

    @api.multi
    def create_custom_call_center_call(self):
        phonecall = self.env['crm.phonecall'].create({
            'name': self.name,
            'duration': 0,
            'user_id': self.env.user[0].id,
            'opportunity_id': self.id,
            'partner_id': self.partner_id.id,
            'state': 'open',
            'partner_phone': self.phone or self.partner_id.phone,
            'in_queue': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'key2': 'client_action_multi',
            'src_model': "crm.phonecall",
            'res_model': "crm.custom.phonecall.wizard",
            'multi': "True",
            'target': 'new',
            'context': {'phonecall_id': phonecall.id,
                        'default_name': phonecall.name,
                        'default_partner_id': phonecall.partner_id.id,
                        'default_user_id': self.env.user[0].id,
                        },
            'views': [[False, 'form']],
        }

    @api.multi
    def delete_call_center_call(self):
        phonecall = self.env['crm.phonecall'].search([('opportunity_id','=',self.id),('in_queue','=',True),('user_id','=',self.env.user[0].id)])
        phonecall.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
        }

    @api.multi
    def log_new_phonecall(self):
        phonecall = self.env['crm.phonecall'].create({
            'name': self.name,
            'user_id': self.env.user[0].id,
            'opportunity_id': self.id,
            'partner_id': self.partner_id.id,
            'state': 'done',
            'partner_phone': self.phone or self.partner_id.phone,
            'partner_mobile': self.partner_id.mobile,
            'in_queue': False,
        })
        return {
            'name': 'Log a call',
            'type': 'ir.actions.act_window',
            'key2': 'client_action_multi',
            'src_model': "crm.phonecall",
            'res_model': "crm.phonecall.log.wizard",
            'multi': "True",
            'target': 'new',
            'context': {'phonecall_id': phonecall.id,
                        'default_opportunity_id': phonecall.opportunity_id.id,
                        'default_name': phonecall.name,
                        'default_duration': phonecall.duration,
                        'default_description': phonecall.description,
                        'default_opportunity_name': phonecall.opportunity_id.name,
                        'default_opportunity_planned_revenue': phonecall.opportunity_id.planned_revenue,
                        'default_opportunity_title_action': phonecall.opportunity_id.title_action,
                        'default_opportunity_date_action': phonecall.opportunity_id.date_action,
                        'default_opportunity_probability': phonecall.opportunity_id.probability,
                        'default_partner_id': phonecall.partner_id.id,
                        'default_partner_name': phonecall.partner_id.name,
                        'default_partner_email': phonecall.partner_id.email,
                        'default_partner_phone': phonecall.opportunity_id.phone or phonecall.partner_id.phone,
                        'default_partner_image_small': phonecall.partner_id.image_small,},
                        'default_show_duration': self._context.get('default_show_duration'),
            'views': [[False, 'form']],
            'flags': {
                'headless': True,
            },
        }


class res_partner(models.Model):
    _inherit = "res.partner"

    @api.one
    def create_call_in_queue(self, number):
        phonecall = self.env['crm.phonecall'].create({
            'name': 'Call for ' + self.name,
            'duration': 0,
            'user_id': self.env.user[0].id,
            'partner_id': self.id,
            'state': 'open',
            'partner_phone': number,
            'in_queue': True,
        })
        return phonecall.id


class crm_phonecall_log_wizard(models.TransientModel):
    _name = 'crm.phonecall.log.wizard'

    description = fields.Text('Description')
    name = fields.Char(readonly=True)
    opportunity_id = fields.Integer(readonly=True)
    opportunity_name = fields.Char(readonly=True)
    opportunity_planned_revenue = fields.Char(readonly=True)
    opportunity_title_action = fields.Char('Next Action')
    opportunity_date_action = fields.Date('Next Action Date')
    opportunity_probability = fields.Float(readonly=True)
    partner_id = fields.Integer(readonly=True)
    partner_name = fields.Char(readonly=True)
    partner_email = fields.Char(readonly=True)
    partner_phone = fields.Char(readonly=True)
    partner_image_small = fields.Char(readonly=True)
    duration = fields.Char('Duration', readonly=True)
    reschedule_option = fields.Selection([
        ('no_reschedule', "Don't Reschedule"),
        ('1d', 'Tomorrow'),
        ('7d', 'In 1 Week'),
        ('15d', 'In 15 Day'),
        ('2m', 'In 2 Months'),
        ('custom', 'Specific Date')
    ], 'Schedule A New Call', required=True, default="no_reschedule")
    reschedule_date = fields.Datetime('Specific Date',
        default=lambda *a: datetime.now() + timedelta(hours=2))
    next_activity_id = fields.Many2one("crm.activity", "Next Activity")
    new_title_action = fields.Char('Next Action')
    new_date_action = fields.Date()
    show_duration = fields.Boolean()
    custom_duration = fields.Float(default=0)
    in_automatic_mode = fields.Boolean()

    def schedule_again(self):
        new_phonecall = self.env['crm.phonecall'].create({
            'name': self.name,
            'duration': 0,
            'user_id': self.env.user[0].id,
            'opportunity_id': self.opportunity_id,
            'partner_id': self.partner_id,
            'state': 'open',
            'partner_phone': self.partner_phone,
            'in_queue': True,
        })
        if self.reschedule_option == "7d":
            new_phonecall.date = datetime.now() + timedelta(weeks=1)
        elif self.reschedule_option == "1d":
            new_phonecall.date = datetime.now() + timedelta(days=1)
        elif self.reschedule_option == "15d":
            new_phonecall.date = datetime.now() + timedelta(days=15)
        elif self.reschedule_option == "2m":
            new_phonecall.date = datetime.now() + timedelta(weeks=8)
        elif self.reschedule_option == "custom":
            new_phonecall.date = self.reschedule_date

    @api.multi
    def modify_phonecall(self, phonecall):
        phonecall.description = self.description
        if(self.opportunity_id):
            opportunity = self.env['crm.lead'].browse(self.opportunity_id)
            if self.next_activity_id:
                opportunity.next_activity_id = self.next_activity_id
                opportunity.title_action = self.new_title_action
                opportunity.date_action = self.new_date_action
            if (self.show_duration):
                mins = int(self.custom_duration)
                sec = (self.custom_duration - mins)*0.6
                sec = '%.2f' % sec
                time = str(mins) + ":" + sec[-2:]
                message = "Call " + time + " min(s)"
                phonecall.duration = self.custom_duration
            else:
                message = "Call " + self.duration + " min(s)"
            if(phonecall.description):
                message += " about " + phonecall.description
            opportunity.message_post(message)
        if self.reschedule_option != "no_reschedule":
            self.schedule_again()

    @api.multi
    def save(self):
        phonecall = self.env['crm.phonecall'].browse(self._context.get('phonecall_id'))
        self.modify_phonecall(phonecall)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
            'params': {'in_automatic_mode': self.in_automatic_mode},
        }

    @api.multi
    def save_go_opportunity(self):
        phonecall = self.env['crm.phonecall'].browse(self._context.get('phonecall_id'))
        self.modify_phonecall(phonecall)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
            'params': {'go_to_opp': True,
                       'opportunity_id': self.opportunity_id,
                       'in_automatic_mode': self.in_automatic_mode},
        }


class crm_custom_phonecall_wizard(models.TransientModel):
    _name = 'crm.custom.phonecall.wizard'

    name = fields.Char('Call summary', required=True)
    user_id = fields.Many2one('res.users', "Assign To")
    date = fields.Datetime('Date', required=True, default=lambda *a: datetime.now())
    partner_id = fields.Many2one('res.partner', "Partner")

    @api.multi
    def action_schedule(self):
        phonecall = self.env['crm.phonecall'].browse(self._context.get('phonecall_id'))
        phonecall.name = self.name
        phonecall.date = self.date
        phonecall.partner_id = self.partner_id
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
        }


class crm_phonecall_transfer_wizard(models.TransientModel):
    _name = 'crm.phonecall.transfer.wizard'

    transfer_number = fields.Char('transfer To')
    transfer_choice = fields.Selection(selection=[('physical', 'transfer to your external phone'), ('extern', 'transfer to another External Phone')], default='physical', required=True)

    @api.multi
    def save(self):
        if self.transfer_choice == 'extern':
            action = {
                'type': 'ir.actions.client',
                'tag': 'transfer_call',
                'params': {'number': self.transfer_number},
            }
        else:
            if self.env.user[0].sip_external_phone:
                action = {
                    'type': 'ir.actions.client',
                    'tag': 'transfer_call',
                    'params': {'number': self.env.user[0].sip_external_phone},
                }
            else:
                action = {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("Wrong configuration for the call. There is no external phone number configured"),
                    },
                }
        return action


class crm_phonecall_report(models.Model):
    _name = "crm.phonecall.report"
    _description = "Phone Calls by user and team"
    _auto = False

    user_id = fields.Many2one('res.users', 'Responsible', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Contact', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    duration = fields.Float('Duration', digits=(16, 2), group_operator="avg", readonly=True)
    team_id = fields.Many2one('crm.team', 'Sales Team', select=True,
        help="Sales team to which Case belongs to.")
    categ_id = fields.Many2one('crm.phonecall.category', 'Category')
    state = fields.Selection([
        ('pending', 'Not Held'),
        ('cancel', 'Cancelled'),
        ('open', 'To Do'),
        ('done', 'Held')
    ], 'Status', readonly=True)
    date = fields.Datetime('Date', readonly=True, select=True)
    nbr = fields.Integer('# of Cases', readonly=True)

    def init(self, cr):

        """ Phone Calls By User And Team
            @param cr: the current row, from the database cursor,
        """
        tools.drop_view_if_exists(cr, 'crm_phonecall_report')
        cr.execute("""
            create or replace view crm_phonecall_report as (
                select
                    id,
                    c.state,
                    c.user_id,
                    c.team_id,
                    c.categ_id,
                    c.partner_id,
                    c.duration,
                    c.company_id,
                    c.priority,
                    1 as nbr,
                    c.date
                from
                    crm_phonecall c
                where
                    c.state = 'done'
            )""")


class crm_phonecall2phonecall(models.TransientModel):
    _name = "crm.phonecall2phonecall"

    name = fields.Char('Call Summary', required=True)
    date = fields.Datetime('Date', required=True)
    name = fields.Char('Call summary', required=True, select=1)
    user_id = fields.Many2one('res.users', "Assign To")
    contact_name = fields.Char('Contact')
    phone = fields.Char('Phone')
    categ_id = fields.Many2one('crm.phonecall.category', 'Category')
    team_id = fields.Many2one('crm.team', 'Sales Team')
    partner_id = fields.Many2one('res.partner', "Partner")
    note = fields.Text('Note')

    def action_cancel(self, cr, uid, ids, context=None):
            """
            Closes Phonecall to Phonecall form
            """
            return {'type': 'ir.actions.act_window_close'}

    def action_schedule(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        phonecall = self.pool.get('crm.phonecall')
        phonecall_ids = context and context.get('active_ids') or []
        for this in self.browse(cr, uid, ids, context=context):
            phocall_ids = phonecall.schedule_another_phonecall(
                cr, uid, phonecall_ids, this.date, this.name,
                this.user_id and this.user_id.id or False,
                this.team_id and this.team_id.id or False,
                this.categ_id and this.categ_id.id or False,
                context=context)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload_panel',
        }

    def default_get(self, cr, uid, fields, context=None):
        """
        This function gets default values
        
        """
        res = super(crm_phonecall2phonecall, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        if record_id:
            phonecall = self.pool.get('crm.phonecall').browse(cr, uid, record_id, context=context)

            categ_id = False
            data_obj = self.pool.get('ir.model.data')
            try:
                res_id = data_obj._get_id(cr, uid, 'crm', 'categ_phone2')
                categ_id = data_obj.browse(cr, uid, res_id, context=context).res_id
            except ValueError:
                pass

            if 'name' in fields:
                res.update({'name': phonecall.name})
            if 'user_id' in fields:
                res.update({'user_id': phonecall.user_id and phonecall.user_id.id or False})
            if 'date' in fields:
                res.update({'date': False})
            if 'team_id' in fields:
                res.update({'team_id': phonecall.team_id and phonecall.team_id.id or False})
            if 'categ_id' in fields:
                res.update({'categ_id': categ_id})
            if 'partner_id' in fields:
                res.update({'partner_id': phonecall.partner_id and phonecall.partner_id.id or False})
        return res


class crm_phonecall_category(models.Model):
    _name = "crm.phonecall.category"
    _description = "Category of phone call"

    name = fields.Char('Name', required=True, translate=True)
    team_id = fields.Many2one('crm.team', 'Sales Team')
