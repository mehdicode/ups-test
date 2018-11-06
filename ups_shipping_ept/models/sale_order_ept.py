from odoo import models, fields, api, _

class sale_order(models.Model):
    _inherit = "sale.order"

    # estimated_arrival_date = fields.Date(string='Estimated Arrival Date', help="Estimated Arrival Date describe the shipment will reach the destination location.")
    signature_required = fields.Boolean(string="Signature Required",
                                        help="Use this signature required, UPS rate comes with signatured cost.",
                                        default=False)

    @api.onchange('carrier_id')
    def onchange_carrier_id(self):
        res = super(sale_order, self).onchange_carrier_id()
        self.signature_required = self.carrier_id.signature_required
        return res