# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from datetime import datetime
from openerp.exceptions import UserError, RedirectWarning


class ebay_category(models.Model):
    _name = 'ebay.category'

    name = fields.Char('Name')
    full_name = fields.Char('Full Name', store=True, compute='_compute_full_name')
    # The IDS are string because of the limitation of the SQL integer range
    category_id = fields.Char('Category ID')
    category_parent_id = fields.Char('Category Parent ID')
    leaf_category = fields.Boolean(default=False)
    category_type = fields.Selection(
        [('ebay', 'Official eBay Category'), ('store', 'Custom Store Category')],
        string='Category Type',
    )

    @api.one
    @api.depends('category_parent_id', 'name')
    def _compute_full_name(self):
        name = self.name if self.name else ''
        parent_id = self.category_parent_id
        category_type = self.category_type
        while parent_id != '0':
            parent = self.search([
                ('category_id', '=', parent_id),
                ('category_type', '=', category_type),
            ])
            parent_name = parent.name if parent.name else ''
            name = parent_name + " > " + name
            parent_id = parent.category_parent_id if parent.category_parent_id else '0'
        self.full_name = name

    @api.multi
    def name_get(self):
        result = []
        for cat in self:
            result.append((cat.id, cat.full_name))
        return result

    @api.model
    def _cron_sync(self, auto_commit=False):
        try:
            self.sync_categories()
        except UserError, e:
            if auto_commit:
                self.env.cr.rollback()
                self.env.user.message_post(
                    body=_("eBay error: Impossible to synchronize the categories. \n'%s'") % e[0])
                self.env.cr.commit()
            else:
                raise e
        except RedirectWarning, e:
            if not auto_commit:
                raise e
            # not configured, ignore
            return

    @api.model
    def sync_categories(self):
        self.sync_store_categories()

        domain = self.env['ir.config_parameter'].get_param('ebay_domain')
        prod = self.env['product.template']
        # First call to 'GetCategories' to only get the categories' version
        categories = prod.ebay_execute('GetCategories')
        ebay_version = categories.dict()['Version']
        version = self.env['ir.config_parameter'].get_param('ebay_sandbox_category_version'
                                                            if domain == 'sand'
                                                            else 'ebay_prod_category_version')
        if version != ebay_version:
            # If the version returned by eBay is different than the one in Odoo
            # Another call to 'GetCategories' with all the information (ReturnAll) is done
            self.env['ir.config_parameter'].set_param('ebay_sandbox_category_version'
                                                      if domain == 'sand'
                                                      else 'ebay_prod_category_version',
                                                      ebay_version)
            call_data = {
                'DetailLevel': 'ReturnAll',
                'LevelLimit': 4,
            }
            response = prod.ebay_execute('GetCategories', call_data)
            categories = response.dict()['CategoryArray']['Category']
            # Delete the eBay categories not existing anymore on eBay
            category_ids = map(lambda c: c['CategoryID'], categories)
            self.search([
                ('category_id', 'not in', category_ids),
                ('category_type', '=', 'ebay'),
            ]).unlink()
            self.create_categories(categories)

    @api.model
    def create_categories(self, categories):
        for category in categories:
            cat = self.search([
                ('category_id', '=', category['CategoryID']),
                ('category_type', '=', 'ebay'),
            ])
            if not cat:
                cat = self.create({
                    'category_id': category['CategoryID'],
                    'category_type': 'ebay',
                })
            cat.write({
                'name': category['CategoryName'],
                'category_parent_id': category['CategoryParentID'] if category['CategoryID'] != category['CategoryParentID'] else '0',
                'leaf_category': category.get('LeafCategory'),
            })
            if category['CategoryLevel'] == '1':
                call_data = {
                    'CategoryID': category['CategoryID'],
                    'ViewAllNodes': True,
                    'DetailLevel': 'ReturnAll',
                    'AllFeaturesForCategory': True,
                }
                response = self.env['product.template'].ebay_execute('GetCategoryFeatures', call_data)
                if 'ConditionValues' in response.dict()['Category']:
                    conditions = response.dict()['Category']['ConditionValues']['Condition']
                    if not isinstance(conditions, list):
                        conditions = [conditions]
                    for condition in conditions:
                        if not self.env['ebay.item.condition'].search([('code', '=', condition['ID'])]):
                            self.env['ebay.item.condition'].create({
                                'code': condition['ID'],
                                'name': condition['DisplayName'],
                            })

    @api.model
    def sync_store_categories(self):
        response = self.env['product.template'].ebay_execute('GetStore')
        categories = response.dict()['Store']['CustomCategories']['CustomCategory']
        if not isinstance(categories, list):
            categories = [categories]
        new_categories = []
        self._create_store_categories(categories, '0', new_categories)
        # Delete the store categories not existing anymore on eBay
        self.search([
            ('category_id', 'not in', new_categories),
            ('category_type', '=', 'store'),
        ]).unlink()

    @api.model
    def _create_store_categories(self, categories, parent_id, new_categories):
        for category in categories:
            cat = self.search([
                ('category_id', '=', category['CategoryID']),
                ('category_type', '=', 'store'),
            ])
            if not cat:
                cat = self.create({
                    'category_id': category['CategoryID'],
                    'category_type': 'store',
                })
            cat.write({
                'name': category['Name'],
                'category_parent_id': parent_id,
            })
            new_categories.append(category['CategoryID'])
            if 'ChildCategory' in category:
                cat._create_store_categories(category['ChildCategory'], cat.category_id, new_categories)
            else:
                cat.leaf_category = True


