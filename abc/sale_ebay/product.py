# -*- coding: utf-8 -*-

import base64
from datetime import datetime, timedelta
from openerp import models, fields, api, _
from datetime import datetime, timedelta
from openerp.exceptions import UserError, RedirectWarning
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from StringIO import StringIO
from xml.sax.saxutils import escape
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

# eBay api limits ItemRevise calls to 150 per day 
MAX_REVISE_CALLS = 150


class product_template(models.Model):
    _inherit = "product.template"

    ebay_id = fields.Char('eBay ID')
    ebay_use = fields.Boolean('Use eBay', default=False)
    ebay_url = fields.Char('eBay url', readonly=True)
    ebay_listing_status = fields.Char('eBay Status', default='Unlisted', readonly=True)
    ebay_title = fields.Char('Title', size=80,
        help='The title is restricted to 80 characters')
    ebay_subtitle = fields.Char('Subtitle', size=55,
        help='The subtitle is restricted to 55 characters. Fees can be claimed by eBay for this feature')
    ebay_description = fields.Html('Description')
    ebay_item_condition_id = fields.Many2one('ebay.item.condition', string="Item Condition")
    ebay_category_id = fields.Many2one('ebay.category',
        string="Category", domain=[('category_type', '=', 'ebay'),('leaf_category','=',True)])
    ebay_category_2_id = fields.Many2one('ebay.category',
        string="Category 2 (Optional)", domain=[('category_type', '=', 'ebay'),('leaf_category','=',True)],
        help="The use of a secondary category is not allowed on every eBay sites. Fees can be claimed by eBay for this feature")
    ebay_store_category_id = fields.Many2one('ebay.category',
        string="Store Category (Optional)", domain=[('category_type', '=', 'store'),('leaf_category','=',True)])
    ebay_store_category_2_id = fields.Many2one('ebay.category',
        string="Store Category 2 (Optional)", domain=[('category_type', '=', 'store'),('leaf_category','=',True)])
    ebay_price = fields.Float(string='Starting Price for Auction')
    ebay_buy_it_now_price = fields.Float(string='Buy It Now Price')
    ebay_listing_type = fields.Selection([
        ('Chinese', 'Auction'),
        ('FixedPriceItem', 'Fixed price')], string='Listing Type', default='Chinese')
    ebay_listing_duration = fields.Selection([
        ('Days_3', '3 Days'),
        ('Days_5', '5 Days'),
        ('Days_7', '7 Days'),
        ('Days_10', '10 Days'),
        ('Days_30', '30 Days (only for fixed price)'),
        ('GTC', 'Good \'Til Cancelled (only for fixed price)')],
        string='Duration', default='Days_7')
    ebay_seller_payment_policy_id = fields.Many2one('ebay.policy',
        string="Payment Policy", domain=[('policy_type', '=', 'PAYMENT')])
    ebay_seller_return_policy_id = fields.Many2one('ebay.policy',
        string="Return Policy", domain=[('policy_type', '=', 'RETURN_POLICY')])
    ebay_seller_shipping_policy_id = fields.Many2one('ebay.policy',
        string="Shipping Policy", domain=[('policy_type', '=', 'SHIPPING')])
    ebay_sync_stock = fields.Boolean(string="Use Stock Quantity", default=False)
    ebay_best_offer = fields.Boolean(string="Allow Best Offer", default=False)
    ebay_private_listing = fields.Boolean(string="Private Listing", default=False)
    ebay_start_date = fields.Datetime('Start Date', readonly=1)
    ebay_quantity_sold = fields.Integer(related='product_variant_ids.ebay_quantity_sold', store=True)
    ebay_fixed_price = fields.Float(related='product_variant_ids.ebay_fixed_price', store=True)
    ebay_quantity = fields.Integer(related='product_variant_ids.ebay_quantity', store=True)
    ebay_last_sync = fields.Datetime(string="Last update")
    ebay_template_id = fields.Many2one('mail.template', string='Description Template',
        ondelete='set null',
        help='This field contains the template that will be used.')

    _defaults = {
        'date': fields.Datetime.now()
    }

    @api.multi
    def _prepare_item_dict(self):
        if self.ebay_sync_stock:
            self.ebay_quantity = max(int(self.virtual_available), 0)
        country_id = self.env['ir.config_parameter'].get_param('ebay_country')
        country = self.env['res.country'].browse(int(country_id))
        currency_id = self.env['ir.config_parameter'].get_param('ebay_currency')
        currency = self.env['res.currency'].browse(int(currency_id))
        comp_currency = self.env.user.company_id.currency_id
        item = {
            "Item": {
                "Title": self._ebay_encode(self.ebay_title),
                "PrimaryCategory": {"CategoryID": self.ebay_category_id.category_id},
                "StartPrice": comp_currency.compute(self.ebay_price, currency)
                if self.ebay_listing_type == 'Chinese'
                else comp_currency.compute(self.ebay_fixed_price, currency),
                "CategoryMappingAllowed": "true",
                "Country": country.code,
                "Currency": currency.name,
                "ConditionID": self.ebay_item_condition_id.code,
                "ListingDuration": self.ebay_listing_duration,
                "ListingType": self.ebay_listing_type,
                "PostalCode": self.env['ir.config_parameter'].get_param('ebay_zip_code'),
                "Location": self.env['ir.config_parameter'].get_param('ebay_location'),
                "Quantity": self.ebay_quantity,
                "BestOfferDetails": {'BestOfferEnabled': self.ebay_best_offer},
                "PrivateListing": self.ebay_private_listing,
                "SellerProfiles": {
                    "SellerPaymentProfile": {
                        "PaymentProfileID": self.ebay_seller_payment_policy_id.policy_id,
                    },
                    "SellerReturnProfile": {
                        "ReturnProfileID": self.ebay_seller_return_policy_id.policy_id,
                    },
                    "SellerShippingProfile": {
                        "ShippingProfileID": self.ebay_seller_shipping_policy_id.policy_id,
                    }
                },
            }
        }
        if self.ebay_description and self.ebay_template_id:
            description = self.ebay_template_id.render_template(self.ebay_template_id.body_html, 'product.template', self.id)
            item['Item']['Description'] = '<![CDATA['+description+']]>'
        if self.ebay_subtitle:
            item['Item']['SubTitle'] = self._ebay_encode(self.ebay_subtitle)
        picture_urls = self._create_picture_url()
        if picture_urls:
            item['Item']['PictureDetails'] = {'PictureURL': picture_urls}
            if self.env['ir.config_parameter'].get_param('ebay_gallery_plus'):
                item['Item']['PictureDetails']['GalleryType'] = 'Plus'
        if self.ebay_listing_type == 'Chinese' and self.ebay_buy_it_now_price:
            item['Item']['BuyItNowPrice'] = comp_currency.compute(self.ebay_buy_it_now_price, currency)
        NameValueList = []
        variant = self.product_variant_ids.filtered('ebay_use')
        # If only one variant selected to be published, we don't create variant
        # but set the variant's value has an item specific on eBay
        if len(variant) == 1 \
           and self.ebay_listing_type == 'FixedPriceItem':
            for spec in variant.attribute_value_ids:
                NameValueList.append({
                    'Name': self._ebay_encode(spec.attribute_id.name),
                    'Value': self._ebay_encode(spec.name),
                })
            if self.ebay_sync_stock:
                variant.ebay_quantity = max(int(variant.virtual_available), 0)
            item['Item']['Quantity'] = variant.ebay_quantity
            item['Item']['StartPrice'] = variant.ebay_fixed_price
        # If one attribute has only one value, we don't create variant
        # but set the value has an item specific on eBay
        elif self.attribute_line_ids:
            for attribute in self.attribute_line_ids:
                if len(attribute.value_ids) == 1:
                    NameValueList.append({
                        'Name': self._ebay_encode(attribute.attribute_id.name),
                        'Value': self._ebay_encode(attribute.value_ids.name),
                    })

        if NameValueList:
            item['Item']['ItemSpecifics'] = {'NameValueList': NameValueList}
        if self.ebay_category_2_id:
            item['Item']['SecondaryCategory'] = {'CategoryID': self.ebay_category_2_id.category_id}
        if self.ebay_store_category_id:
            item['Item']['Storefront'] = {
                'StoreCategoryID': self.ebay_store_category_id.category_id,
                'StoreCategoryName': self._ebay_encode(self.ebay_store_category_id.name),
            }
            if self.ebay_store_category_2_id:
                item['Item']['Storefront']['StoreCategory2ID'] = self.ebay_store_category_2_id.category_id
                item['Item']['Storefront']['StoreCategory2Name'] = self._ebay_encode(self.ebay_store_category_2_id.name)
        return item

    @api.model
    def _ebay_encode(self, string):
        return escape(string.strip().encode('utf-8')) if string else ''

    @api.multi
    def _prepare_non_variant_dict(self):
        item = self._prepare_item_dict()
        item['Item']['ProductListingDetails'] = {'UPC': 'Does not Apply'}
        if self.barcode:
            if len(self.barcode) == 12:
                item['Item']['ProductListingDetails']['UPC'] = self.barcode
            elif len(self.barcode) == 13:
                item['Item']['ProductListingDetails']['EAN'] = self.barcode
        return item

    @api.multi
    def _prepare_variant_dict(self):
        if not self.product_variant_ids.filtered('ebay_use'):
            raise UserError(_("Error Encountered.\n No Variant Set To Be Listed On eBay."))
        currency_id = self.env['ir.config_parameter'].get_param('ebay_currency')
        currency = self.env['res.currency'].browse(int(currency_id))
        comp_currency = self.env.user.company_id.currency_id
        items = self._prepare_item_dict()
        items['Item']['Variations'] = {'Variation': []}
        variations = items['Item']['Variations']['Variation']

        name_values = {}
        for variant in self.product_variant_ids:
            if self.ebay_sync_stock:
                variant.ebay_quantity = max(int(variant.virtual_available), 0)
            if not variant.ebay_quantity and\
               not self.env['ir.config_parameter'].get_param('ebay_out_of_stock'):
                raise UserError(_('All the quantities must be greater than 0 or you need to enable the Out Of Stock option.'))
            variant_name_values = []
            for spec in variant.attribute_value_ids:
                attr_line = self.attribute_line_ids.filtered(
                    lambda l: l.attribute_id.id == spec.attribute_id.id)
                if len(attr_line.value_ids) > 1:
                    if spec.attribute_id.name not in name_values:
                        name_values[spec.attribute_id.name] = []
                    if spec.name not in name_values[spec.attribute_id.name]:
                        name_values[spec.attribute_id.name].append(spec.name)
                    variant_name_values.append({
                        'Name': self._ebay_encode(spec.attribute_id.name),
                        'Value': self._ebay_encode(spec.name),
                        })
            variations.append({
                'Quantity': variant.ebay_quantity,
                'StartPrice': comp_currency.compute(variant.ebay_fixed_price, currency),
                'VariationSpecifics': {'NameValueList': variant_name_values},
                'Delete': False if variant.ebay_use else True,
                })
        # example of a valid name value list array
        # possible_name_values = [{'Name':'size','Value':['16gb','32gb']},{'Name':'color', 'Value':['red','blue']}]
        possible_name_values = []
        for key in name_values:
            possible_name_values.append({
                'Name': self._ebay_encode(key),
                'Value': map(lambda n: self._ebay_encode(n), sorted(name_values[key]))
            })
        items['Item']['Variations']['VariationSpecificsSet'] = {
            'NameValueList': possible_name_values
        }
        return items

    @api.multi
    def _get_item_dict(self):
        if len(self.product_variant_ids) > 1 \
           and self.ebay_listing_type == 'FixedPriceItem':
            item_dict = self._prepare_variant_dict()
        else:
            item_dict = self._prepare_non_variant_dict()
        return item_dict

    @api.one
    def _set_variant_url(self, item_id):
        variants = self.product_variant_ids.filtered('ebay_use')
        if len(variants) > 1 and self.ebay_listing_type == 'FixedPriceItem':
            for variant in variants:
                name_value_list = [{
                    'Name': self._ebay_encode(spec.attribute_id.name),
                    'Value': self._ebay_encode(spec.name)
                } for spec in variant.attribute_value_ids]
                call_data = {
                    'ItemID': item_id,
                    'VariationSpecifics': {
                        'NameValueList': name_value_list
                    }
                }
                item = self.ebay_execute('GetItem', call_data)
                variant.ebay_variant_url = item.dict()['Item']['ListingDetails']['ViewItemURL']

    @api.model
    def get_ebay_api(self, domain):
        dev_id = self.env['ir.config_parameter'].get_param('ebay_dev_id')
        site_id = self.env['ir.config_parameter'].get_param('ebay_site')
        site = self.env['ebay.site'].browse(int(site_id))
        if domain == 'sand':
            app_id = self.env['ir.config_parameter'].get_param('ebay_sandbox_app_id')
            cert_id = self.env['ir.config_parameter'].get_param('ebay_sandbox_cert_id')
            token = self.env['ir.config_parameter'].get_param('ebay_sandbox_token')
            domain = 'api.sandbox.ebay.com'
        else:
            app_id = self.env['ir.config_parameter'].get_param('ebay_prod_app_id')
            cert_id = self.env['ir.config_parameter'].get_param('ebay_prod_cert_id')
            token = self.env['ir.config_parameter'].get_param('ebay_prod_token')
            domain = 'api.ebay.com'

        if not app_id or not cert_id or not token:
            action = self.env.ref('base_setup.action_sale_config')
            raise RedirectWarning(_('One parameter is missing.'),
                                  action.id, _('Configure The eBay Integrator Now'))

        return Trading(domain=domain,
                       config_file=None,
                       appid=app_id,
                       devid=dev_id,
                       certid=cert_id,
                       token=token,
                       siteid=int(site.ebay_id))

    @api.model
    def ebay_execute(self, verb, data=None, list_nodes=[], verb_attrs=None, files=None):
        domain = self.env['ir.config_parameter'].get_param('ebay_domain')
        ebay_api = self.get_ebay_api(domain)
        try:
            return ebay_api.execute(verb, data, list_nodes, verb_attrs, files)
        except ConnectionError as e:
            errors = e.response.dict()['Errors']
            if not isinstance(errors, list):
                errors = [errors]
            error_message = ''
            for error in errors:
                if error['SeverityCode'] == 'Error':
                    error_message += error['LongMessage']
            if 'Condition is required for this category.' in error_message:
                error_message += _('Or the condition is not compatible with the category.')
            if any(s in error for s in ['Internal error to the application', 'Internal application error']):
                error_message = _('eBay is unreachable. Please try again later.')
            if 'Invalid Multi-SKU item id supplied with variations' in error_message:
                error_message = _('Impossible to revise a listing into a multi-variations listing.\n Create a new listing.')
            if 'UPC is missing a value.' in error_message:
                error_message = _('The UPC value (the barcode value of your product) is not valid by using the checksum.')
            if 'must have a quantity greater than 0' in error_message:
                error_message += _(" If you want to set quantity to 0, the Out Of Stock option should be enabled"
                                  " and the listing duration should set to Good 'Til Canceled")
            if 'Item Specifics entered for a Multi-SKU item should be different' in error_message:
                error_message = _(" You need to have at least 2 variations selected for a multi-variations listing.\n"
                                   " Or if you try to delete a variation, you cannot do it by unselecting it."
                                   " Setting the quantity to 0 is the safest method to make a variation unavailable.")
            raise UserError(_("Error Encountered.\n'%s'") % (error_message,))

    @api.multi
    def _create_picture_url(self):
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id)
        ], order="create_date")

        urls = []
        for att in attachments:
            image = StringIO(base64.standard_b64decode(att["datas"]))
            files = {'file': ('EbayImage', image)}
            pictureData = {
                "WarningLevel": "High",
                "PictureName": self.name
            }
            response = self.ebay_execute('UploadSiteHostedPictures', pictureData, files=files)
            urls.append(response.dict()['SiteHostedPictureDetails']['FullURL'])
        return urls

    @api.one
    def _update_ebay_data(self, response):
        domain = self.env['ir.config_parameter'].get_param('ebay_domain')
        item = self.ebay_execute('GetItem', {'ItemID': response['ItemID']}).dict()
        qty = int(item['Item']['Quantity']) - int(item['Item']['SellingStatus']['QuantitySold'])
        self.write({
            'ebay_listing_status': 'Active' if qty > 0 else 'Out Of Stock',
            'ebay_id': response['ItemID'],
            'ebay_url': item['Item']['ListingDetails']['ViewItemURL'],
            'ebay_start_date': datetime.strptime(response['StartTime'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
        })

    @api.one
    def push_product_ebay(self):
        if self.ebay_listing_status != 'Active':
            item_dict = self._get_item_dict()
            response = self.ebay_execute('AddItem' if self.ebay_listing_type == 'Chinese'
                                         else 'AddFixedPriceItem', item_dict)
            self._set_variant_url(response.dict()['ItemID'])
            self._update_ebay_data(response.dict())

    @api.one
    def end_listing_product_ebay(self):
        call_data = {"ItemID": self.ebay_id,
                     "EndingReason": "NotAvailable"}
        self.ebay_execute('EndItem' if self.ebay_listing_type == 'Chinese'
                          else 'EndFixedPriceItem', call_data)
        self.ebay_listing_status = 'Ended'

    @api.one
    def relist_product_ebay(self):
        item_dict = self._get_item_dict()
        # set the item id to relist the correct ebay listing
        item_dict['Item']['ItemID'] = self.ebay_id
        response = self.ebay_execute('RelistItem' if self.ebay_listing_type == 'Chinese'
                                     else 'RelistFixedPriceItem', item_dict)
        self._set_variant_url(response.dict()['ItemID'])
        self._update_ebay_data(response.dict())

    @api.one
    def revise_product_ebay(self):
        item_dict = self._get_item_dict()
        # set the item id to revise the correct ebay listing
        item_dict['Item']['ItemID'] = self.ebay_id
        if not self.ebay_subtitle:
            item_dict['DeletedField'] = 'Item.SubTitle'

        response = self.ebay_execute('ReviseItem' if self.ebay_listing_type == 'Chinese'
                                     else 'ReviseFixedPriceItem', item_dict)
        self._set_variant_url(response.dict()['ItemID'])
        self._update_ebay_data(response.dict())

    @api.model
    def sync_product_status(self, sync_big_stocks=False, auto_commit=False):
        self._sync_recent_product_status(1, sync_big_stocks=sync_big_stocks, auto_commit=auto_commit)
        self._sync_old_product_status(sync_big_stocks=sync_big_stocks, auto_commit=auto_commit)

    @api.model
    def _sync_recent_product_status(self, page_number=1, sync_big_stocks=False, auto_commit=False):
        call_data = {'StartTimeFrom': str(datetime.today()-timedelta(days=119)),
                     'StartTimeTo': str(datetime.today()),
                     'DetailLevel': 'ReturnAll',
                     'Pagination': {'EntriesPerPage': 200,
                                    'PageNumber': page_number,
                                    }
                     }
        try:
            response = self.ebay_execute('GetSellerList', call_data)
        except UserError, e:
            if auto_commit:
                self.env.cr.rollback()
                self.env.user.message_post(body=_("eBay error: Impossible to synchronize the products. \n'%s'") % e[0])
                self.env.cr.commit()
            else:
                raise e
        except RedirectWarning, e:
            if not auto_commit:
                raise e
            # not configured, ignore
            return
        if response.dict()['ItemArray'] is None:
            return
        items = response.dict()['ItemArray']['Item']
        if not isinstance(items, list):
            items = [items]
        for item in items:
            domain = [
                ('ebay_id', '=', item['ItemID']),
                ('virtual_available', '>' if sync_big_stocks else '<', MAX_REVISE_CALLS),
            ]
            product = self.search(domain)
            if product:
                product._sync_transaction(item, auto_commit=auto_commit)
        if page_number < int(response.dict()['PaginationResult']['TotalNumberOfPages']):
            self._sync_product_status(page_number + 1)

    @api.model
    def _sync_old_product_status(self, sync_big_stocks=False, auto_commit=False):
        date = (datetime.today()-timedelta(days=119)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        domain = [
            ('ebay_use', '=', True),
            ('ebay_start_date', '<', date),
            ('ebay_listing_status', 'in', ['Active', 'Error']),
            ('virtual_available', '>' if sync_big_stocks else '<', MAX_REVISE_CALLS),
        ]
        products = self.search(domain)
        for product in products:
            response = self.ebay_execute('GetItem', {'ItemID': product.ebay_id})
            product._sync_transaction(response.dict()['Item'], auto_commit=auto_commit)
        return

    @api.one
    def _sync_transaction(self, item, auto_commit=False):
        try:
            if self.ebay_listing_status != 'Ended'\
               and self.ebay_listing_status != 'Out Of Stock':
                self.ebay_listing_status = item['SellingStatus']['ListingStatus']
                if self.env['ir.config_parameter'].get_param('ebay_out_of_stock') and\
                   self.ebay_listing_status == 'Ended':
                    self.ebay_listing_status = 'Out Of Stock'
                if int(item['SellingStatus']['QuantitySold']) > 0:
                    call_data = {
                        'ItemID': item['ItemID'],
                    }
                    if self.ebay_last_sync:
                        call_data['ModTimeFrom'] = str(self.ebay_last_sync)
                        self.ebay_last_sync = datetime.now()
                    resp = self.ebay_execute('GetItemTransactions', call_data).dict()
                    if 'TransactionArray' in resp:
                        transactions = resp['TransactionArray']['Transaction']
                        if not isinstance(transactions, list):
                            transactions = [transactions]
                        for transaction in transactions:
                            if transaction['Status']['CheckoutStatus'] == 'CheckoutComplete':
                                self.create_sale_order(transaction)
            self.sync_available_qty()
        except UserError, e:
            if auto_commit:
                self.env.cr.rollback()
                self.ebay_listing_status = 'Error'
                self.message_post(
                    body=_("eBay error: Impossible to synchronize the products. \n'%s'") % e[0])
                self.env.cr.commit()
            else:
                raise e
        except RedirectWarning, e:
            if not auto_commit:
                raise e
            # not configured, ignore
            return

    @api.one
    def create_sale_order(self, transaction):
        if not self.env['sale.order'].search([
           ('client_order_ref', '=', transaction['OrderLineItemID'])]):
            partner = self.env['res.partner'].search([
                ('email', '=', transaction['Buyer']['Email'])])
            if not partner:
                partner = self.env['res.partner'].create({'name': transaction['Buyer']['UserID']})
            partner_data = {
                'name': transaction['Buyer']['UserID'],
                'ebay_id': transaction['Buyer']['UserID'],
                'email': transaction['Buyer']['Email'],
                'ref': 'eBay',
            }
            if 'BuyerInfo' in transaction['Buyer'] and\
               'ShippingAddress' in transaction['Buyer']['BuyerInfo']:
                infos = transaction['Buyer']['BuyerInfo']['ShippingAddress']
                partner_data['name'] = infos.get('Name')
                partner_data['street'] = infos.get('Street1')
                partner_data['street2'] = infos.get('Street2')
                partner_data['city'] = infos.get('CityName')
                partner_data['zip'] = infos.get('PostalCode')
                partner_data['phone'] = infos.get('Phone')
                partner_data['country_id'] = self.env['res.country'].search([
                    ('code', '=', infos['Country'])
                ]).id
                state = self.env['res.country.state'].search([
                    ('code', '=', infos.get('StateOrProvince')),
                    ('country_id', '=', partner_data['country_id'])
                ])
                if not state:
                    state = self.env['res.country.state'].search([
                        ('name', '=', infos.get('StateOrProvince')),
                        ('country_id', '=', partner_data['country_id'])
                    ])
                partner_data['state_id'] = state.id

            partner.write(partner_data)
            if self.product_variant_count > 1:
                if 'Variation' in transaction:
                    variant = self.product_variant_ids.filtered(
                        lambda l:
                        l.ebay_use and
                        l.ebay_variant_url.split("vti", 1)[1] ==
                        transaction['Variation']['VariationViewItemURL'].split("vti", 1)[1])
                # If multiple variants but only one listed on eBay as Item Specific
                else:
                    call_data = {'ItemID': self.ebay_id, 'IncludeItemSpecifics': True}
                    resp = self.ebay_execute('GetItem', call_data)
                    name_value_list = resp.dict()['Item']['ItemSpecifics']['NameValueList']
                    if not isinstance(name_value_list, list):
                        name_value_list = [name_value_list]
                    # get only the item specific in the value list
                    specs = filter(lambda n: n['Source'] == 'ItemSpecific', name_value_list)
                    attrs = []
                    # get the attribute.value ids in order to get the variant listed on ebay
                    for spec in specs:
                        attr = self.env['product.attribute.value'].search([('name', '=', spec['Value'])])
                        attrs.append(('attribute_value_ids', '=', attr.id))
                    variant = self.env['product.product'].search(attrs).filtered(
                        lambda l: l.product_tmpl_id.id == self.id)
            else:
                variant = self.product_variant_ids[0]
            variant.write({
                'ebay_quantity_sold': variant.ebay_quantity_sold + int(transaction['QuantityPurchased']),
                'ebay_quantity': variant.ebay_quantity - int(transaction['QuantityPurchased']),
                })
            sale_order = self.env['sale.order'].create({
                'partner_id': partner.id,
                'state': 'draft',
                'client_order_ref': transaction['OrderLineItemID'],
                'origin': 'eBay' + transaction['TransactionID'],
            })
            if self.env['ir.config_parameter'].get_param('ebay_sales_team'):
                sale_order.team_id = int(self.env['ir.config_parameter'].get_param('ebay_sales_team'))

            currency = self.env['res.currency'].search([
                ('name', '=', transaction['TransactionPrice']['_currencyID'])])
            self.env['sale.order.line'].create({
                'product_id': variant.id,
                'order_id': sale_order.id,
                'name': self.name,
                'product_uom_qty': float(transaction['QuantityPurchased']),
                'product_uom': variant.uom_id.id,
                'price_unit': currency.compute(
                    float(transaction['TransactionPrice']['value']),
                    self.env.user.company_id.currency_id),
            })
            # create a sale order line if a shipping service is selected
            if 'ShippingServiceSelected' in transaction:
                company_id = self.env.user.company_id
                ir_values = self.env['ir.values']
                taxes_id = ir_values.get_default('product.template', 'taxes_id', company_id=company_id.id)
                shipping_name = transaction['ShippingServiceSelected']['ShippingService']
                shipping_product = self.env['product.template'].search([('name', '=', shipping_name)])
                if not shipping_product:
                    shipping_product = self.env['product.template'].create({
                        'name': shipping_name,
                        'uom_id': self.env.ref('product.product_uom_unit').id,
                        'type': 'service',
                        'categ_id': self.env.ref('sale_ebay.product_category_ebay').id,
                    })
                so_line = self.env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'name': shipping_name,
                    'product_id': shipping_product.product_variant_ids[0].id,
                    'product_uom_qty': 1,
                    'product_uom': self.env.ref('product.product_uom_unit').id,
                    'price_unit': currency.compute(
                            float(transaction['ShippingServiceSelected']['ShippingServiceCost']['value']),
                            company_id.currency_id),
                    'tax_id': [(6, 0, taxes_id)] if taxes_id else False,
                })
                so_line._compute_tax_id()
            sale_order.action_confirm()
            if 'BuyerCheckoutMessage' in transaction:
                sale_order.message_post(_('The Buyer Posted :\n') + transaction['BuyerCheckoutMessage'])
                sale_order.picking_ids.message_post(_('The Buyer Posted :\n') + transaction['BuyerCheckoutMessage'])
            if 'ShippingServiceSelected' in transaction:
                sale_order.picking_ids.message_post(
                    _('The Buyer Chose The Following Delivery Method :\n') + shipping_name)
            sale_order.action_invoice_create(final=True)

    @api.one
    def sync_available_qty(self):
        if self.ebay_use and self.ebay_sync_stock:
            if self.ebay_listing_status in ['Active', 'Error']:
                # The product is Active on eBay but there is no more stock
                if self.virtual_available <= 0:
                    # Only revise product if there is a change of quantity
                    if self.ebay_quantity != self.virtual_available:
                        # If the Out Of Stock option is enabled only need to revise the quantity
                        if self.env['ir.config_parameter'].get_param('ebay_out_of_stock'):
                            self.revise_product_ebay()
                            self.ebay_listing_status = 'Out Of Stock'
                        else:
                            self.end_listing_product_ebay()
                            self.ebay_listing_status = 'Ended'
                # The product is Active on eBay and there is some stock
                # Check if the quantity in Odoo is different than the one on eBay
                # If it is the case revise the quantity
                else:
                    if len(self.product_variant_ids.filtered('ebay_use')) > 1:
                        for variant in self.product_variant_ids:
                            if variant.virtual_available != variant.ebay_quantity:
                                self.revise_product_ebay()
                                break
                    else:
                        if self.ebay_quantity != self.virtual_available:
                            self.revise_product_ebay()
            elif self.ebay_listing_status == 'Out Of Stock':
                # The product is Out Of Stock on eBay but there is stock in Odoo
                # If the Out Of Stock option is enabled then only revise the product
                if self.virtual_available > 0 and self.ebay_quantity != self.virtual_available:
                    if self.env['ir.config_parameter'].get_param('ebay_out_of_stock'):
                        self.revise_product_ebay()
                    else:
                        self.relist_product_ebay()

    @api.model
    def _cron_sync_ebay_products(self, sync_big_stocks=False, auto_commit=False):
        self.sync_product_status(sync_big_stocks=sync_big_stocks, auto_commit=auto_commit)

    @api.model
    def sync_ebay_products(self, page_number=1):
        self._sync_recent_product_status(1)
        self._sync_old_product_status()

class product_product(models.Model):
    _inherit = "product.product"

    ebay_use = fields.Boolean('Publish On eBay', default=False)
    ebay_quantity_sold = fields.Integer('Quantity Sold', readonly=True)
    ebay_fixed_price = fields.Float('Fixed Price')
    ebay_quantity = fields.Integer(string='Quantity', default=1)
    ebay_listing_type = fields.Selection(related='product_tmpl_id.ebay_listing_type')
    ebay_variant_url = fields.Char('eBay Variant URL')
