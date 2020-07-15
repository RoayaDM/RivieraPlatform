# -*- coding: utf-8 -*-
#############################################
#  Copyright (c) 2015-Present Forfens Tech.
#############################################

{
    'name': 'WeAccept Payment Acquirer',
    'version': '1.0',
    'summary': 'Payment Acquirer: WeAccept Implementation',
    'description': """Accept is a payment service provider and payment aggregator that empowers \
businesses to get paid wherever their customers are. Our services facilitate both online and \
offline payment channels with a set of tools to accept payments whether online, via mobile, on \
delivery or in store and whether paid by card, mobile wallet or cash.""",
    'category': 'Website',
    'license': 'OPL-1',
    'author': 'Forfens Tech',
    'sequence': 1,
    'images': ['static/description/main_screenshot.png'],
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_acquirer_views.xml',
        'views/payment_acquirer_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'support': 'forfens.com@gmail.com',
    'installable': True,
    'application': True,
    'price': 179,
    'currency': 'EUR',
    'live_test_url': '',
}
