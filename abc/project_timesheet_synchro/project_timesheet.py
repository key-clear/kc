# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import models, api, exceptions

import time
import datetime
from dateutil.relativedelta import relativedelta
from openerp import tools
from openerp.tools.translate import _


class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"

    @api.model
    def export_data_for_ui(self):
        """
        Exports analytic lines (timesheet entries), tasks and projects for the UI during sync.
        """
        # AALS
        aal_ids = self.search([
            ("user_id", "=", self.env.uid),
            ("is_timesheet", "=", True),
            ("date", ">", (datetime.datetime.today() - datetime.timedelta(days=21)).strftime('%Y-%m-%d'))
            # The 21 days limit for data retrieval is arbitrary.
        ])

        aals_fields = [
            "id",
            "task_id/id",  # external id, to send to the UI
            "task_id.id",  # internal id, for data manipulation here
            "name",
            "account_id.id",
            "date",
            "unit_amount",
            "__last_update",
            "sheet_id/state",
        ]

        aals = aal_ids.export_data(aals_fields)

        # List comprehension to find the task and account ids used in aals.
        task_ids_list = list(set([int(aals['datas'][x][2]) for x in range(len(aals['datas'])) if len(aals['datas'][x][2]) > 0]))
        account_ids_list = list(set([int(aals['datas'][x][4]) for x in range(len(aals['datas'])) if len(aals['datas'][x][4]) > 0]))

        # Tasks
        task_ids = self.env["project.task"].search([
            '&',
                '|',
                    '|',
                        '|',
                        ("user_id", "=", self.env.uid),
                        ("user_id", "=", False),
                    ("message_partner_ids", "=", self.env.user.partner_id.id),
                ("id", "in", task_ids_list),
            ('active', '=', True),
        ])
        tasks_fields = [
            "id",
            "project_id/id",
            "project_id.id",
            "name",
            "user_id",
        ]
        tasks = task_ids.export_data(tasks_fields)

        project_ids_list = list(set([int(tasks['datas'][x][2]) for x in range(len(tasks['datas'])) if len(tasks['datas'][x][2]) > 0]))

        # Projects
        projects_ids = self.env["project.project"].search([
            '&',
                '|',
                    '|',
                    ("id", "in", project_ids_list),
                    ("user_id", '=', self.env.uid),  # User is the manager of the project
                ("analytic_account_id", "in", account_ids_list),
            ('active', '=', True),
        ])

        projects_fields = [
            "id",
            "name",
            "analytic_account_id.id",
        ]
        projects = projects_ids.export_data(projects_fields)

        # Sets the appropriate project to aal, using the account_id
        # Reduces the sheet_id/state to open or closed.
        # If an aal is not linked to a project, it won't be imported
        aals_to_return = {'datas': []}
        index = 0
        for aal in aals['datas']:
            for project in projects['datas']:
                if aal[4] == project[2]:
                    aal.append(project[0])
            if aal[8] == 'Approved' or aal[8] == 'Waiting Approval':
                aal[8] = 'closed'
            else:
                aal[8] = 'open'
            if len(aal) > (9):
                aals_to_return['datas'].append(aal)
        return {
            'aals': aals_to_return,
            'tasks': tasks,
            'projects': projects,
        }

    @api.model
    def import_ui_data(self, ls_aals, ls_tasks, ls_projects, context=None):
        """
        Imports the projects, tasks and analytic lines (timesheet entries) sent by the UI during sync.
        Returns a dict with lists of errors and lists of records to remove from the UI.
        The records to remove from the UI are those that no longer exist on the server and that have not been modified in the UI since the previous sync, and analytic lines where the user_id has been changed in the backend.
        In this method, ls_ refers to the items sent by the ui, from its localStorage.
        """
        ls_projects_to_import = []
        ls_projects_to_remove = []
        for ls_project in ls_projects:
            sv_project = self.env["ir.model.data"].xmlid_to_object(str(ls_project['id']))
            if not sv_project:
                if ls_project.get('to_sync'):
                    ls_projects_to_import.append([
                        str(ls_project['id']),
                        ls_project['name'],
                    ])
                else:
                    ls_projects_to_remove.append(str(ls_project['id']))
            elif not sv_project.active:
                ls_projects_to_remove.append(str(ls_project['id']))

        projects_fields = [
            'id',
            'name',
        ]
        project_errors = self.load_wrapper(self.env["project.project"], projects_fields, ls_projects_to_import)

        # Tasks management
        ls_tasks_to_import = []
        ls_tasks_to_remove = []
        for ls_task in ls_tasks:
            sv_task = self.env["ir.model.data"].xmlid_to_object(str(ls_task['id']))
            if not sv_task:
                if ls_task.get('to_sync'):
                    ls_tasks_to_import.append([
                        str(ls_task['id']),
                        ls_task['name'],
                        str(ls_task['project_id']),
                        str(self.env.uid),
                    ])
                else:
                    ls_tasks_to_remove.append(str(ls_task['id']))
            elif not sv_task.active:
                ls_tasks_to_remove.append(str(ls_task['id']))

        tasks_fields = [
            'id',
            'name',
            'project_id/id',
            'user_id/.id',
        ]
        task_errors = self.load_wrapper(self.env["project.task"], tasks_fields, ls_tasks_to_import)

        # Account analytic lines management
        new_ls_aals = []
        ls_aals_to_remove = []
        aals_on_hold = []
        for ls_aal in ls_aals:
            sv_aal = self.env["ir.model.data"].xmlid_to_object(str(ls_aal['id']))
            sv_project = self.env["ir.model.data"].xmlid_to_object(str(ls_aal.get('project_id')))

            if sv_aal and sv_aal.user_id.id != self.env.uid:  # The user on the activity has been changed
                ls_aals_to_remove.append(str(ls_aal['id']))
            elif sv_aal and ls_aal.get('to_remove'):  # The UI is requesting the deletion of the activity
                try:
                    self.unlink(sv_aal.id)
                    ls_aals_to_remove.append(str(ls_aal['id']))
                except:
                    aals_on_hold.append(str(ls_aal['id']))
                    pass
            elif ls_aal.get('to_sync') and sv_project:
                if sv_aal:
                    if(datetime.datetime.strptime(ls_aal['write_date'], tools.DEFAULT_SERVER_DATETIME_FORMAT) > datetime.datetime.strptime(sv_aal['__last_update'], tools.DEFAULT_SERVER_DATETIME_FORMAT)):
                        new_ls_aals.append(ls_aal)
                else:
                    new_ls_aals.append(ls_aal)
            elif ls_aal.get('to_sync') and not sv_project:
                aals_on_hold.append(str(ls_aal['id']))
            elif not sv_aal:
                ls_aals_to_remove.append(str(ls_aal['id']))

        for new_ls_aal in new_ls_aals:
            sv_project = self.env["ir.model.data"].xmlid_to_object(str(new_ls_aal['project_id']))
            new_ls_aal['account_id'] = str(sv_project['analytic_account_id']['id'])
            if not new_ls_aal.get('task_id'):
                new_ls_aal['task_id'] = ""

        ls_aals_to_import = []
        for new_ls_aal in new_ls_aals:
            if new_ls_aal.get('to_sync'):
                ls_aals_to_import.append([
                    str(new_ls_aal['id']),
                    new_ls_aal['desc'],
                    new_ls_aal['account_id'],
                    new_ls_aal['date'],
                    new_ls_aal['unit_amount'],
                    str(new_ls_aal.get('task_id')),
                    self.env.uid,
                    'True',
                ])

        aals_fields = [
            'id',
            'name',
            'account_id/.id',
            'date',
            'unit_amount',
            'task_id/id',
            'user_id/.id',
            'is_timesheet',
        ]

        aals_errors = self.load_wrapper(self, aals_fields, ls_aals_to_import)
        aals_errors['failed_records'] += aals_on_hold

        return {'project_errors': project_errors,
            'task_errors': task_errors,
            'aals_errors': aals_errors,
            'projects_to_remove': ls_projects_to_remove,
            'tasks_to_remove': ls_tasks_to_remove,
            'aals_to_remove': ls_aals_to_remove,
        }

    def load_wrapper(self, model, fields, data_rows):
        """
        Wrapper for the load method. It ensures that all valid records are loaded, while records that can't be loaded for any reason are left out.
        Returns the failed records ids and error messages.
        """
        messages = model.load(fields, data_rows, context=self.env.context)['messages']

        failed_records_indices = [messages[x].get('record') for x in range(len(messages)) if messages[x].get('type') == 'error']

        failed_records = []
        failed_records_messages = []

        if failed_records_indices:
            correct_data_rows = [v for i, v in enumerate(data_rows) if i not in failed_records_indices]
            second_load_message = model.load(fields, correct_data_rows, context=self.env.context)

            failed_records_messages = [messages[x].get('message') for x in range(len(messages)) if messages[x].get('type') == 'error']
            failed_records = [v[0] for i, v in enumerate(data_rows) if i in failed_records_indices]
        return {
            "failed_records": failed_records,
            "failed_records_messages": failed_records_messages,
        }
