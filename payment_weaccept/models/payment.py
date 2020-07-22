# -*- coding: utf-8 -*-

import datetime
import logging
import json
import requests

from odoo import api, fields, models, _
from odoo.http import request
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class WeAcceptAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    weaccept_username = fields.Char(string='Username', required_if_provider='weaccept')
    weaccept_password = fields.Char(string='Password', required_if_provider='weaccept')
    weaccept_merchant_id = fields.Char(string='Merchant ID', required_if_provider='weaccept')
    weaccept_payment_integration_id = fields.Char(
        string='Payment Integration ID', required_if_provider='weaccept')
    weaccept_iframe_id = fields.Char(string='Iframe ID', required_if_provider='weaccept')
    provider = fields.Selection(selection_add=[('weaccept', 'WeAccept')])

    def weaccept_form_generate_values(self, values):
        weaccept_tx_values = dict(values)
        return weaccept_tx_values

    def weaccept_get_form_action_url(self):
        self.ensure_one()
        return '/weaccept/payment'

    def create_token_and_get_payment_url(self, order):
        token_url = "https://accept.paymobsolutions.com/api/auth/tokens"
        payload = {
            "username": self.weaccept_username,
            "password": self.weaccept_password,
            "expiration": "36000"
        }
        headers = {'content-type': 'application/json'}
        token_response = requests.post(token_url, data=json.dumps(payload), headers=headers)
        token = token_response.json().get('token')

        txn = self.env['payment.transaction'].sudo().search([
            ('sale_order_ids', 'in', [order.id]),
            ('state', '=', 'draft')], limit=1, order="id DESC")
        # txn = self.env['payment.transaction'].sudo().browse(request.session.get('sale_transaction_id'))

        # Check weaccept order number exist then first delete
        if txn.weaccept_order_no:
            delete_url = 'https://accept.paymobsolutions.com/api/ecommerce/orders/%s?token=%s' % (
                txn.weaccept_order_no, token)
            delete_response = requests.delete(delete_url, data=json.dumps({}), headers=headers)
            if delete_response.json().get('message') == 'deleted':
                txn.weaccept_order_no = None

        # weaccept order request create
        order_url = 'https://accept.paymobsolutions.com/api/ecommerce/orders?token=%s' % token
        order_payload = {
            'merchant_id': self.weaccept_merchant_id,
            'amount_cents': "%s" % (round(order.amount_total * 100)),
            'currency': order.currency_id.name,
            'merchant_order_id': order.name,
            "items": []
        }
        order_response = requests.post(order_url, data=json.dumps(order_payload), headers=headers)
        order_response_data = order_response.json()
        txn.weaccept_order_no = order_response_data.get('id')

        # weaccept payment token key create
        payment_url = 'https://accept.paymobsolutions.com/api/acceptance/payment_keys?token=%s' % token
        payment_key_payload = {
            'amount_cents': "%s" % (round(order.amount_total * 100)),
            'expiration': 36000,
            'order_id': txn.weaccept_order_no,
            'billing_data': {
                "first_name": order.partner_id.name,
                "last_name": order.partner_id.name,
                "email": order.partner_id.email,
                "apartment": "1",
                "building": "1",
                "floor": "1",
                "street": order.partner_id.street,
                "city": order.partner_id.city,
                "postal_code": order.partner_id.zip or "11865",
                "state": order.partner_id.state_id and order.partner_id.state_id.name or "Utah",
                "country": order.partner_id.country_id and order.partner_id.country_id.code or "CR",
                "phone_number": order.partner_id.phone,
                "shipping_method": "PKG",
            },
            'currency': order.currency_id.name,
            'integration_id': self.weaccept_payment_integration_id
        }
        payment_key_response = requests.post(
            payment_url, data=json.dumps(payment_key_payload), headers=headers)
        payment_key_response_data = payment_key_response.json()
        payment_token = payment_key_response_data.get('token')
        return 'https://accept.paymobsolutions.com/api/acceptance/iframes/%s?payment_token=%s' % (
            self.weaccept_iframe_id, payment_token)


