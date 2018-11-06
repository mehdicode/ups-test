# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
     # App information
    'name': 'UPS Odoo Shipping Connector',
    'category': 'Website',
    'version': '11.0',
    'summary': 'Odoo UPS Shipping Integration helps to connect Odoo with UPS and manage your Shipping operations directly from Odoo',

    'license': 'OPL-1',

    # Dependencies
    'depends': ['shipping_integration_ept'],


    'data': ['data/delivery_ups.xml',
            'views/view_shipping_instance_ept.xml',
            'views/delivery_carrier_view.xml',
            ],
    # Odoo Store Specific
    
    'images': ['static/description/UPS.jpg'],
       
     # Author

    'author': 'Emipro Technologies Pvt. Ltd.',
    'website': 'http://www.emiprotechnologies.com',
    'maintainer': 'Emipro Technologies Pvt. Ltd.',
   
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'live_test_url':'http://www.emiprotechnologies.com/free-trial?app=ups-shipping-ept&version=11',
    'price': '149',
    'currency': 'EUR',

}