class ebay_policy(models.Model):
    _name = 'ebay.policy'

    name = fields.Char('Name')
    policy_id = fields.Char('Policy ID')
    policy_type = fields.Char('Type')
    short_summary = fields.Text('Summary')

    @api.model
    def sync_policies(self):
        response = self.env['product.template'].ebay_execute('GetUserPreferences',
            {'ShowSellerProfilePreferences': True})
        if 'SellerProfilePreferences' not in response.dict() or \
           not response.dict()['SellerProfilePreferences']['SupportedSellerProfiles']:
                raise UserError(_('No Business Policies'))
        policies = response.dict()['SellerProfilePreferences']['SupportedSellerProfiles']['SupportedSellerProfile']
        if not isinstance(policies, list):
            policies = [policies]
        # Delete the policies not existing anymore on eBay
        policy_ids = map(lambda p: p['ProfileID'], policies)
        self.search([('policy_id', 'not in', policy_ids)]).unlink()
        for policy in policies:
            record = self.search([('policy_id', '=', policy['ProfileID'])])
            if not record:
                record = self.create({
                    'policy_id': policy['ProfileID'],
                })
            record.write({
                'name': policy['ProfileName'],
                'policy_type': policy['ProfileType'],
                'short_summary': policy['ShortSummary'] if 'ShortSummary' in policy else ' ',
            })


class ebay_item_condition(models.Model):
    _name = 'ebay.item.condition'

    name = fields.Char('Name')
    code = fields.Integer('Code')


