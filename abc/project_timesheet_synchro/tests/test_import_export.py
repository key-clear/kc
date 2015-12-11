# -*- coding: utf-8 -*-


from openerp.exceptions import AccessError, ValidationError, UserError
from openerp.tests import common


class TestImportExport(common.TransactionCase):

    # Simple import / export test
    def test_import_export_general(self):
        test_analytic_lines = [
            {
                "id": "Project_timesheet_UI_admin1433780253119_aal.1",
                "date": "2015-06-08",
                "project_id": "Project_timesheet_UI_admin1433780253119_project.1",
                "task_id": "Project_timesheet_UI_admin1433780253119_task.1",
                "desc": "description",
                "unit_amount": "2.00",
                "write_date": "2015-06-08 16:17:59",
                "to_sync": True,
                "sync_problem": False,
                "sheet_state": "open",
            },
        ]
        test_tasks = [
            {
                "name": "task",
                "id": "Project_timesheet_UI_admin1433780253119_task.1",
                "project_id": "Project_timesheet_UI_admin1433780253119_project.1",
                "to_sync": True,
                "sync_problem": False,
            }
        ]
        test_projects = [{
            "name": "project",
            "id": "Project_timesheet_UI_admin1433780253119_project.1",
            "to_sync": True,
            "sync_problem": False,
        }]

        AAL = self.env['account.analytic.line']

        context = {'lang': "en_US", 'tz': "Europe/Brussels", 'uid': 1, 'default_is_timesheet': True}

        AAL.with_context(context).import_ui_data(test_analytic_lines, test_tasks, test_projects)

        AAL.with_context(context).export_data_for_ui()

        for line in test_analytic_lines:
            line_ext_id = line["id"]
            aal = self.env["ir.model.data"].xmlid_to_object(line_ext_id)
            self.assertEqual(line["desc"], aal.name)
            self.assertEqual(line["date"], aal.date)
            self.assertEqual(float(line["unit_amount"]), aal.unit_amount)

    # Creates a project and sets the related contract to allow invoicing based on timesheet
    # Then create import a analytic line on htis contract and make sure to_invoice is properly set.
    def test_import_line_on_invoiced_contract(self):
        test_analytic_lines = [
            {
                "id": "Project_timesheet_UI_admin1433780253119_aal.1",
                "date": "2015-06-08",
                "project_id": "Project_timesheet_UI_admin1433780253119_project.1",
                "desc": "description",
                "unit_amount": "2.00",
                "write_date": "2015-06-08 16:17:59",
                "to_sync": True,
                "sync_problem": False,
                "sheet_state": "open",
            },
            {
                "id": "Project_timesheet_UI_admin1433780253115_aal.2",
                "date": "2015-06-08",
                "project_id": "Project_timesheet_UI_admin1433780253119_project.2",
                "desc": "description",
                "unit_amount": "2.00",
                "write_date": "2015-06-08 16:17:59",
                "to_sync": True,
                "sync_problem": False,
                "sheet_state": "open",
            },
          ]
        test_projects = [
            {
                "name": "project",
                "id": "Project_timesheet_UI_admin1433780253119_project.1",
                "to_sync": True,
                "sync_problem": False
            },
            {
                "name": "project2",
                "id": "Project_timesheet_UI_admin1433780253119_project.2",
                "to_sync": True,
                "sync_problem": False,
            },
        ]

        context = {'lang': "en_US", 'tz': "Europe/Brussels", 'uid': 1, 'default_is_timesheet': True}
        AAL = self.env['account.analytic.line']
        AAL.with_context(context).import_ui_data([], [], test_projects)

        project = self.env["ir.model.data"].xmlid_to_object(test_projects[0]['id'])
        contract = project.analytic_account_id

        AAL.with_context(context).import_ui_data(test_analytic_lines, [], [])

        for line in test_analytic_lines:
            line_ext_id = line["id"]
            aal = self.env["ir.model.data"].xmlid_to_object(line_ext_id)
            self.assertEqual(line["desc"], aal.name)
            self.assertEqual(line["date"], aal.date)
            self.assertEqual(float(line["unit_amount"]), aal.unit_amount)

            project = self.env["ir.model.data"].xmlid_to_object(line['project_id'])
            contract = project.analytic_account_id

    # Creates a timesheet_sheet and sets it in a confirmed state.
    # Then exports data and makes sure that the analytic lines of the sheet are exported with sheet_state closed
    def test_closed_sheet_sync(self):

        test_projects = [
            {
                "name": "project",
                "id": "Project_timesheet_UI_admin1433780253119_project.1",
                "to_sync": True,
                "sync_problem": False,
            }
        ]

        context = {'lang': "en_US", 'tz': "Europe/Brussels", 'uid': 1, 'default_is_timesheet': True, }
        AAL = self.env['account.analytic.line']
        AAL.with_context(context).import_ui_data([], [], test_projects)

        project = self.env["ir.model.data"].xmlid_to_object(test_projects[0]['id'])
        contract = project.analytic_account_id

        AAL = self.env['account.analytic.line']
        aal = AAL.with_context(context).create({
            'account_id': contract.id,
            'is_timesheet': True,
            'user_id': 1,
            'name': 'activity description',
        })

        Time_Sheet_Sheet = self.env['hr_timesheet_sheet.sheet']
        sheet = Time_Sheet_Sheet.create({})

        # Open sheet case
        exported_data = AAL.with_context(context).export_data_for_ui()

        for exported_aal in exported_data['aals']['datas']:
            if self.env["ir.model.data"].xmlid_to_res_id(exported_aal[0]) == aal.id:
                self.assertEqual(exported_aal[8], 'open')

        # closed sheet case
        sheet.state = 'done'

        exported_data = AAL.with_context(context).export_data_for_ui()

        for exported_aal in exported_data['aals']['datas']:
            if self.env["ir.model.data"].xmlid_to_res_id(exported_aal[0]) == aal.id:
                self.assertEqual(exported_aal[8], 'closed')
