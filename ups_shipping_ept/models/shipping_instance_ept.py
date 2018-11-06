# Copyright (c) 2017 Emipro Technologies Pvt Ltd (www.emiprotechnologies.com). All rights reserved.
# -*- coding: utf-8 -*-
import time
from datetime import datetime
import xml.etree.ElementTree as etree
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, Warning, UserError
from odoo.addons.ups_shipping_ept.ups_api.ups_request import UPS_API


class ShippingInstanceEpt(models.Model):
    _inherit = "shipping.instance.ept"

    # Fields
    provider = fields.Selection(selection_add=[('ups_ept', 'UPS')])
    access_license_number = fields.Char("AccessLicenseNumber", copy=False,
                                        help="Holds the UPS Access Key associated with the UPS account.")
    ups_userid = fields.Char("UPS UserId", copy=False, help="Holds the username associated with your My UPS account.")
    ups_password = fields.Char("UPS Password", copy=False,
                               help="Holds the password associated with your My UPS account.")
    ups_shipper_number = fields.Char("UPS Shipper Number", copy=False,
                                     help="A shipper number is required when requesting to receive the negotiated rates. The shipper number is optional when requesting to receive the published rates.")

    check_recipient_address=fields.Boolean(copy=False,string="Check Recipient Address",help="Before the rate request and label request checking the recipient Address when value is TRUE.")

    # Constraints
    _sql_constraints = [('user_unique', 'unique(ups_userid)', 'User already exists.'), (
        'access_license_number_unique', 'unique(access_license_number)', 'AccessLicenseNumber already exists.')]

    @api.model
    def get_ups_api_object(self, environment, service_name, ups_user_id, ups_password, ups_access_license_number):
        api = UPS_API(environment, service_name, ups_user_id, ups_password, ups_access_license_number, timeout=500)
        return api

    @api.one
    def ups_ept_retrive_shipping_services(self, to_add):
        """ Retrive shipping services from the UPS
            @param:
            @return: list of dictionaries with shipping service
            @author: Jigar Vagadiya on dated 9-May-2017
        """

        # Prepared the Service list
        services_name = {'01': 'Next Day Air',
                         '02': '2nd Day Air',
                         '03': 'Ground',
                         '12': '3 Day Select',
                         '13': 'Next Day Air Saver',
                         '14': 'UPS Next Day Air Early',
                         '59': '2nd Day Air A.M.',
                         '07': 'Worldwide Express',
                         '08': 'Worldwide Expedited',
                         '11': 'Standard',
                         '54': 'Worldwide Express Plus',
                         '65': 'Saver',
                         '96': 'UPS Worldwide Express Freight'}

        shipping_services_obj = self.env['shipping.services.ept']
        services = shipping_services_obj.search([('shipping_instance_id', '=', self.id)])
        services.sudo().unlink()

        for company in self.company_ids:
            api = self.get_ups_api_object(True, "Rate", self.ups_userid, self.ups_password, self.access_license_number)
            service_root = etree.Element("RatingServiceSelectionRequest")

            request = etree.SubElement(service_root, "Request")
            etree.SubElement(request, "RequestAction").text = "Rate"
            etree.SubElement(request, "RequestOption").text = "Shop"

            shipment = etree.SubElement(service_root, "Shipment")
            etree.SubElement(shipment, "Description").text = "Rate Description"

            shipper = etree.SubElement(shipment, "Shipper")
            shipper_address = etree.SubElement(shipper, "Address")
            etree.SubElement(shipper_address, "PostalCode").text = company.zip
            etree.SubElement(shipper_address, "CountryCode").text = "%s"%(company.country_id and company.country_id.code or "")

            ship_to = etree.SubElement(shipment, "ShipTo")
            ship_to_address = etree.SubElement(ship_to, "Address")
            if to_add.use_toaddress_different:
                etree.SubElement(ship_to_address, "PostalCode").text = "%s"%(to_add.to_zip)
                etree.SubElement(ship_to_address, "CountryCode").text = "%s"%(to_add.to_country_id.code)
            else:
                etree.SubElement(ship_to_address, "PostalCode").text = company.zip
                etree.SubElement(ship_to_address, "CountryCode").text = "%s"%(company.country_id and company.country_id.code or "")

            package_info = etree.SubElement(shipment, "Package")
            package_type = etree.SubElement(package_info, "PackagingType")
            etree.SubElement(package_type, "Code").text = "02"
            package_weight = etree.SubElement(package_info, "PackageWeight")

            package_uom = etree.SubElement(package_weight, "UnitOfMeasurement")
            etree.SubElement(package_uom, "Code").text = "LBS"
            etree.SubElement(package_weight, "Weight").text = "50"

            try:
                api.execute('RatingServiceSelectionRequest', etree.tostring(service_root).decode('utf-8'))
                results = api.response.dict()
            except Exception as e:
                raise ValidationError(e)
            if results is not None:
                product_details = results.get('RatingServiceSelectionResponse', {}).get('RatedShipment', {})
                for pro_detail in product_details:
                    service_code_ept = pro_detail.get('Service', {}).get('Code')
                    service_name_ept = services_name.get(service_code_ept)
                    if service_code_ept:
                        service_id = shipping_services_obj.search(
                            [('service_code', '=', service_code_ept), ('shipping_instance_id', '=', self.id)])
                        if service_id:
                            if company.id not in service_id.company_ids.ids:
                                service_id.write({'company_ids': [(4, company.id)]})
                        else:
                            shipping_services_obj.create(
                                {'shipping_instance_id': self.id, 'service_code': service_code_ept,
                                 'service_name': service_name_ept, 'company_ids': [(4, company.id)]})
            else:
                raise ValidationError("There is no shipping service available!")
        return True

    @api.model
    def ups_ept_quick_add_shipping_services(self, service_type, service_name):
        """ Allow you to get the default shipping services value while creating quick 
            record from the Shipping Service for UPS
            @param service_type: Service type of UPS
            @return: dict of default value set
            @author: Jigar Vagadiya on dated 9-may-2017
        """
        return {'default_ups_service_type': service_type,
                'default_name': service_name}
