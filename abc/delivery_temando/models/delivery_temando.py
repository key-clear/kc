# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from openerp import fields, models, _
from openerp.exceptions import ValidationError

from temando_request import TemandoRequest

_logger = logging.getLogger(__name__)

TRACK_URL = 'https://temando.com/track?token='


class ProviderTemando(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('temando', "Temando")])

    temando_username = fields.Char(string='Temando Username')
    temando_password = fields.Char(string='Temando Password')
    temando_client_id = fields.Char(string='Temando Client Id')
    temando_test_mode = fields.Boolean(default=True, string="Test Mode", help="Uncheck this box to use production Temando Web Services")
    temando_delivery_nature = fields.Selection([('Domestic', 'Domestic'), ('International', 'International')], default="Domestic", required=True)
    temando_delivery_type = fields.Selection([('Door to Door', 'Door to Door'), ('Depot to Depot', 'Depot to Depot')], required=True, default='Door to Door')
    temando_preferred_carrier = fields.Integer(string="Preferred Carrier ID")

    # Required based on condition
    temando_subclass = fields.Selection([('Household Goods', 'Household Goods'), ('Furniture', 'Furniture'), ('Other (Etc.)', 'Other (Etc.)')], default='Other (Etc.)')
    temando_default_packaging_type = fields.Selection([('Box', 'Box'), ('Carton', 'Carton'), ('Document Envelope', 'Document Envelope'), ('Letter', 'Letter'), ('Pallet', 'Pallet'), ('Parcel', 'Parcel'), ('Unpackage or N/A', 'Unpackage or N/A')], default='Box')
    temando_pallet_type = fields.Selection([('Chep', 'chep'), ('Loscam', 'Loscam'), ('Plain', 'Plain'), ('Not Required', 'Not Required')])
    temando_pallet_nature = fields.Selection([('Exchange', 'Exchange'), ('Transfer', 'Transfer'), ('Not Required', 'Not Required')])
    temando_distance_measurement_type = fields.Selection([('Centimetres', 'Centimetres'), ('Metres', 'Metres'), ('Inches', 'Inches'), ('Feet', 'Feet')], default='Centimetres')
    temando_weight_measurement_type = fields.Selection([('Grams', 'Grams'), ('Kilograms', 'Kilograms'), ('Ounces', 'Ounces'), ('Pounds', 'Pounds')], default='Kilograms')
    temando_location_selection = fields.Selection([('Priority', 'Priority'), ('Nearest', 'Nearest'), ('Nearest by Priority', 'Nearest by Priority'), ('Most Stock', 'Most Stock')], default='Nearest')
    temando_hs_code = fields.Char(string='HS Code')
    temando_package_height = fields.Integer(string='Package Height', help="Fix Height if not provided on the product packaging.")
    temando_package_width = fields.Integer(string='Package Width', help="Fix Width if not provided on the product packaging.")
    temando_package_length = fields.Integer(string='Package Length', help="Fix Length if not provided on the product packaging.")

    def temando_get_shipping_price_from_so(self, orders):
        res = []
        ResCurrency = self.env['res.currency']

        for order in orders:
            price = 0.0

            request = TemandoRequest(self.temando_test_mode, self.temando_username, self.temando_password)
            request.check_required_value(order.partner_shipping_id, order.warehouse_id.partner_id, order=order)
            request.set_quotes_anything_detail(self, order)
            request.set_anywhere_detail(self, order.warehouse_id.partner_id, order.partner_shipping_id)
            request.set_general_detail(order.currency_id.name, order.amount_total, self.temando_delivery_nature)

            if self.temando_preferred_carrier:
                request.set_carrier_quotefilter_detail(order)
            else:
                request.set_cheapest_quotefilter_detail()

            quotes = request.rate_shipping()

            if quotes.get('error_message'):
                raise ValidationError(quotes['error_message'])

            if order.currency_id.name == quotes['currency']:
                price = quotes['price']
            else:
                quote_currency = ResCurrency.search([('name', '=', quotes['currency'])], limit=1)
                price = quote_currency.compute(float(quotes['price']), order.currency_id)

            order.write({'temando_carrier_id': quotes['carrier_id'],
                         'temando_carrier_name': quotes['carrier_name'],
                         'temando_delivery_method': quotes['delivery_method']})
            res = res + [price]
        return res

    def temando_send_shipping(self, pickings):
        res = []
        ResCurrency = self.env['res.currency']

        for picking in pickings:

            sale_order = picking.sale_id
            if not sale_order:
                raise ValidationError(_("This picking cannot be sent through Temando, as it has no linked sale order"))

            request = TemandoRequest(self.temando_test_mode, self.temando_username, self.temando_password)

            currency_order = sale_order.currency_id or picking.company_id.currency_id
            total_price = sum([(line.product_id.lst_price * line.product_uom_qty) for line in picking.move_lines]) or 0.0

            request.check_required_value(picking.partner_id, picking.picking_type_id.warehouse_id.partner_id, picking=picking)
            request.set_shipping_anything_detail(self, picking)

            request.set_anywhere_detail(self, picking.picking_type_id.warehouse_id.partner_id, picking.partner_id)
            request.set_location_origin_detail(picking.company_id.partner_id, picking.picking_type_id.warehouse_id.partner_id)
            request.set_location_destination_detail(picking.partner_id)

            request.set_carrier_quotefilter_detail(sale_order)

            request.set_client_reference(self.temando_client_id)
            request.set_general_detail(currency_order.name, total_price, self.temando_delivery_nature)
            request.set_payment_detail()
            request.set_labelprinter_detail()

            booking = request.make_booking()

            if booking.get('error_message'):
                raise ValidationError(booking['error_message'])

            if currency_order.name == booking['currency']:
                carrier_price = booking['price']
            else:
                booking_currency = ResCurrency.search([('name', '=', booking['currency'])], limit=1)
                carrier_price = booking_currency.compute(float(booking['price']), currency_order)

            carrier_name = booking['carrier_name']
            carrier_tracking_ref = booking['tracking_number']
            logmessage = (_("Shipment created into Temando <br/> <b>Carrier: </b>%s <br/> <b>Tracking Number: </b>%s") % (carrier_name, carrier_tracking_ref))
            attachments = request.save_label(picking.carrier_id.temando_delivery_nature) or []
            if attachments:
                attachments = [('LabelTemando-%s.pdf' % carrier_tracking_ref, attachments)]
            picking.message_post(body=logmessage, attachments=attachments)

            shipping_data = {'exact_price': carrier_price,
                             'tracking_number': carrier_tracking_ref}
            res = res + [shipping_data]

        return res

    def temando_get_tracking_link(self, pickings):
        res = []
        for picking in pickings:
            res = res + ['%s%s' % (TRACK_URL, picking.carrier_tracking_ref)]
        return res

    def temando_cancel_shipment(self, picking):
        request = TemandoRequest(self.temando_test_mode, self.temando_username, self.temando_password)

        request.set_deletion_detail(self.temando_client_id, picking.carrier_tracking_ref)
        result = request.cancel_shipment()

        if result.get('error_message'):
            raise ValidationError(result['error_message'])

        picking.write({'carrier_tracking_ref': False,
                       'carrier_price': False})
        logmessage = (_(u"Shipment N° %s has been cancelled") % (picking.carrier_tracking_ref))
        picking.message_post(body=logmessage)
