import openerp.tests
# @openerp.tests.common.at_install(False)
# @openerp.tests.common.post_install(True)
class TestUi(openerp.tests.HttpCase):
    def test_01_ui(self):
        self.phantom_js("/", "odoo.__DEBUG__.services['web.Tour'].run('activity_creation', 'test')", "odoo.__DEBUG__.services['web.Tour'].tours.activity_creation", login='admin')

    def test_02_ui(self):
        self.phantom_js("/", "odoo.__DEBUG__.services['web.Tour'].run('test_screen_navigation', 'test')", "odoo.__DEBUG__.services['web.Tour'].tours.test_screen_navigation", login='admin')