class ebay_link_listing(models.TransientModel):
    _name = 'ebay.link.listing'

    ebay_id = fields.Char('eBay Listing ID')

    @api.one
    def link_listing(self):
        response = self.env['product.template'].ebay_execute('GetItem', {
            'ItemID': self.ebay_id,
            'DetailLevel': 'ReturnAll'
        })
        item = response.dict()['Item']
        currency = self.env['res.currency'].search([
            ('name', '=', item['StartPrice']['_currencyID'])])
        product = self.env['product.template'].browse(self._context.get('active_id'))
        product_values = {
            'ebay_id': item['ItemID'],
            'ebay_url': item['ListingDetails']['ViewItemURL'],
            'ebay_listing_status': item['SellingStatus']['ListingStatus'],
            'ebay_title': item['Title'],
            'ebay_subtitle': item['SubTitle'] if 'SubTitle' in item else False,
            'ebay_description': item['Description'],
            'ebay_item_condition_id': self.env['ebay.item.condition'].search([
                ('code', '=', item['ConditionID'])
            ]).id if 'ConditionID' in item else False,
            'ebay_category_id': self.env['ebay.category'].search([
                ('category_id', '=', item['PrimaryCategory']['CategoryID']),
                ('category_type', '=', 'ebay')
            ]).id,
            'ebay_store_category_id': self.env['ebay.category'].search([
                ('category_id', '=', item['Storefront']['StoreCategoryID']),
                ('category_type', '=', 'store')
            ]).id,
            'ebay_store_category_2_id': self.env['ebay.category'].search([
                ('category_id', '=', item['Storefront']['StoreCategory2ID']),
                ('category_type', '=', 'store')
            ]).id,
            'ebay_price': currency.compute(
                float(item['StartPrice']['value']),
                self.env.user.company_id.currency_id
            ),
            'ebay_buy_it_now_price': currency.compute(
                float(item['BuyItNowPrice']['value']),
                self.env.user.company_id.currency_id
            ),
            'ebay_listing_type': item['ListingType'],
            'ebay_listing_duration': item['ListingDuration'],
            'ebay_best_offer': True if 'BestOfferDetails' in item
                and item['BestOfferDetails']['BestOfferEnabled'] == 'true' else False,
            'ebay_private_listing': True if item['PrivateListing'] == 'true' else False,
            'ebay_start_date': datetime.strptime(
                item['ListingDetails']['StartTime'].split('.')[0], '%Y-%m-%dT%H:%M:%S'),
            'ebay_last_sync': datetime.now(),
        }
        if 'SellerProfiles' in item:
            if 'SellerPaymentProfile' in item['SellerProfiles']\
                and 'PaymentProfileID' in item['SellerProfiles']['SellerPaymentProfile']:
                ebay_seller_payment_policy_id = self.env['ebay.policy'].search_read([
                    ('policy_type', '=', 'PAYMENT'),
                    ('policy_id', '=', item['SellerProfiles']['SellerPaymentProfile']['PaymentProfileID'])
                ], ['id'])
                if ebay_seller_payment_policy_id:
                    product_values['ebay_seller_payment_policy_id'] = ebay_seller_payment_policy_id[0]['id']
            if 'SellerReturnProfile' in item['SellerProfiles']\
                and 'ReturnProfileID' in item['SellerProfiles']['SellerReturnProfile']:
                ebay_seller_return_policy_id = self.env['ebay.policy'].search_read([
                    ('policy_type', '=', 'RETURN_POLICY'),
                    ('policy_id', '=', item['SellerProfiles']['SellerReturnProfile']['ReturnProfileID'])
                ], ['id'])
                if ebay_seller_return_policy_id:
                    product_values['ebay_seller_return_policy_id'] = ebay_seller_return_policy_id[0]['id']
            if 'SellerShippingProfile' in item['SellerProfiles']\
                and 'ShippingProfileID' in item['SellerProfiles']['SellerShippingProfile']:
                ebay_seller_shipping_policy_id = self.env['ebay.policy'].search([
                    ('policy_type', '=', 'SHIPPING'),
                    ('policy_id', '=', item['SellerProfiles']['SellerShippingProfile']['ShippingProfileID'])
                ])
                if ebay_seller_shipping_policy_id:
                    product_values['ebay_seller_shipping_policy_id'] = ebay_seller_shipping_policy_id[0]['id']
        product.write(product_values)

        if 'Variations' in item:
            variations = item['Variations']['Variation']
            if not isinstance(variations, list):
                variations = [variations]
            for variation in variations:
                specs = variation['VariationSpecifics']['NameValueList']
                attrs = []
                if not isinstance(specs, list):
                    specs = [specs]
                for spec in specs:
                    attr = self.env['product.attribute.value'].search([('name', '=', spec['Value'])])
                    attrs.append(('attribute_value_ids', '=', attr.id))
                variant = self.env['product.product'].search(attrs).filtered(
                    lambda l: l.product_tmpl_id.id == product.id)
                variant.write({
                    'ebay_use': True,
                    'ebay_quantity_sold': variation['SellingStatus']['QuantitySold'],
                    'ebay_fixed_price': currency.compute(
                        float(variation['StartPrice']['value']),
                        self.env.user.company_id.currency_id
                    ),
                    'ebay_quantity': int(variation['Quantity']) - int(variation['SellingStatus']['QuantitySold']),
                })
            product._set_variant_url(self.ebay_id)
        elif product.product_variant_count == 1:
            product.product_variant_ids.write({
                'ebay_quantity_sold': item['SellingStatus']['QuantitySold'],
                'ebay_fixed_price': currency.compute(
                    float(item['StartPrice']['value']),
                    self.env.user.company_id.currency_id
                ),
                'ebay_quantity': int(item['Quantity']) - int(item['SellingStatus']['QuantitySold']),
            })
