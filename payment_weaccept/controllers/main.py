# -*- coding: utf-8 -*-

import pprint
import logging
import werkzeug

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WeAcceptController(http.Controller):
    _return_url = '/weaccept/payment/response'

    @http.route(['/weaccept/payment'], type='http', auth="public", website=True, csrf=False)
    def weaccept_payment(self, **post):
        PaymentAcquirer = request.env['payment.acquirer'].browse(int(post.get('acquirer_id', 0)))
        order = request.website.sale_get_order()
        url = PaymentAcquirer.create_token_and_get_payment_url(order)
        return werkzeug.utils.redirect(url)

    @http.route('/weaccept/payment/response', type='http', auth="public", csrf=False)
    def weaccept_payment_form_feedback(self, **post):
        _logger.info('Getting Response from WeAccept: %s', pprint.pformat(post))
        request.env['payment.transaction'].sudo().form_feedback(post, 'weaccept')
        return werkzeug.utils.redirect('/payment/process')
