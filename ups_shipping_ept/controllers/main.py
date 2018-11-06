# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery



class WebsiteSaleDeliveryUps(WebsiteSaleDelivery):

    @http.route(['/shop/update_carrier'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def update_eshop_carrier(self, **post):
        response = super(WebsiteSaleDeliveryUps, self).update_eshop_carrier(**post)
        order = request.website.sale_get_order()
        carrier_id = int(post['carrier_id'])
        currency = order.currency_id
        if order:
            order._check_carrier_quotation(force_carrier_id=carrier_id)
            return {'status': order.delivery_rating_success,
                    'error_message': order.delivery_message,
                    'carrier_id': carrier_id,
                    'new_amount_delivery': self._format_amount(order.delivery_price, currency),
                    'new_amount_untaxed': self._format_amount(order.amount_untaxed, currency),
                    'new_amount_tax': self._format_amount(order.amount_tax, currency),
                    'new_amount_total': self._format_amount(order.amount_total, currency),
                    'estimated_arrival_date':order.estimated_arrival_date
            }

    def _format_amount(self, amount, currency):
        fmt = "%.{0}f".format(currency.decimal_places)
        lang = request.env['res.lang']._lang_get(request.env.context.get('lang') or 'en_US')

        return lang.format(fmt, currency.round(amount), grouping=True, monetary=True)\
            .replace(r' ', u'\N{NO-BREAK SPACE}').replace(r'-', u'\u2011')