# -*- coding: utf-8 -*-
from openerp.tests import common


class TestContractCommon(common.TransactionCase):

    def setUp(self):
        super(TestContractCommon, self).setUp()
        Contract = self.env['sale.subscription']
        Product = self.env['product.product']
        ProductTmpl = self.env['product.template']
        UomCat = self.env['product.uom.categ']
        Uom = self.env['product.uom']
        # Analytic Account
        self.master_tag = self.env['account.analytic.tag'].create({
            'name': 'Test Tag',
        })

        # Units of measure
        self.uom_cat = UomCat.create({
            'name': 'Test Cat',
        })
        self.uom_base = Uom.create({
            'name': 'Base uom',
            'category_id': self.uom_cat.id,
        })
        self.uom_big = Uom.create({
            'name': '10x uom',
            'category_id': self.uom_cat.id,
            'uom_type': 'bigger',
            'factor_inv': 10,
        })

        # Test products
        self.product_tmpl = ProductTmpl.create({
            'name': 'TestProduct',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.uom_base.id,
            'uom_po_id': self.uom_base.id,
            'price': 50.0
        })
        self.product = Product.create({
            'product_tmpl_id': self.product_tmpl.id,
        })

        self.product_opt_tmpl = ProductTmpl.create({
            'name': 'TestOptionProduct',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.uom_base.id,
            'uom_po_id': self.uom_base.id,
            'price': 20.0
        })
        self.product_opt = Product.create({
            'product_tmpl_id': self.product_opt_tmpl.id,
        })

        self.product_tmpl2 = ProductTmpl.create({
            'name': 'TestProduct2',
            'type': 'service',
            'recurring_invoice': True,
            'uom_id': self.uom_base.id,
            'uom_po_id': self.uom_base.id,
            'price': 15.0
        })
        self.product2 = Product.create({
            'product_tmpl_id': self.product_tmpl2.id,
        })

        # Test user
        TestUsersEnv = self.env['res.users'].with_context({'no_reset_password': True})
        group_portal_id = self.ref('base.group_portal')
        self.user_portal = TestUsersEnv.create({
            'name': 'Beatrice Portal',
            'login': 'Beatrice',
            'alias_name': 'beatrice',
            'email': 'beatrice.employee@example.com',
            'groups_id': [(6, 0, [group_portal_id])]
        })

        # Test Contract
        self.contract_tmpl_1 = Contract.create({
            'name': 'TestContractTemplate1',
            'type': 'template',
            'recurring_rule_type': 'yearly',
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': self.product.list_price, 'uom_id': self.uom_base.id})],
            'option_invoice_line_ids': [(0, 0, {'product_id': self.product_opt.id, 'name': 'TestRecurringLine', 'price_unit': self.product_opt.list_price, 'uom_id': self.uom_base.id})],
            'tag_ids': [(4, self.master_tag.id, False)],
        })
        self.contract_tmpl_2 = Contract.create({
            'name': 'TestContractTemplate2',
            'type': 'template',
            'recurring_rule_type': 'monthly',
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': self.product.list_price * 2, 'uom_id': self.uom_big.id}),
                                           (0, 0, {'product_id': self.product2.id, 'name': 'TestRecurringLine', 'price_unit': self.product2.list_price * 2, 'uom_id': self.uom_big.id})],
            'option_invoice_line_ids': [(0, 0, {'product_id': self.product_opt.id, 'name': 'TestRecurringLine', 'price_unit': self.product_opt.list_price * 2, 'uom_id': self.uom_big.id})],
            'tag_ids': [(4, self.master_tag.id, False)],
        })
        self.contract_tmpl_3 = Contract.create({
            'name': 'TestContractTemplate3',
            'type': 'template',
            'user_selectable': False,
            'tag_ids': [(4, self.master_tag.id, False)],
        })
        self.contract = Contract.create({
            'name': 'TestContract',
            'type': 'contract',
            'recurring_rule_type': 'yearly',
            'pricelist_id': self.env.ref('product.list0').id,
            'state': 'open',
            'partner_id': self.user_portal.partner_id.id,
            'template_id': self.contract_tmpl_1.id,
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': self.product.list_price, 'uom_id': self.uom_base.id})],
        })
