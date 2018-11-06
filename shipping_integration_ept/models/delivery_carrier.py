# Copyright (c) 2017 Emipro Technologies Pvt Ltd (www.emiprotechnologies.com). All rights reserved.
from math import floor

from odoo import models, fields, api, _
from odoo.exceptions import Warning, ValidationError, UserError


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    shipping_instance_id = fields.Many2one('shipping.instance.ept', string="Shipping Instance")
    add_value_added_service_costs_to_delivery_cost=fields.Boolean(string="Add Value Added Service Costs To Delivery Cost",help="Add Value Added Service Costs To Delivery Cost functionality True Than Add cost in UPS.",default=False)
    extra_delivery_cost = fields.Float(string="Delivery Cost",help="This value consider when API rate calculate and add rate in order. Add this cost in actual rate.",default=0.0)
    percentage_of_value_added_cost_to_paid_by_customer=fields.Float("Percentage Of Value Added Cost To Paid By Customer(%)",help="Percentage Of Value Added Cost To Paid By Customer.",default=0)

    def _default_uom_in_delive(self):
        weight_uom_id = self.env.ref('product.product_uom_kgm', raise_if_not_found=False)
        if not weight_uom_id:
            uom_categ_id = self.env.ref('product.product_uom_categ_kgm').id
            weight_uom_id = self.env['product.uom'].search([('category_id', '=', uom_categ_id), ('factor', '=', 1)], limit=1)
        return weight_uom_id

    weight_uom_id = fields.Many2one('product.uom', string='Shipping UoM according to API UoM',help="Set equivalent unit of measurement according to provider unit of measurement. For Example, if the provider unit of measurement is KG then you have to select KG unit of measurement in the Shipping Unit of Measurement field.")


    def rate_shipment(self, order):
        ''' Compute the price of the order shipment

        :param order: record of sale.order
        :return dict: {'success': boolean,
                       'price': a float,
                       'error_message': a string containing an error message,
                       'warning_message': a string containing a warning message}
                       # TODO maybe the currency code?
        '''
        res=super(DeliveryCarrier,self).rate_shipment(order)
        if order.declared_value_for_carriage and self.add_value_added_service_costs_to_delivery_cost:
            if self.percentage_of_value_added_cost_to_paid_by_customer > 0:
            #     res['price'] = res['price'] + (self.extra_delivery_cost * self.percentage_of_value_added_cost_to_paid_by_customer / 100)
            # else:
                res['price'] = res['price'] * self.percentage_of_value_added_cost_to_paid_by_customer / 100
        return res

    @api.model
    def validating_address(self, partner, additional_fields=[]):
        """Check the method address is validate or not.
           @param: address.
           @return: If the data is validate then True otherwise genrate the error.
           @author: Jigar vagadiya and jigneshbhai.
        """
        missing_value = []
        mandatory_fields = ['country_id', 'city', 'zip']
        mandatory_fields.extend(additional_fields)
        if not partner.street and not partner.street2 :
            mandatory_fields.append('street')
        for field in mandatory_fields :
            if not getattr(partner, field) :
                missing_value.append(field)
        return missing_value

    @api.multi
    def check_required_value_to_ship(self, orders):
        """Check the require value like address(sender and receiver) and Check the product weight.
           @param: order detail
           @return: If the data is validate then True otherwise genrate the error.
           @author: Jigar vagadiya and jigneshbhai.
        """
        if not self.shipping_instance_id :
            return _("Shipping Instance is not found in selected delivery method.")
        for order in orders :
            if not order.order_line:
                return _("You have not any item to ship. Please provide item first")
            else :
                order_lines_without_weight = order.order_line.filtered(lambda line_item: not line_item.product_id.type in ['service', 'digital'] and not line_item.product_id.weight and not line_item.is_delivery)
                for order_line in order_lines_without_weight :
                    return _("Please define weight in product : \n %s") % order_line.product_id.name

            # validating customer address
            missing_value = self.validating_address(order.partner_shipping_id)
            if missing_value :
                fields = ", ".join(missing_value)
                return (_("Missing the values of the Customer address. \n Missing field(s) : %s  ") % fields)

            # validation shipper address
            missing_value = self.validating_address(order.warehouse_id.partner_id)
            if missing_value :
                fields = ", ".join(missing_value)
                return (_("Missing the values of the Warehouse address. \n Missing field(s) : %s  ") % fields)
        return False

    @api.multi
    def convert_weight(self,from_uom_unit ,to_uom_unit, weight):
        """Convert weight as per UOM.
           @param: Weight and UOM
           @return: Converted Weight return.
           @author: Jigar vagadiya and jigneshbhai.
        """
        return from_uom_unit._compute_quantity(weight, to_uom_unit)


    @api.multi
    def check_max_weight(self, order, shipment_weight):
        """Check the package weight is maximum for actual weight or not.
           @param: Package Weight and Shipment Weight
           @return: Check both weight if right then true otherwise genrate the error.
           @author: Jigar vagadiya and jigneshbhai.
        """
        for order_line in order.order_line:
            if order_line.product_id and order_line.product_id.weight > shipment_weight:
                return (_("Product weight is more than maximum weight."))
        return False

"""   
    @api.multi
    def manage_the_package_method(self,picking,max_weight):
        res=[]
        product_weight=[]
        package_weight=0.0
        picking_line=picking.move_lines
        box_available_weight=max_weight
        multipackage_weight=0.0
#         weight=0.0
#         for t in temp:
#             weight += t.product_id.weight 
#             if weight <= max_weight:
#                 weight=t.product_id.weight
                
        
        
        for order in picking_line:
            count=order.product_qty
            while(count > 0):
                product_weight.append(order.product_id.weight)
                count=count-1
        while(product_weight):  
            box_available_weight=max_weight
            package_weight=0.0
            
            for package_information in product_weight:
                if box_available_weight >= package_information:
                    if box_available_weight > 0:
                        box_available_weight=box_available_weight-package_information
                        package_weight += package_information
                        product_weight.remove(package_information.value) 
            res.append(package_weight)
            
            
            
            
            
            
#             if box_available_weight >= order.product_id.weight:
#                 if box_available_weight > 0:
#                     if order.product_id.weight > 0:
#                         box_available_weight=box_available_weight-order.product_id.weight
#                         package_weight = package_weight + order.product_id.weight
#                         
#             else:
#                 box_available_weight=max_weight
#                 box_available_weight=box_available_weight-order.product_id.weight
#                 multipackage_weight += order.product_id.weight
#             res=[package_weight,multipackage_weight]            
        return res"""
