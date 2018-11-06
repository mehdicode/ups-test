# Copyright (c) 2017 Emipro Technologies Pvt Ltd (www.emiprotechnologies.com). All rights reserved.
import binascii
from datetime import datetime
from math import ceil
import pytz
import time
from requests import request
from odoo import models, fields, api, _
from odoo.addons.ups_shipping_ept.ups_api.ups_request import UPS_API
from odoo.addons.ups_shipping_ept.ups_api.ups_response import Response

from odoo.exceptions import Warning, ValidationError, UserError
import xml.etree.ElementTree as etree
import logging
_logger = logging.getLogger(__name__)

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[("ups_ept", "UPS")])
    ups_service_type = fields.Selection([('01', '01-Next Day Air'),
                                         ('02', '02-2nd Day Air'),
                                         ('03', '03-Ground'),
                                         ('12', '12-3 Day Select'),
                                         ('13', '13-Next Day Air Saver'),
                                         ('14', '14-UPS Next Day Air Early'),
                                         ('59', '59-2nd Day Air A.M.'),
                                         ('07', '07-Worldwide Express'),
                                         ('08', '08-Worldwide Expedited'),
                                         ('11', '11-Standard'),
                                         ('54', '54-Worldwide Express Plus'),
                                         ('65', '65-Saver'),
                                         ('96', '96-UPS Worldwide Express Freight')], string="Service Type",
                                        help="Shipping Services those are accepted by UPS")

    # note:-Ounce set when usps provide the ounces, First of all check ounce wil be support or not.
    ups_weight_uom = fields.Selection([('LBS', 'LBS-Pounds'),
                                       ('KGS', 'KGS-Kilograms'),
                                       ('OZS', 'OZS-Ounces')], string="Weight UOM", help="Weight UOM of the Shipment")

    ups_default_product_packaging_id = fields.Many2one('product.packaging', string="Default Package Type")

    # ups_dimension_measurement=fields.Selection([('IN', 'Inches'),('CM', 'Centremetres')], string="Dimension Unit",help="Dimension Unit of the Shipment")

    ups_lable_print_methods = fields.Selection([('GIF', 'GIF'),
                                                ('EPL', 'EPL2'),
                                                ('ZPL', 'ZPL'),
                                                ('SPL', 'SPL'),
                                                ('STAR', 'STARPL')], string="Label File Type",
                                               help="Specifies the type of lable formate.", default="GIF")

    @api.multi
    def ups_ept_rate_shipment(self, order):
        """ Get the Rate of particular shipping service for UPS
            @param orders : recordset of sale order object
            @return: dict of default value of rate
            @author: Emipro Technologies Pvt Ltd
        """
        # check the address validation
        self.check_required_value_to_ship(order)

        # check the product weight is appropriate to maximum weight.
        shipment_weight = self.ups_default_product_packaging_id.max_weight
        self.check_max_weight(order, shipment_weight)

        shipper_address = order.warehouse_id.partner_id
        recipient_address = order.partner_shipping_id

        # Address validation Request
        if self.shipping_instance_id and self.shipping_instance_id.check_recipient_address:
            self.check_recipient_address(recipient_address)

        # convet weight in to the delivery method's weight UOM
        total_weight = self.convert_weight(order.company_id and order.company_id.weight_unit_of_measurement_id, self.weight_uom_id,
                                        sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line if not line.is_delivery]))

        declared_value = round(order.amount_untaxed, 2)
        declared_currency = order.currency_id.name

        shipping_dict = self.ups_get_shipping_rate(shipper_address, recipient_address, total_weight,
                                                   picking_bulk_weight=False, packages=False,
                                                   declared_value=declared_value, declared_currency=declared_currency,
                                                   company_id=order.company_id)
        if shipping_dict.get('error_message',False):
            return {'success': False, 'price': 0.0, 'error_message': shipping_dict['error_message'],
                    'warning_message': False}

        currency_code = shipping_dict.get('CurrencyCode')
        shipping_charge = shipping_dict.get('ShippingCharge')
        rate_currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        price = rate_currency.compute(float(shipping_charge), order.currency_id)

        return {'success': True, 'price': float(price), 'error_message': False, 'warning_message': False}

    @api.multi
    def ups_get_shipping_rate(self, shipper_address, recipient_address, total_weight, picking_bulk_weight,
                              packages=False, declared_value=False, declared_currency=False, company_id=False):
        """ Retrive shipping Rate using this services from the UPS
            @param: Address Info, Weight info
            @return: request parameter 
            @author: Emipro Technologies Pvt Ltd
        """
        res = {}
        # built request data
        api = self.shipping_instance_id.get_ups_api_object(self.prod_environment, "Rate",
                                                           self.shipping_instance_id.ups_userid,
                                                           self.shipping_instance_id.ups_password,
                                                           self.shipping_instance_id.access_license_number)
        service_root = etree.Element("RatingServiceSelectionRequest")

        request = etree.SubElement(service_root, "Request")
        etree.SubElement(request, "RequestAction").text = "Rate"
        etree.SubElement(request, "RequestOption").text = "Rate"

        shipment = etree.SubElement(service_root, "Shipment")
        etree.SubElement(shipment, "Description").text = "Rate Description"

        shipper = etree.SubElement(shipment, "Shipper")
        from_address = etree.SubElement(shipper, "Address")
        etree.SubElement(from_address, "PostalCode").text = "%s" % (shipper_address.zip)
        etree.SubElement(from_address, "CountryCode").text = "%s" % (
                shipper_address.country_id and shipper_address.country_id.code)

        ship_to = etree.SubElement(shipment, "ShipTo")
        ship_to_address = etree.SubElement(ship_to, "Address")
        etree.SubElement(ship_to_address, "PostalCode").text = "%s" % (recipient_address.zip)
        etree.SubElement(ship_to_address, "CountryCode").text = "%s" % (
                recipient_address.country_id and recipient_address.country_id.code)

        service_discription = etree.SubElement(shipment, "Service")
        etree.SubElement(service_discription, "Code").text = "%s" % (self.ups_service_type)

        if self.ups_service_type == '96':
            # When Calling the Rate API we pass numofpiece 1 manually when calling rate API Because When Used the 96 service must pass some piece or in sale order we have not any packages so pass manually one.
            etree.SubElement(shipment, "NumOfPieces").text = str("1")
        if self.ups_service_type in ['07', '08', '11', '54', '65', '96']:
            shipment_weight = etree.SubElement(shipment, "ShipmentTotalWeight")
            package_uom = etree.SubElement(shipment_weight, "UnitOfMeasurement")
            etree.SubElement(package_uom, "Code").text = "%s" % (self.ups_weight_uom)
            etree.SubElement(shipment_weight, "Code").text = "%s" % (total_weight)

        if packages:
            for package in packages:
                product_weight = self.convert_weight(company_id and company_id.weight_unit_of_measurement_id,
                                                     self.weight_uom_id, package.shipping_weight)

                package_info = etree.SubElement(shipment, "Package")
                package_type = etree.SubElement(package_info, "PackagingType")

                etree.SubElement(package_type, "Code").text = "%s" % (
                        self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.shipper_package_code)
                package_weight = etree.SubElement(package_info, "PackageWeight")

                # dimension is condition parameter We use just in internation service
                if self.ups_service_type == '96':
                    package_dimention = etree.SubElement(package_info, "Dimensions")

                    etree.SubElement(package_dimention, "Length").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.length or "0")
                    etree.SubElement(package_dimention, "Width").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")
                    etree.SubElement(package_dimention, "Height").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")

                package_uom = etree.SubElement(package_weight, "UnitOfMeasurement")
                etree.SubElement(package_uom, "Code").text = "%s" % (self.ups_weight_uom)
                etree.SubElement(package_weight, "Weight").text = "%s" % (product_weight)
            if picking_bulk_weight:
                package_info = etree.SubElement(shipment, "Package")
                package_type = etree.SubElement(package_info, "PackagingType")

                etree.SubElement(package_type, "Code").text = "%s" % (
                self.ups_default_product_packaging_id.shipper_package_code)
                package_weight = etree.SubElement(package_info, "PackageWeight")

                # dimension is condition parameter We use just in internation service
                if self.ups_service_type == '96':
                    package_dimention = etree.SubElement(package_info, "Dimensions")

                    etree.SubElement(package_dimention, "Length").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.length or "0")
                    etree.SubElement(package_dimention, "Width").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")
                    etree.SubElement(package_dimention, "Height").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")

                package_uom = etree.SubElement(package_weight, "UnitOfMeasurement")
                etree.SubElement(package_uom, "Code").text = "%s" % (self.ups_weight_uom)
                etree.SubElement(package_weight, "Weight").text = "%s" % (picking_bulk_weight)
        else:
            max_weight = self.convert_weight(company_id and company_id.weight_unit_of_measurement_id,self.weight_uom_id,
                                             self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.max_weight)

            if max_weight and total_weight > max_weight:
                num_of_packages = int(ceil(total_weight / max_weight))

                total_package_weight = total_weight / num_of_packages
                while (num_of_packages > 0):
                    package_info = etree.SubElement(shipment, "Package")
                    package_type = etree.SubElement(package_info, "PackagingType")

                    etree.SubElement(package_type, "Code").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.shipper_package_code)
                    package_weight = etree.SubElement(package_info, "PackageWeight")

                    package_uom = etree.SubElement(package_weight, "UnitOfMeasurement")
                    etree.SubElement(package_uom, "Code").text = "%s" % (self.ups_weight_uom)
                    etree.SubElement(package_weight, "Weight").text = "%s" % (total_package_weight)
                    num_of_packages = num_of_packages - 1
            else:
                package_info = etree.SubElement(shipment, "Package")
                package_type = etree.SubElement(package_info, "PackagingType")
                etree.SubElement(package_type, "Code").text = "%s" % (
                        self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.shipper_package_code or "")
                package_weight = etree.SubElement(package_info, "PackageWeight")

                # dimension is condition parameter We use just in internation service
                if self.ups_service_type == '96':
                    package_dimention = etree.SubElement(package_info, "Dimensions")

                    etree.SubElement(package_dimention, "Length").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.length or "0")
                    etree.SubElement(package_dimention, "Width").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")
                    etree.SubElement(package_dimention, "Height").text = "%s" % (
                            self.ups_default_product_packaging_id and self.ups_default_product_packaging_id.width or "0")

                package_uom = etree.SubElement(package_weight, "UnitOfMeasurement")
                etree.SubElement(package_uom, "Code").text = "%s" % (self.ups_weight_uom)
                etree.SubElement(package_weight, "Weight").text = "%s" % (total_weight)
        try:
            api.execute('RatingServiceSelectionRequest', etree.tostring(service_root).decode('utf-8'))
            results = api.response.dict()
            _logger.info("Response Data  : %s" % (results))
        except Exception as e:
            res['error_message'] = e.message
            return res

        product_details = results.get('RatingServiceSelectionResponse', {}).get('RatedShipment', {})
        code = product_details.get('Service', {})
        service_code = code.get('Code')
        service_detail = product_details.get('TotalCharges', {})
        shipment_charge = service_detail.get('MonetaryValue', False)

        if service_code == self.ups_service_type:
            if shipment_charge:
                res.update({'ShippingCharge': shipment_charge or 0.0,
                            'CurrencyCode': service_detail.get('CurrencyCode', False)})
            else:
                res['error_message'] = (_("Shipping service is not available for this location."))
        else:
            res['error_message'] = (_("No shipping service available!"))
        return res

    @api.multi
    def check_recipient_address(self, recipient_address=False):
        """ Check Recipient Address when calling the request in UPS
            @param orders : To Address
            @return: If Address is validate then True otherwise it's give the error.
            @author: Jigar v Vagadiya on dated 27-Nov-2017
        """
        if recipient_address:
            api = self.shipping_instance_id.get_ups_api_object(self.prod_environment, "AV",
                                                               self.shipping_instance_id and self.shipping_instance_id.ups_userid,
                                                               self.shipping_instance_id and self.shipping_instance_id.ups_password,
                                                               self.shipping_instance_id and self.shipping_instance_id.access_license_number)
            service_root = etree.Element("AddressValidationRequest")

            request = etree.SubElement(service_root, "Request")
            etree.SubElement(request, "RequestAction").text = "AV"

            address = etree.SubElement(service_root, "Address")
            etree.SubElement(address, "City").text = "%s" % (recipient_address.city or "")
            etree.SubElement(address, "StateProvinceCode").text = "%s" % (
                    recipient_address.state_id and recipient_address.state_id.code or "")
            etree.SubElement(address, "PostalCode").text = "%s" % (recipient_address.zip or "")
            etree.SubElement(address, "CountryCode").text = "%s" % (
                    recipient_address.country_id and recipient_address.country_id.code or "")
            try:
                api.execute('AddressValidationRequest', etree.tostring(service_root).decode('utf-8'))
                results = api.response.dict()
                _logger.info("Response Data  : %s" % (results))
            except Exception as e:
                raise Warning("Address Validation Error :%s" % (e))
            response_status = results.get('AddressValidationResponse', False) and results.get(
                'AddressValidationResponse', False).get('Response', False) and \
                              results.get('AddressValidationResponse',False).get('Response',False).get('ResponseStatusCode')
            # response_status is success then status code is 1 otherwise 0.
            if response_status == '1':
                return True
            else:
                message = results.get('AddressValidationResponse', False) and results.get(
                    'AddressValidationResponse', False).get('Response', False) and results.get(
                    'AddressValidationResponse', False).get('Response', False).get('Error')
                raise Warning(message)

    @api.multi
    def ups_shipment_accept(self, shipment_degits):
        """ accept shipment and genrate the lable using this services from the UPS
            @param:
            @return: request parameter,shipment degits
            @author: Jigar v vagadiya
         """
        service_root = etree.Element("ShipmentAcceptRequest")

        request_node = etree.SubElement(service_root, "Request")
        etree.SubElement(request_node, "RequestAction").text = "ShipAccept"
        etree.SubElement(request_node, "RequestOption").text = "01"

        etree.SubElement(service_root, "ShipmentDigest").text = str(shipment_degits)
        if not self.prod_environment:
            url = 'https://wwwcie.ups.com/ups.app/xml/ShipAccept'
        else:
            url = 'https://onlinetools.ups.com/ups.app/xml/ShipAccept'
        try:
            xml = etree.tostring(service_root).decode('utf-8')
            base_data = "<AccessRequest xml:lang=\"en-US\"><AccessLicenseNumber>%s</AccessLicenseNumber><UserId>%s</UserId><Password>%s</Password></AccessRequest>" % (
                self.shipping_instance_id.access_license_number, self.shipping_instance_id.ups_userid,
                self.shipping_instance_id.ups_password)
            base_data += xml
            headers = {"Content-Type": "application/xml"}
            response_body = request(method='POST', url=url, data=base_data, headers=headers)
            result = {}
            if response_body.status_code == 200:
                api = Response(response_body)
                result = api.dict()
                return result
            else:
                error_code = "%s" % (response_body.status_code)
                error_message = response_body.reason
                message = error_code + " " + error_message
                raise Warning(
                    "ShipmentAcceptRequest Fail : %s \n More Information \n %s" % (message, response_body.text))
        except Exception as e:
            raise Warning(e)

    @api.model
    def ups_ept_send_shipping(self, pickings):
        """ Genrate the Lable of perticular shipping service for UPS
            @param
            @return: Lable(final data pass in to UPS)
            @author: Jigar v Vagadiya on dated 14-april-2017
        """
        response = []
        for picking in pickings:
            company_id = picking.company_id
            total_weight = self.convert_weight(picking.weight_uom_id,self.weight_uom_id, picking.shipping_weight)
            # total_bulk_weight = self.convert_weight(self.ups_weight_uom,picking.weight_bulk)
            total_bulk_weight = self.convert_weight(picking.weight_uom_id,self.weight_uom_id, picking.weight_bulk)
            total_value = sum([(line.product_uom_qty * line.product_id.list_price) for line in pickings.move_lines])

            picking_partner_id = picking.partner_id
            picking_carrier_id = picking.carrier_id
            picking_company_id = picking.picking_type_id.warehouse_id.partner_id

            # Address validation Request
            if self.shipping_instance_id and self.shipping_instance_id.check_recipient_address:
                self.check_recipient_address(picking_partner_id)

            api = self.shipping_instance_id.get_ups_api_object(self.prod_environment, "ShipConfirm",
                                                               self.shipping_instance_id.ups_userid,
                                                               self.shipping_instance_id.ups_password,
                                                               self.shipping_instance_id.access_license_number)

            shipment_request = etree.Element("ShipmentConfirmRequest")
            request_node = etree.SubElement(shipment_request, "Request")
            etree.SubElement(request_node, "RequestAction").text = "ShipConfirm"
            etree.SubElement(request_node, "RequestOption").text = "nonvalidate"

            shipment_node = etree.SubElement(shipment_request, "Shipment")

            etree.SubElement(shipment_node, "Description").text = str(picking.note or "")

            shipper_node = etree.SubElement(shipment_node, "Shipper")
            etree.SubElement(shipper_node, "Name").text = str(picking_company_id.name)
            if picking_partner_id.phone:
                etree.SubElement(shipper_node, "PhoneNumber").text = str(picking_company_id.phone)
            else:
                raise Warning(_("Customer phone number is require."))
            etree.SubElement(shipper_node, "AttentionName").text = str(picking_company_id.name)

            etree.SubElement(shipper_node, "ShipperNumber").text = str(self.shipping_instance_id and self.shipping_instance_id.ups_shipper_number)
            address = etree.SubElement(shipper_node, "Address")
            if picking_company_id.street:
                etree.SubElement(address, "AddressLine1").text = str(picking_company_id.street)
            else:
                raise Warning(_("AddressLine Is require in company address."))

            etree.SubElement(address, "City").text = "%s" % (picking_company_id.city or "")
            etree.SubElement(address, "StateProvinceCode").text = str(picking_company_id.state_id and picking_company_id.state_id.code or "")
            etree.SubElement(address, "PostalCode").text = str(picking_company_id.zip or "")
            etree.SubElement(address, "CountryCode").text = str(picking_company_id.country_id and picking_company_id.country_id.code or "")

            to_shipper_node = etree.SubElement(shipment_node, "ShipTo")
            etree.SubElement(to_shipper_node, "CompanyName").text = str(picking_partner_id.name)
            if picking_partner_id.phone:
                etree.SubElement(to_shipper_node, "PhoneNumber").text = str(picking_partner_id.phone)
            else:
                raise Warning(_("Recipient phone number is require."))
            etree.SubElement(to_shipper_node, "AttentionName").text = str(picking_partner_id.name)
            to_address = etree.SubElement(to_shipper_node, "Address")
            if picking_partner_id.street:
                etree.SubElement(to_address, "AddressLine1").text = str(picking_partner_id.street)
            else:
                raise Warning(_("AddressLine Is require in customer address."))
            etree.SubElement(to_address, "City").text = str(picking_partner_id.city or "")
            etree.SubElement(to_address, "StateProvinceCode").text = str(picking_partner_id.state_id and picking_partner_id.state_id.code or "")
            etree.SubElement(to_address, "PostalCode").text = str(picking_partner_id.zip or "")
            etree.SubElement(to_address, "CountryCode").text = str(
                picking_partner_id.country_id and picking_partner_id.country_id.code or "")

            payment_information = etree.SubElement(shipment_node, "PaymentInformation")
            prepaid_node = etree.SubElement(payment_information, "Prepaid")
            billshipper_node = etree.SubElement(prepaid_node, "BillShipper")
            etree.SubElement(billshipper_node, "AccountNumber").text = str(
                self.shipping_instance_id and self.shipping_instance_id.ups_shipper_number)

            service_node = etree.SubElement(shipment_node, "Service")
            etree.SubElement(service_node, "Code").text = str(self.ups_service_type)
            etree.SubElement(shipment_node, "NumOfPiecesInShipment").text = str(len(picking.package_ids) if not total_bulk_weight else (len(picking.package_ids) + 1) or "1")

            for package in picking.package_ids:
                product_weight = self.convert_weight(picking.weight_uom_id,self.weight_uom_id, package.shipping_weight)
                shipping_box = package.packaging_id or self.ups_default_product_packaging_id
                package_node = etree.SubElement(shipment_node, "Package")
                package_type = etree.SubElement(package_node, "PackagingType")
                etree.SubElement(package_type, "Code").text = "%s" % (
                self.ups_default_product_packaging_id.shipper_package_code)
                dimension = etree.SubElement(package_node, "Dimensions")
                dimension_uom = etree.SubElement(dimension, "UnitOfMeasurement")
                etree.SubElement(dimension_uom, "Code").text = str("IN" if self.ups_weight_uom != "KGS" else "CM")
                etree.SubElement(dimension, "Length").text = str(shipping_box.length)
                etree.SubElement(dimension, "Width").text = str(shipping_box.width)
                etree.SubElement(dimension, "Height").text = str(shipping_box.height)
                package_weight = etree.SubElement(package_node, "PackageWeight")
                etree.SubElement(package_weight, "UnitOfMeasurement").text = "%s" % (self.ups_weight_uom)
                etree.SubElement(package_weight, "Weight").text = str(product_weight)
            if total_bulk_weight:
                shipping_box = self.ups_default_product_packaging_id
                package_node = etree.SubElement(shipment_node, "Package")
                package_type = etree.SubElement(package_node, "PackagingType")
                etree.SubElement(package_type, "Code").text = str(
                    self.ups_default_product_packaging_id.shipper_package_code)
                dimension = etree.SubElement(package_node, "Dimensions")
                dimension_uom = etree.SubElement(dimension, "UnitOfMeasurement")
                etree.SubElement(dimension_uom, "Code").text = str("IN" if self.ups_weight_uom != "KGS" else "CM")
                etree.SubElement(dimension, "Length").text = str(shipping_box.length)
                etree.SubElement(dimension, "Width").text = str(shipping_box.width)
                etree.SubElement(dimension, "Height").text = str(shipping_box.height)
                package_weight = etree.SubElement(package_node, "PackageWeight")
                etree.SubElement(package_weight, "UnitOfMeasurement").text = str(self.ups_weight_uom)
                etree.SubElement(package_weight, "Weight").text = str(total_bulk_weight)

            label_specification = etree.SubElement(shipment_request, "LabelSpecification")
            lable_print_method = etree.SubElement(label_specification, "LabelPrintMethod")
            etree.SubElement(lable_print_method, "Code").text = str(self.ups_lable_print_methods)
            lable_image_formate = etree.SubElement(label_specification, "LabelImageFormat")
            etree.SubElement(lable_image_formate, "Code").text = str(self.ups_lable_print_methods)

            try:
                api.execute('ShipmentConfirmRequest', etree.tostring(shipment_request).decode('utf-8'), version=str(1.0))
                results = api.response.dict()
                _logger.info("ShipmentConfirm Response Data  : %s" % (results))
            except Exception as e:
                raise Warning(e)

            shippment_digets = results.get('ShipmentConfirmResponse', {}).get('ShipmentDigest', {})
            shippment_accept = {}
            if shippment_digets:
                shippment_accept = self.ups_shipment_accept(shippment_digets)

            # tracking_no=results.get('ShipmentConfirmResponse',{}).get('ShipmentIdentificationNumber',{})
            response_data = shippment_accept.get('ShipmentAcceptResponse', {}) and shippment_accept.get(
                'ShipmentAcceptResponse', {}).get('ShipmentResults', {}) and shippment_accept.get(
                'ShipmentAcceptResponse', {}).get('ShipmentResults', {}).get('PackageResults', {}) or False
            if not response_data:
                raise Warning("ShipmentAccept Request Fail : %s" % (shippment_accept))
            lable_image = shippment_accept.get('ShipmentAcceptResponse', {}).get('ShipmentResults', {}).get(
                'PackageResults', {})
            final_tracking_no = []
            if lable_image:
                if isinstance(lable_image, dict):
                    lable_image = [lable_image]
                for detail in lable_image:
                    tracking_no = detail.get('TrackingNumber')
                    binary_data = detail.get('LabelImage', {}).get('GraphicImage', False)
                    label_binary_data = binascii.a2b_base64(str(binary_data))
                    mesage_ept = (_("Shipment created!<br/> <b>Shipment Tracking Number : </b>%s") % (tracking_no))
                    picking.message_post(body=mesage_ept, attachments=[
                        ('UPS Label-%s.%s' % (tracking_no, self.ups_lable_print_methods), label_binary_data)])
                    final_tracking_no.append(tracking_no)

            shipper_address = picking.picking_type_id.warehouse_id.partner_id
            recipient_address = picking.partner_id
            declared_currency = picking.company_id.currency_id.name
            packages = picking.package_ids

            res = self.ups_get_shipping_rate(shipper_address, recipient_address, total_weight,
                                             picking_bulk_weight=total_bulk_weight, packages=packages,
                                             declared_value=total_value, \
                                             declared_currency=declared_currency, company_id=company_id)
            if res.get('error_message',False):
                return {'success': False, 'price': 0.0, 'error_message': res['error_message'], 'warning_message': False}

            # conver currency In Sale order Currency.
            currency_code = res.get('CurrencyCode')
            shipping_charge = res.get('ShippingCharge')
            rate_currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
            exact_price = rate_currency.compute(float(shipping_charge), picking.sale_id.currency_id)

            # logmessage = (_("Shipment created!<br/> <b>Shipment Tracking Number : </b>%s") % (tracking_no))
            #  picking.message_post(body=logmessage, attachments=[('UPS Label-%s.%s' % (tracking_no, self.ups_lable_print_methods), label_binary_data)])
            shipping_data = {
                'exact_price': exact_price,
                'tracking_number': ','.join(final_tracking_no)}
            response += [shipping_data]
        return response

    @api.multi
    def ups_ept_get_tracking_link(self, picking):
        """ Tracking the shipment from UPS
            @param:
            @return: Redirect UPS site and tracking the shippment.
            @author: Jigar v vagadiya
        """
        link = picking.carrier_id.shipping_instance_id.tracking_link or 'https://wwwapps.ups.com/WebTracking/track?trackNums='
        res = '%s %s' % (link, picking.carrier_tracking_ref)
        return res

    @api.multi
    def ups_ept_cancel_shipment(self, picking):
        tracking_no = picking.carrier_tracking_ref.split(',')
        if tracking_no:
            for shipment_number in tracking_no:
                api = self.shipping_instance_id.get_ups_api_object(self.prod_environment, "Void",
                                                                   self.shipping_instance_id.ups_userid,
                                                                   self.shipping_instance_id.ups_password,
                                                                   self.shipping_instance_id.access_license_number)
                service_root = etree.Element("VoidShipmentRequest")

                request = etree.SubElement(service_root, "Request")
                etree.SubElement(request, "RequestAction").text = "1"
                # tracking Number just testing purpose after Live Credential put the tracking_no[0]-jigar. As per TestRequest enter "1Z12345E0390817264".
                # shipment_number="1Z12345E0390817264"
                etree.SubElement(service_root, "ShipmentIdentificationNumber").text = str(shipment_number)

                try:
                    api.execute('VoidShipmentRequest', etree.tostring(service_root).decode('utf-8'), version=str(1.0))
                    results = api.response.dict()
                    _logger.info("VoidShipment Response Data  : %s" % (results))
                except Exception as e:
                    raise Warning(e)
        else:
            raise Warning(_("Shipment identification number not available!"))
        # Note:-After calling API Give the message shipment Is canceled.
        return True