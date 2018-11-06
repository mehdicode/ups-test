# Copyright (c) 2018 Emipro Technologies Pvt Ltd (www.emiprotechnologies.com). All rights reserved.
from odoo import models, fields, api

class ProductProductEpt(models.Model):
    _inherit = "product.product"
    ups_goods_description=fields.Char(string="Description of Goods/Part No.", help="Product Description, It's value consider in international form provided by UPS. If not entered than name consider.",copy=False)
    ups_c_t_o=fields.Many2one('res.country',string="Product CTO",help="It describe Product made by this country of origin. Use for international request",copy=False)
