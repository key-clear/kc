# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import binascii
import time
from urllib2 import Request, urlopen, URLError
import xml.etree.ElementTree as etree
import unicodedata

from openerp import _
from openerp.exceptions import UserError
from openerp.exceptions import ValidationError


class DHLProvider():

    def __init__(self, test_mode):
        if test_mode:
            self.url = 'https://xmlpitest-ea.dhl.com/XMLShippingServlet'
        else:
            self.url = 'https://xmlpi-ea.dhl.com/XMLShippingServlet'

    def rate_request(self, order, carrier):
        dict_response = {'price': 0.0,
                         'currency': False,
                         'error_found': False}
        param = {
            'carrier': carrier,
            'shipper_partner': order.warehouse_id.partner_id,
            'Date': time.strftime('%Y-%m-%d'),
            'ReadyTime': time.strftime('PT%HH%MM'),
            'recipient_partner': order.partner_shipping_id,
            'total_weight': sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line]),
            'currency_name': order.currency_id.name,
            'total_value': sum([(line.price_unit * line.product_uom_qty) for line in order.order_line.filtered(lambda line: not line.is_delivery)]) or 0,
            'is_dutiable': carrier.dhl_dutiable,
            'package_ids': False,
        }
        request_text = self._create_rate_xml(param)
        root = self._send_request(request_text)
        if root.tag == '{http://www.dhl.com}ErrorResponse':
            condition = root.findall('Response/Status/Condition/ConditionData')
            raise UserError(_(condition[0].text))
        elif root.tag == '{http://www.dhl.com}DCTResponse':
            products = root.findall('GetQuoteResponse/BkgDetails/QtdShp')
            found = False
            for product in products:
                if product.findtext('GlobalProductCode') == carrier.dhl_product_code:
                    dict_response['price'] = product.findall('ShippingCharge')[0].text
                    dict_response['currency'] = product.findall('CurrencyCode')[0].text
                    found = True
            if not found:
                raise UserError(_("No shipping available for the selected DHL product"))
        return dict_response

    def send_shipping(self, picking, carrier):
        dict_response = {'tracking_number': 0.0,
                         'price': 0.0,
                         'currency': False}

        param = {
            # it's if you want to track the message numbers
            'MessageTime': '2001-12-17T09:30:47-05:00',
            'MessageReference': '1234567890123456789012345678901',
            'carrier': carrier,
            'RegionCode': carrier.dhl_region_code,
            'lang': 'en',
            'recipient_partner': picking.partner_id,
            'PiecesEnabled': 'Y',
            # Hard coded, S for Shipper, R for Recipient and T for Third Party
            'ShippingPaymentType': 'S',
            'recipient_streetLines': ('%s%s') % (picking.partner_id.street or '',
                                                 picking.partner_id.street2 or ''),
            'NumberOfPieces': len(picking.package_ids) or 1,
            'weight_bulk': picking.weight_bulk,
            'package_ids': picking.package_ids,
            'total_weight': picking.weight,
            # Odoo is working in KG
            'weight_unit': "K",
            'dimension_unit': carrier.dhl_package_dimension_unit[0],
            # For the rating API waits for CM and IN here for C and I...
            'GlobalProductCode': carrier.dhl_product_code,
            'Date': time.strftime('%Y-%m-%d'),
            'shipper_partner': picking.picking_type_id.warehouse_id.partner_id,
            'shipper_company': picking.company_id,
            'shipper_streetLines': ('%s%s') % (picking.picking_type_id.warehouse_id.partner_id.street or '',
                                               picking.picking_type_id.warehouse_id.partner_id.street2 or ''),
            'LabelImageFormat': 'PDF',
            'is_dutiable': carrier.dhl_dutiable,
            'currency_name': picking.sale_id.currency_id.name or picking.company_id.currency_id.name,
            'total_value': str(sum([line.product_id.lst_price * int(line.product_uom_qty) for line in picking.move_lines]))
        }
        request_text = self._create_shipping_xml(param)

        root = self._send_request(request_text)
        if root.tag == '{http://www.dhl.com}ShipmentResponse':
            label_image = root.findall('LabelImage')
            self.label = label_image[0].findall('OutputImage')[0].text
            dict_response['tracking_number'] = root.findtext('AirwayBillNumber')

        # Warning sometimes the ShipmentRequest returns a shipping rate, not everytime.
        # After discussing by mail with the DHL Help Desk, they said that the correct rate
        # is given by the DCTRequest GetQuote.

        param_final_rating = {
            'carrier': carrier,
            'shipper_partner': picking.picking_type_id.warehouse_id.partner_id,
            'Date': time.strftime('%Y-%m-%d'),
            'ReadyTime': time.strftime('PT%HH%MM'),
            'recipient_partner': picking.partner_id,
            'currency_name': picking.sale_id.currency_id.name or picking.company_id.currency_id.name,
            'total_value': str(sum([line.product_id.lst_price * int(line.product_uom_qty) for line in picking.move_lines])),
            'is_dutiable': carrier.dhl_dutiable,
            'package_ids': picking.package_ids,
            'total_weight': picking.weight_bulk,
        }
        request_text = self._create_rate_xml(param_final_rating)
        root = self._send_request(request_text)

        if root.tag == '{http://www.dhl.com}DCTResponse':
            products = root.findall('GetQuoteResponse/BkgDetails/QtdShp')
            found = False
            for product in products:
                if product.findtext('GlobalProductCode') == carrier.dhl_product_code:
                    dict_response['price'] = product.findall('ShippingCharge')[0].text
                    dict_response['currency'] = product.findall('CurrencyCode')[0].text
                    found = True
            if not found:
                raise UserError(_("No service available for the selected product"))

        return dict_response

    def save_label(self):
        label_binary_data = binascii.a2b_base64(self.label)
        return label_binary_data

    def send_cancelling(self, picking, carrier):
        dict_response = {'tracking_number': 0.0, 'price': 0.0, 'currency': False}
        return dict_response

    def _send_request(self, request_xml):
        try:
            req = Request(url=self.url,
                          data=request_xml,
                          headers={'Content-Type': 'application/xml'})
            response_text = urlopen(req).read()
        except URLError:
            raise UserError("DHL Server not found. Check your connectivity.")
        root = etree.fromstring(response_text)
        error = root.findall('.//ConditionData')
        if error:
            raise UserError(_(error[0].text))
        else:
            return root

    def _create_rate_xml(self, param):
        etree.register_namespace("req", "http://www.dhl.com")
        root = etree.Element("{http://www.dhl.com}DCTRequest")
        get_quote_node = etree.SubElement(root, "GetQuote")
        service_header_node = etree.SubElement(get_quote_node, "Request")
        service_header_node = etree.SubElement(service_header_node, "ServiceHeader")
        etree.SubElement(service_header_node, "SiteID").text = param["carrier"].dhl_SiteID
        etree.SubElement(service_header_node, "Password").text = param["carrier"].dhl_password

        from_node = etree.SubElement(get_quote_node, "From")
        etree.SubElement(from_node, "CountryCode").text = param["shipper_partner"].country_id.code
        etree.SubElement(from_node, "Postalcode").text = param["shipper_partner"].zip
        etree.SubElement(from_node, "City").text = param["shipper_partner"].city

        bkg_details_node = etree.SubElement(get_quote_node, "BkgDetails")
        etree.SubElement(bkg_details_node, "PaymentCountryCode").text = param["shipper_partner"].country_id.code
        etree.SubElement(bkg_details_node, "Date").text = param["Date"]
        etree.SubElement(bkg_details_node, "ReadyTime").text = param["ReadyTime"]
        etree.SubElement(bkg_details_node, "DimensionUnit").text = param["carrier"].dhl_package_dimension_unit
        etree.SubElement(bkg_details_node, "WeightUnit").text = param["carrier"].dhl_package_weight_unit
        pieces_node = etree.SubElement(bkg_details_node, "Pieces")
        if param["package_ids"]:
            for index, package in enumerate(param["package_ids"], start=1):
                piece_node = etree.SubElement(pieces_node, "Piece")
                etree.SubElement(piece_node, "PieceID").text = str(index)
                etree.SubElement(piece_node, "PackageTypeCode").text = param["carrier"].dhl_package_type
                etree.SubElement(piece_node, "Height").text = str(param["carrier"].dhl_package_height)
                etree.SubElement(piece_node, "Depth").text = str(param["carrier"].dhl_package_depth)
                etree.SubElement(piece_node, "Width").text = str(param["carrier"].dhl_package_width)
                etree.SubElement(piece_node, "Weight").text = str(package.weight)
        else:
            piece_node = etree.SubElement(pieces_node, "Piece")
            etree.SubElement(piece_node, "PieceID").text = str(1)
            etree.SubElement(piece_node, "PackageTypeCode").text = param["carrier"].dhl_package_type
            etree.SubElement(piece_node, "Height").text = str(param["carrier"].dhl_package_height)
            etree.SubElement(piece_node, "Depth").text = str(param["carrier"].dhl_package_depth)
            etree.SubElement(piece_node, "Width").text = str(param["carrier"].dhl_package_width)
            etree.SubElement(piece_node, "Weight").text = str(param["total_weight"])

        etree.SubElement(bkg_details_node, "PaymentAccountNumber").text = param["carrier"].dhl_account_number
        if param["is_dutiable"]:
            etree.SubElement(bkg_details_node, "IsDutiable").text = "Y"
        else:
            etree.SubElement(bkg_details_node, "IsDutiable").text = "N"
        to_node = etree.SubElement(get_quote_node, "To")
        etree.SubElement(to_node, "CountryCode").text = param["recipient_partner"].country_id.code
        etree.SubElement(to_node, "Postalcode").text = param["recipient_partner"].zip
        etree.SubElement(to_node, "City").text = param["recipient_partner"].city

        if param["is_dutiable"]:
            dutiable_node = etree.SubElement(get_quote_node, "Dutiable")
            etree.SubElement(dutiable_node, "DeclaredCurrency").text = param["currency_name"]
            etree.SubElement(dutiable_node, "DeclaredValue").text = str(round(param["total_value"], 2))
        return etree.tostring(root)

    def _create_shipping_xml(self, param):
        etree.register_namespace("req", "http://www.dhl.com")
        root = etree.Element("{http://www.dhl.com}ShipmentRequest")
        root.attrib['schemaVersion'] = "1.0"
        root.attrib['xsi:schemaLocation'] = "http://www.dhl.com ship-val-global-req.xsd"
        root.attrib['xmlns:xsi'] = "http://www.w3.org/2001/XMLSchema-instance"

        request_node = etree.SubElement(root, "Request")
        request_node = etree.SubElement(request_node, "ServiceHeader")
        etree.SubElement(request_node, "MessageTime").text = param["MessageTime"]
        etree.SubElement(request_node, "MessageReference").text = param["MessageReference"]
        etree.SubElement(request_node, "SiteID").text = param["carrier"].dhl_SiteID
        etree.SubElement(request_node, "Password").text = param["carrier"].dhl_password

        etree.SubElement(root, "RegionCode").text = param["RegionCode"]
        etree.SubElement(root, "RequestedPickupTime").text = "Y"

        etree.SubElement(root, "LanguageCode").text = param["lang"]
        etree.SubElement(root, "PiecesEnabled").text = param["PiecesEnabled"]

        billing_node = etree.SubElement(root, "Billing")
        etree.SubElement(billing_node, "ShipperAccountNumber").text = param['carrier'].dhl_account_number
        etree.SubElement(billing_node, "ShippingPaymentType").text = param['ShippingPaymentType']
        if param["is_dutiable"]:
            etree.SubElement(billing_node, "DutyPaymentType").text = "S"

        consignee_node = etree.SubElement(root, "Consignee")
        etree.SubElement(consignee_node, "CompanyName").text = self._remove_accents(param["recipient_partner"].name)
        etree.SubElement(consignee_node, "AddressLine").text = self._remove_accents(param["recipient_streetLines"])
        etree.SubElement(consignee_node, "City").text = self._remove_accents(param["recipient_partner"].city)

        if param["recipient_partner"].state_id:
            etree.SubElement(consignee_node, "Division").text = param["recipient_partner"].state_id.name
            etree.SubElement(consignee_node, "DivisionCode").text = param["recipient_partner"].state_id.name
        etree.SubElement(consignee_node, "PostalCode").text = param["recipient_partner"].zip
        etree.SubElement(consignee_node, "CountryCode").text = param["recipient_partner"].country_id.code
        etree.SubElement(consignee_node, "CountryName").text = param["recipient_partner"].country_id.name
        contact_node = etree.SubElement(consignee_node, "Contact")
        etree.SubElement(contact_node, "PersonName").text = param["recipient_partner"].name
        etree.SubElement(contact_node, "PhoneNumber").text = param["recipient_partner"].phone
        etree.SubElement(contact_node, "Email").text = param["recipient_partner"].email
        if param["is_dutiable"]:
            dutiable_node = etree.SubElement(root, "Dutiable")
            etree.SubElement(dutiable_node, "DeclaredValue").text = param["total_value"]
            etree.SubElement(dutiable_node, "DeclaredCurrency").text = param["currency_name"]

        shipment_details_node = etree.SubElement(root, "ShipmentDetails")
        etree.SubElement(shipment_details_node, "NumberOfPieces").text = str(param["NumberOfPieces"])
        pieces_node = etree.SubElement(shipment_details_node, "Pieces")
        if param["package_ids"]:
            # Multi-package
            for package in param["package_ids"]:
                piece_node = etree.SubElement(pieces_node, "Piece")
                etree.SubElement(piece_node, "PieceID").text = str(package.name)   # need to be removed
                etree.SubElement(piece_node, "Width").text = str(param["carrier"].dhl_package_width)
                etree.SubElement(piece_node, "Height").text = str(param["carrier"].dhl_package_height)
                etree.SubElement(piece_node, "Depth").text = str(param["carrier"].dhl_package_depth)
                etree.SubElement(piece_node, "PieceContents").text = str(package.name)
        if param["weight_bulk"]:
            # Monopackage
            piece_node = etree.SubElement(pieces_node, "Piece")
            etree.SubElement(piece_node, "PieceID").text = str(1)   # need to be removed
            etree.SubElement(piece_node, "Width").text = str(param["carrier"].dhl_package_width)
            etree.SubElement(piece_node, "Height").text = str(param["carrier"].dhl_package_height)
            etree.SubElement(piece_node, "Depth").text = str(param["carrier"].dhl_package_depth)
        etree.SubElement(shipment_details_node, "Weight").text = str(param["total_weight"])
        etree.SubElement(shipment_details_node, "WeightUnit").text = param["weight_unit"]
        etree.SubElement(shipment_details_node, "GlobalProductCode").text = param["GlobalProductCode"]
        etree.SubElement(shipment_details_node, "LocalProductCode").text = param["GlobalProductCode"]
        etree.SubElement(shipment_details_node, "Date").text = param["Date"]
        etree.SubElement(shipment_details_node, "Contents").text = "MY DESCRIPTION"
        etree.SubElement(shipment_details_node, "DimensionUnit").text = param["dimension_unit"]
        etree.SubElement(shipment_details_node, "CurrencyCode").text = param["currency_name"]

        shipper_node = etree.SubElement(root, "Shipper")
        etree.SubElement(shipper_node, "ShipperID").text = param["carrier"].dhl_account_number
        etree.SubElement(shipper_node, "CompanyName").text = self._remove_accents(param["shipper_company"].name)
        etree.SubElement(shipper_node, "AddressLine").text = self._remove_accents(param["shipper_streetLines"])
        etree.SubElement(shipper_node, "City").text = self._remove_accents(param["shipper_partner"].city)
        etree.SubElement(shipper_node, "PostalCode").text = self._remove_accents(param["shipper_partner"].zip)
        etree.SubElement(shipper_node, "CountryCode").text = param["shipper_partner"].country_id.code
        etree.SubElement(shipper_node, "CountryName").text = param["shipper_partner"].country_id.name

        contact_node = etree.SubElement(shipper_node, "Contact")
        etree.SubElement(contact_node, "PersonName").text = self._remove_accents(param["shipper_partner"].name)
        etree.SubElement(contact_node, "PhoneNumber").text = param["shipper_partner"].phone
        etree.SubElement(root, "LabelImageFormat").text = param["LabelImageFormat"]

        return etree.tostring(root)

    def check_required_value(self, carrier, recipient, shipper, order=False, picking=False):
        recipient_required_field = ['city', 'zip', 'country_id']
        if not carrier.dhl_SiteID:
            raise ValidationError(_("DHL Site ID is missing, please modify your delivery method settings."))
        if not carrier.dhl_password:
            raise ValidationError(_("DHL password is missing, please modify your delivery method settings."))
        if not carrier.dhl_account_number:
            raise ValidationError(_("DHL account number is missing, please modify your delivery method settings."))

        if not recipient.street and not recipient.street2:
            recipient_required_field.append('street')
        res = [field for field in recipient_required_field if not recipient[field]]
        if res:
            raise ValidationError(_("The address of the custommer is missing or wrong (Missing field(s) :\n %s)") % ", ".join(res).replace("_id", ""))

        shipper_required_field = ['city', 'zip', 'phone', 'country_id']
        if not shipper.street and not shipper.street2:
            shipper_required_field.append('street')

        res = [field for field in shipper_required_field if not shipper[field]]
        if res:
            raise ValidationError(_("The address of your company warehouse is missing or wrong (Missing field(s) :\n %s)") % ", ".join(res).replace("_id", ""))

        if order:
            if not order.order_line:
                raise ValidationError(_("Please provide at least one item to ship."))
            for line in order.order_line.filtered(lambda line: not line.product_id.weight and not line.is_delivery):
                raise ValidationError(_('The estimated price cannot be computed because the weight of your product is missing.'))
        return True

    def _remove_accents(self, input_str):
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        only_ascii = nfkd_form.encode('ASCII', 'ignore')
        return only_ascii