class TransactionWeAccept(models.Model):
    _inherit = 'payment.transaction'

    weaccept_order_no = fields.Char(string='Order Number', help='WeAccept Order Number')
    weaccept_sub_type = fields.Char(string='Sub Type', help='WeAccept Sub Type')
    weaccept_type = fields.Char(string='Type', help='WeAccept Type')
    weaccept_hmac = fields.Char(string='hmac', help='WeAccept hmac')
    weaccept_currency = fields.Char(string='Currency', help='WeAccept Currency')
    weaccept_amount_cents = fields.Char(string='Amount Cents', help='WeAccept Amount Cents')
    weaccept_message = fields.Char(string='Status', help='WeAccept Message')

    @api.model
    def _weaccept_form_get_tx_from_data(self, data):
        orderid, amount_cents = data.get('merchant_order_id'), data.get('amount_cents')
        amount = '{:,.2f}'.format(int(amount_cents)/100.0)

        merchant_id, response_code = data.get('profile_id'), data.get('txn_response_code')
        if not orderid or not amount or not merchant_id or not response_code:
            error_msg = _(
                'WeAccept: Received data with missing orderid (%s) or amount (%s) or merchantcode (%s)'
            ) % (orderid, amount, merchant_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        tx = self.search([('reference', '=', orderid)])
        if not tx:
            order_id = self.env['sale.order'].search([('name', '=', orderid)]).id
            tx = self.search([('sale_order_ids', 'in', [order_id])], order="id DESC", limit=1)

        if not tx or len(tx) > 1:
            error_msg = _('WeAccept: Received data for Orderid %s') % (orderid)
            if not tx:
                error_msg += _('No order found.')
            else:
                error_msg += _('Multiple order found.')
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        if response_code == 'APPROVED' or response_code == '0':
            _logger.info('WeAccept: Payment revalidated Successfully.')
            tx.write({
                'weaccept_order_no': data.get('order'),
                'weaccept_sub_type': data.get('source_data.sub_type'),
                'weaccept_type': data.get('source_data.type'),
                'weaccept_hmac': data.get('hmac'),
                'weaccept_currency': data.get('currency'),
                'weaccept_amount_cents': data.get('amount_cents'),
                'weaccept_message': data.get('data.message'),
            })
        else:
            error_msg = _('WeAccept: Payment revalidated failed.')
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return tx

    def _weaccept_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        amount = '{:,.2f}'.format(int(data.get('amount_cents'))/100.0)

        if self.acquirer_reference and data.get('id') != self.acquirer_reference:
            invalid_parameters.append(('id', data.get('id'), self.acquirer_reference))
        if float_compare(float(amount), self.amount, 2) != 0:
            invalid_parameters.append(('Amount', amount, '%.2f' % self.amount))
        if data.get('currency') != self.currency_id.name:
            invalid_parameters.append(('currency', data.get('currency'), self.currency_id.name))
        return invalid_parameters

    def _weaccept_form_validate(self, data):
        if self.state == 'done':
            _logger.info('WeAccept: Already validated transaction (ref %s)', self.reference)
            return True

        _weaccept_success_tx_status = ['0','APPROVED']
        status = data.get('txn_response_code')
        if status in _weaccept_success_tx_status:
            self._set_transaction_done()
            self.write({
                'acquirer_reference': data.get('id')
            })
            return True
        else:
            if status == '1':
                error_msg = 'There was an error processing the transaction'
            elif status == '2':
                error_msg = 'Contact card issuing bank'
            elif status == '3':
                error_msg = 'Expired Card'
            elif status == '4':
                error_msg = 'Insufficient Funds'
            else:
                error_msg = 'Unknown error'
            error = 'WeAccept: feedback Error: %(error_msg)s' % {
                'error_msg': error_msg,
            }
            _logger.info(error)
            self.write({
                'state_message': error,
            })
            self._set_transaction_cancel()
            return True
