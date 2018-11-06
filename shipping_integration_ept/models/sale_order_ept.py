from odoo import models, fields, api, _

class sale_order(models.Model):
    _inherit = "sale.order"

    estimated_arrival_date_ept = fields.Date(string='Estimated Arrival Date', help="Estimated Arrival Date describe the shipment will reach the destination location.",copy=False)
    declared_value_for_carriage=fields.Boolean(string="Declared Value For Carriage",help="Add Value Added Service Costs To Delivery Cost functionality True Than Add cost in UPS.",default=False)

    @api.onchange('carrier_id')
    def onchange_carrier_id(self):
        res=super(sale_order,self).onchange_carrier_id()
        self.declared_value_for_carriage=self.carrier_id.add_value_added_service_costs_to_delivery_cost
        return res