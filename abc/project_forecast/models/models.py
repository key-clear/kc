# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class ProjectForecast(models.Model):
    _name = 'project.forecast'

    def default_user_id(self):
        return self.env.user if ("default_user_id" not in self.env.context) else self.env.context["default_user_id"]

    def default_end_date(self):
        today = fields.Date.from_string(fields.Datetime.now())
        duration = timedelta(days=1)
        return today + duration

    name = fields.Char(compute='_compute_name')

    user_id = fields.Many2one('res.users', string="User", required=True,
                              default=default_user_id)
    project_id = fields.Many2one('project.project', string="Project")
    task_id = fields.Many2one('project.task', string="Task", domain="[('project_id', '=', project_id)]")

    time = fields.Integer(string="%", default=100.0, help="Percentage of working time")

    start_date = fields.Datetime(default=fields.Date.today, required="True")
    end_date = fields.Datetime(default=default_end_date, required="True")

    # consolidation color and exclude
    color = fields.Integer(string="Color", compute='_compute_color')
    exclude = fields.Boolean(string="Exclude", compute='_compute_exclude', store=True)

    # resource
    resource_hours = fields.Float(string="Planned hours", compute='_compute_resource_hours', store=True)
    effective_hours = fields.Float(string="Effective hours", compute='_compute_effective_hours', store=True)
    percentage_hours = fields.Float(string="Progress", compute='_compute_percentage_hours', store=True)

    @api.one
    @api.depends('project_id', 'task_id', 'user_id')
    def _compute_name(self):
        group = self.env.context["group_by"] if "group_by" in self.env.context else ""

        name = []
        if (group != "user_id"):
            name.append(self.user_id.name)
        if (group != "project_id" and self.project_id):
            name.append(self.project_id.name)
        if (group != "task_id" and self.task_id):
            name.append(self.task_id.name)
        self.name = " - ".join(name)
        if (self.name == ""):
            self.name = _("undefined")

    @api.one
    @api.depends('project_id.color')
    def _compute_color(self):
        if (self.project_id):
            self.color = self.project_id.color
        else:
            self.color = 0

    @api.one
    @api.depends('project_id.name')
    def _compute_exclude(self):
        self.exclude = (self.project_id and self.project_id.name == "Leaves")

    @api.one
    @api.depends('time', 'start_date', 'end_date')
    def _compute_resource_hours(self):
        start = datetime.strptime(self.start_date, "%Y-%m-%d %H:%M:%S")
        stop = datetime.strptime(self.end_date, "%Y-%m-%d %H:%M:%S")
        resource = self.env['resource.resource'].search([('user_id', '=', self.user_id.id)], limit=1)
        if (resource):
            calendar = resource.calendar_id
            if (calendar):
                hours = calendar.get_working_hours(start, stop)
                self.resource_hours = hours[0] * (self.time / 100.0)
                return
        self.resource_hours = 0

    @api.one
    @api.depends('task_id', 'user_id', 'start_date', 'end_date', 'project_id.analytic_account_id')
    def _compute_effective_hours(self):
        if not self.task_id and not self.project_id:
            self.effective_hours = 0
        else:
            if self.task_id and self.env['project.config.settings'].search([]).module_project_timesheet:
                timesheets = self.env['account.analytic.line'].search([('task_id', '=', self.task_id.id), ('user_id', '=', self.user_id.id), ('date', '>=', self.start_date), ('date', '<=', self.end_date)])
            elif self.project_id:
                timesheets = self.env['account.analytic.line'].search([('account_id', '=', self.project_id.analytic_account_id.id), ('user_id', '=', self.user_id.id), ('date', '>=', self.start_date), ('date', '<=', self.end_date)])
            else:
                timesheets = self.env['account.analytic.line'].browse()
            acc = 0
            for timesheet in timesheets:
                acc += timesheet.unit_amount
            self.effective_hours = acc

    @api.one
    @api.depends('resource_hours', 'effective_hours')
    def _compute_percentage_hours(self):
        if (self.resource_hours != 0):
            self.percentage_hours = self.effective_hours / self.resource_hours
        else:
            self.percentage_hours = 0

    @api.one
    @api.constrains('time')
    def _check_time_positive(self):
        if self.time and (self.time < 0):
            raise ValidationError(_("The time must be positive"))

    @api.one
    @api.constrains('task_id', 'project_id')
    def _task_id_in_project(self):
        if self.project_id and self.task_id and (self.task_id not in self.project_id.tasks):
            raise ValidationError(_("Your task is not in the selected project."))

    @api.one
    @api.constrains('start_date', 'end_date')
    def _start_date_lower_end_date(self):
        if self.start_date > self.end_date:
            raise ValidationError(_("The start-date must be lower than end-date."))

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if (self.task_id):
            self.project_id = self.task_id.project_id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        domain = [] if not self.project_id else [('project_id', '=', self.project_id.id)]
        return {
            'domain': {'task_id': domain},
        }

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if (self.end_date < self.start_date):
            start = fields.Date.from_string(self.start_date)
            duration = timedelta(days=1)
            self.end_date = start + duration

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if (self.start_date > self.end_date):
            end = fields.Date.from_string(self.end_date)
            duration = timedelta(days=1)
            self.start_date = end - duration

    @api.model
    def all_users(self, present_ids, domain, **kwargs):
        users = self.env['res.users'].search([])
        name = users.name_get()
        return name, None

    _group_by_full = {
        'user_id': all_users,
    }


class Project(models.Model):
    _inherit = 'project.project'

    allow_forecast = fields.Boolean("Allow forecast", default=False, help="This feature shows the Forecast link in the kanban view")

    @api.multi
    def create_forecast(self):
        view_id = self.env['ir.model.data'].get_object_reference('project_forecast', 'project_forecast_view_form')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.forecast',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_user_id': self.user_id.id,
            }
        }


class Task(models.Model):
    _inherit = 'project.task'

    @api.multi
    def create_forecast(self):
        view_id = self.env['ir.model.data'].get_object_reference('project_forecast', 'project_forecast_view_form')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.forecast',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'default_user_id': self.user_id.id,
            }
        }

