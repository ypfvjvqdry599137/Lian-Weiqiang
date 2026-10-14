import base64
import io
import json
import os
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import NameOID
from flask import Flask
import werkzeug

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

from client_routes import client_bp  # noqa: E402
from auth import issue_token  # noqa: E402
from extensions import db  # noqa: E402
from models import Category, ClientIdentity, OrderItem, OrderMaster, Product, ProductStock, User  # noqa: E402
import wechat_pay_support  # noqa: E402


def _build_test_certificate():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'CN'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Test WeChat Pay'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'test.wechatpay.local')
    ])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    return private_key, certificate


def _encrypt_resource(api_v3_key, payload, nonce='testnonce123456', associated_data='wechatpay'):
    aesgcm = AESGCM(api_v3_key.encode('utf-8'))
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ciphertext = aesgcm.encrypt(
        nonce.encode('utf-8'),
        plaintext,
        associated_data.encode('utf-8') if associated_data else None
    )
    return {
        'algorithm': 'AEAD_AES_256_GCM',
        'nonce': nonce,
        'associated_data': associated_data,
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8')
    }


def _sign_callback_body(private_key, timestamp, nonce, body_text):
    signature = private_key.sign(
        f'{timestamp}\n{nonce}\n{body_text}\n'.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


class FakeWeChatResponse:
    def __init__(self, body, headers):
        self.body = body.encode('utf-8')
        self.headers = headers

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class WeChatPayTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(prefix='wechat-pay-test-', suffix='.sqlite')
        os.close(fd)

        self.app = Flask(__name__)
        self.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path.replace("\\", "/")}',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'AUTH_SIGNING_KEY': 'payment-test-signing-key-with-32-characters',
            'WECHAT_MINI_PROGRAM_APPID': 'wx1234567890abcdef',
            'WECHAT_MINI_PROGRAM_SECRET': 'secret-secret-secret',
            'WECHAT_PAY_MCHID': '1900000001',
            'WECHAT_PAY_API_V3_KEY': '0123456789abcdef0123456789abcdef',
            'WECHAT_PAY_SERIAL_NO': 'MERCHANT_SERIAL_001',
            'WECHAT_PAY_NOTIFY_URL': 'https://example.com/client/wechat/pay/notify'
        })
        db.init_app(self.app)
        self.app.register_blueprint(client_bp)

        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.client = self.app.test_client()
        self.user = User(nickname='测试用户', phone='13800138000', openid='openid-test')
        db.session.add(self.user)
        db.session.flush()
        db.session.add(ClientIdentity(openid=self.user.openid, user_id=self.user.id))

        self.category = Category(name='测试分类', sort_order=1)
        db.session.add(self.category)
        db.session.flush()

        self.product = Product(
            name='测试商品',
            description='用于支付测试',
            category_id=self.category.id,
            price=Decimal('12.50'),
            image_url='https://example.com/product.png',
            unit='份',
            is_active=True,
            sales_count=0
        )
        db.session.add(self.product)
        db.session.flush()

        self.stock = ProductStock(
            product_id=self.product.id,
            total_stock=100,
            lock_stock=2,
            warning_stock=10
        )
        db.session.add(self.stock)
        db.session.flush()

        self.order = OrderMaster(
            order_sn='ORD202608150001',
            user_id=self.user.id,
            order_status=10,
            refund_status=0,
            total_amount=Decimal('25.00'),
            delivery_fee=Decimal('5.00'),
            final_amount=Decimal('30.00'),
            receiver_name='张三',
            receiver_phone='13800138000',
            receiver_address='北京市朝阳区测试路 1 号'
        )
        db.session.add(self.order)
        db.session.flush()

        self.order_item = OrderItem(
            order_sn=self.order.order_sn,
            product_id=self.product.id,
            product_name=self.product.name,
            product_image=self.product.image_url,
            price=self.product.price,
            quantity=2,
            unit=self.product.unit,
            processing_option=None,
            is_preorder=False
        )
        db.session.add(self.order_item)
        db.session.commit()
        self.auth_headers = {'Authorization': f'Bearer {issue_token("client", self.user.id, self.user.openid)}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def _reload_order(self):
        db.session.expire_all()
        return OrderMaster.query.filter_by(order_sn=self.order.order_sn).first()

    def _successful_trade(self, transaction_id='4200001234567890'):
        return {
            'appid': self.app.config['WECHAT_MINI_PROGRAM_APPID'],
            'mchid': self.app.config['WECHAT_PAY_MCHID'],
            'out_trade_no': self.order.order_sn,
            'transaction_id': transaction_id,
            'trade_type': 'JSAPI',
            'trade_state': 'SUCCESS',
            'amount': {'total': 3000, 'currency': 'CNY'},
            'payer': {'openid': self.user.openid}
        }

    def _unpaid_trade(self):
        return {
            'appid': self.app.config['WECHAT_MINI_PROGRAM_APPID'],
            'mchid': self.app.config['WECHAT_PAY_MCHID'],
            'out_trade_no': self.order.order_sn,
            'trade_state': 'NOTPAY'
        }

    def test_parse_wechatpay_notification_round_trip(self):
        private_key, certificate = _build_test_certificate()
        api_v3_key = self.app.config['WECHAT_PAY_API_V3_KEY']
        resource_payload = self._successful_trade()
        resource = _encrypt_resource(api_v3_key, resource_payload)
        notification = {
            'id': 'notify-001',
            'create_time': '2026-08-15T08:00:00+08:00',
            'event_type': 'TRANSACTION.SUCCESS',
            'resource': resource
        }
        body_text = json.dumps(notification, ensure_ascii=False, separators=(',', ':'))
        timestamp = str(int(time.time()))
        nonce = 'nonce-123456'
        signature = _sign_callback_body(private_key, timestamp, nonce, body_text)
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': nonce,
            'Wechatpay-Signature': signature,
            'Wechatpay-Serial': 'TEST_SERIAL_001'
        }

        with patch.object(wechat_pay_support, '_get_platform_certificate', return_value=certificate):
            parsed_notification, parsed_resource = wechat_pay_support.parse_wechatpay_notification(headers, body_text)

        self.assertEqual(parsed_notification['id'], 'notify-001')
        self.assertEqual(parsed_resource['out_trade_no'], self.order.order_sn)
        self.assertEqual(parsed_resource['transaction_id'], '4200001234567890')
        self.assertEqual(parsed_resource['trade_state'], 'SUCCESS')

    def test_wechat_pay_notify_is_idempotent(self):
        resource = self._successful_trade()
        notification = {'event_type': 'TRANSACTION.SUCCESS'}

        with patch.object(wechat_pay_support, 'parse_wechatpay_notification', return_value=(notification, resource)):
            first_response = self.client.post('/client/wechat/pay/notify', data='{}', content_type='application/json')
            second_response = self.client.post('/client/wechat/pay/notify', data='{}', content_type='application/json')

        self.assertEqual(first_response.status_code, 204)
        self.assertEqual(second_response.status_code, 204)

        order = self._reload_order()
        self.assertEqual(order.order_status, 20)
        self.assertEqual(order.transaction_id, '4200001234567890')
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(self.product.stock.total_stock, 98)
        self.assertEqual(self.product.stock.lock_stock, 0)
        self.assertEqual(self.product.sales_count, 2)

    def test_second_transaction_id_for_paid_order_is_rejected(self):
        notification = {'event_type': 'TRANSACTION.SUCCESS'}
        first = self._successful_trade('4200001234567890')
        second = self._successful_trade('4200009999999999')
        with patch.object(wechat_pay_support, 'parse_wechatpay_notification',
                          return_value=(notification, first)):
            self.assertEqual(self.client.post('/client/wechat/pay/notify', data='{}').status_code, 204)
        with patch.object(wechat_pay_support, 'parse_wechatpay_notification',
                          return_value=(notification, second)):
            response = self.client.post('/client/wechat/pay/notify', data='{}')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self._reload_order().transaction_id, '4200001234567890')
        self.assertEqual(self.product.stock.total_stock, 98)

    def test_paid_query_accepts_omitted_optional_currency(self):
        trade = self._successful_trade()
        del trade['amount']['currency']
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no', return_value=trade):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/pay', headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._reload_order().order_status, 20)

    def test_pay_order_finalizes_paid_order(self):
        with patch.object(
            wechat_pay_support,
            'query_jsapi_order_by_out_trade_no',
            return_value=self._successful_trade('4200000987654321')
        ):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/pay', headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['message'], '支付成功')
        self.assertEqual(payload['transaction_id'], '4200000987654321')

        order = self._reload_order()
        self.assertEqual(order.order_status, 20)
        self.assertEqual(order.transaction_id, '4200000987654321')
        self.assertEqual(self.product.stock.total_stock, 98)
        self.assertEqual(self.product.stock.lock_stock, 0)
        self.assertEqual(self.product.sales_count, 2)

    def test_success_trade_mismatches_never_mark_paid(self):
        mutations = [
            ('appid', 'wx-other'),
            ('mchid', 'other-merchant'),
            ('out_trade_no', 'OTHER-ORDER'),
            ('transaction_id', None),
            ('amount', {'total': 1, 'currency': 'CNY'}),
            ('payer', {'openid': 'other-user'})
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                trade = self._successful_trade()
                trade[field] = value
                with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no', return_value=trade):
                    response = self.client.post(f'/client/orders/{self.order.order_sn}/pay', headers=self.auth_headers)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(self._reload_order().order_status, 10)
                self.assertEqual(self.product.stock.lock_stock, 2)

    def test_callback_mismatch_returns_failure_without_mutating_order(self):
        for field, value in [('mchid', 'wrong'), ('amount', {'total': 1, 'currency': 'CNY'}),
                             ('payer', {'openid': 'wrong'})]:
            with self.subTest(field=field):
                resource = deepcopy(self._successful_trade())
                resource[field] = value
                notification = {'event_type': 'TRANSACTION.SUCCESS'}
                with patch.object(wechat_pay_support, 'parse_wechatpay_notification',
                                  return_value=(notification, resource)):
                    response = self.client.post('/client/wechat/pay/notify', data='{}')
                self.assertEqual(response.status_code, 500)
                self.assertEqual(self._reload_order().order_status, 10)

    def test_cancel_closes_unpaid_wechat_order_before_releasing_stock(self):
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no',
                          return_value=self._unpaid_trade()), \
             patch.object(wechat_pay_support, 'close_jsapi_order_by_out_trade_no') as close:
            response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        close.assert_called_once_with(self.order.order_sn)
        self.assertEqual(self._reload_order().order_status, 60)
        self.assertEqual(self.product.stock.total_stock, 100)
        self.assertEqual(self.product.stock.lock_stock, 0)

    def test_cancel_keeps_order_when_close_fails(self):
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no',
                          return_value=self._unpaid_trade()), \
             patch.object(wechat_pay_support, 'close_jsapi_order_by_out_trade_no',
                          side_effect=wechat_pay_support.WeChatPayError('关单失败')):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self._reload_order().order_status, 10)
        self.assertEqual(self.product.stock.lock_stock, 2)

    def test_cancel_paid_wechat_order_updates_local_payment_instead(self):
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no',
                          return_value=self._successful_trade()):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self._reload_order().order_status, 20)
        self.assertEqual(self.product.stock.total_stock, 98)

    def test_cancel_when_wechat_order_does_not_exist(self):
        missing = wechat_pay_support.WeChatPayApiError('不存在', 'ORDER_NOT_EXIST', 404)
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no', side_effect=missing):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._reload_order().order_status, 60)

    def test_cancel_does_not_release_stock_while_wechat_is_paying(self):
        trade = self._unpaid_trade()
        trade['trade_state'] = 'USERPAYING'
        with patch.object(wechat_pay_support, 'query_jsapi_order_by_out_trade_no', return_value=trade), \
             patch.object(wechat_pay_support, 'close_jsapi_order_by_out_trade_no') as close:
            response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)

        self.assertEqual(response.status_code, 409)
        close.assert_not_called()
        self.assertEqual(self._reload_order().order_status, 10)
        self.assertEqual(self.product.stock.lock_stock, 2)

    def test_paid_callback_for_cancelled_order_is_not_silently_accepted(self):
        self.order.order_status = 60
        db.session.commit()
        resource = self._successful_trade()
        with patch.object(wechat_pay_support, 'parse_wechatpay_notification',
                          return_value=({'event_type': 'TRANSACTION.SUCCESS'}, resource)):
            response = self.client.post('/client/wechat/pay/notify', data='{}')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self._reload_order().order_status, 60)

    def test_duplicate_callback_after_dispatch_does_not_change_stock(self):
        self.order.order_status = 30
        self.order.transaction_id = '4200001234567890'
        self.order.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.product.stock.total_stock = 98
        self.product.stock.lock_stock = 0
        self.product.sales_count = 2
        db.session.commit()
        resource = self._successful_trade()
        with patch.object(wechat_pay_support, 'parse_wechatpay_notification',
                          return_value=({'event_type': 'TRANSACTION.SUCCESS'}, resource)):
            response = self.client.post('/client/wechat/pay/notify', data='{}')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self._reload_order().order_status, 30)
        self.assertEqual(self.product.stock.total_stock, 98)
        self.assertEqual(self.product.sales_count, 2)

    def test_expired_wechat_signature_is_rejected(self):
        with self.assertRaises(wechat_pay_support.WeChatPayError):
            wechat_pay_support.verify_wechatpay_signature({
                'Wechatpay-Timestamp': '1720000000',
                'Wechatpay-Nonce': 'old-nonce',
                'Wechatpay-Signature': 'c2lnbmF0dXJl',
                'Wechatpay-Serial': 'TEST_SERIAL_001'
            }, '{}')

    def test_query_api_response_must_have_valid_signature(self):
        private_key, certificate = _build_test_certificate()
        trade = self._successful_trade()
        body = json.dumps(trade, separators=(',', ':'))
        timestamp = str(int(time.time()))
        nonce = 'api-response-nonce'
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': nonce,
            'Wechatpay-Serial': 'TEST_SERIAL_001',
            'Wechatpay-Signature': _sign_callback_body(private_key, timestamp, nonce, body)
        }
        path = '/v3/pay/transactions/out-trade-no/ORD202608150001?mchid=1900000001'

        with patch.object(wechat_pay_support, '_build_auth_header', return_value='TEST'), \
             patch.object(wechat_pay_support, '_get_platform_certificate', return_value=certificate), \
             patch.object(wechat_pay_support, 'urlopen',
                          return_value=FakeWeChatResponse(body, headers)):
            self.assertEqual(wechat_pay_support._wechat_api_request('GET', path), trade)

        with patch.object(wechat_pay_support, '_build_auth_header', return_value='TEST'), \
             patch.object(wechat_pay_support, '_get_platform_certificate', return_value=certificate), \
             patch.object(wechat_pay_support, 'urlopen',
                          return_value=FakeWeChatResponse(body.replace('SUCCESS', 'NOTPAY'), headers)):
            with self.assertRaises(wechat_pay_support.WeChatPayError):
                wechat_pay_support._wechat_api_request('GET', path)

    def test_wechatpay_public_key_mode_verifies_exact_configured_id(self):
        private_key, _ = _build_test_certificate()
        public_key_pem = private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        self.app.config['WECHAT_PAY_PUBLIC_KEY_ID'] = 'PUB_KEY_ID_1234567890'
        self.app.config['WECHAT_PAY_PUBLIC_KEY'] = public_key_pem
        wechat_pay_support._load_wechatpay_public_key.cache_clear()

        body = '{"status":"SUCCESS"}'
        timestamp = str(int(time.time()))
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': 'public-key-nonce',
            'Wechatpay-Serial': 'PUB_KEY_ID_1234567890',
            'Wechatpay-Signature': _sign_callback_body(private_key, timestamp, 'public-key-nonce', body)
        }
        try:
            wechat_pay_support.verify_wechatpay_signature(headers, body)
            with self.assertRaises(wechat_pay_support.WeChatPayError):
                wechat_pay_support.verify_wechatpay_signature(headers, '{"status":"NOTPAY"}')
            headers['Wechatpay-Serial'] = 'PUB_KEY_ID_OTHER'
            with self.assertRaises(wechat_pay_support.WeChatPayError):
                wechat_pay_support.verify_wechatpay_signature(headers, body)
        finally:
            wechat_pay_support._load_wechatpay_public_key.cache_clear()

    def test_refund_query_uses_read_only_endpoint(self):
        with patch.object(wechat_pay_support, '_wechat_api_request', return_value={'status': 'SUCCESS'}) as request:
            self.assertEqual(wechat_pay_support.query_manual_refund('REFUND_001'), {'status': 'SUCCESS'})
        request.assert_called_once_with('GET', '/v3/refund/domestic/refunds/REFUND_001')

    def test_refund_application_uses_full_original_transaction_amount(self):
        with patch.object(wechat_pay_support, '_wechat_api_request', return_value={'status': 'PROCESSING'}) as request:
            result = wechat_pay_support.create_wechat_refund('WECHAT_TX', 'AR123', 399, '用户申请退款')
        self.assertEqual(result['status'], 'PROCESSING')
        request.assert_called_once_with('POST', '/v3/refund/domestic/refunds', {
            'transaction_id': 'WECHAT_TX', 'out_refund_no': 'AR123', 'reason': '用户申请退款',
            'amount': {'refund': 399, 'total': 399, 'currency': 'CNY'},
        })

    def test_signed_order_not_exist_error_preserves_code(self):
        private_key, certificate = _build_test_certificate()
        body = '{"code":"ORDER_NOT_EXIST","message":"missing"}'
        timestamp = str(int(time.time()))
        nonce = 'api-error-nonce'
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': nonce,
            'Wechatpay-Serial': 'TEST_SERIAL_001',
            'Wechatpay-Signature': _sign_callback_body(private_key, timestamp, nonce, body)
        }
        error = HTTPError('https://api.mch.weixin.qq.com/test', 404, 'Not Found', headers,
                          io.BytesIO(body.encode('utf-8')))
        with patch.object(wechat_pay_support, '_build_auth_header', return_value='TEST'), \
             patch.object(wechat_pay_support, '_get_platform_certificate', return_value=certificate), \
             patch.object(wechat_pay_support, 'urlopen', side_effect=error):
            with self.assertRaises(wechat_pay_support.WeChatPayApiError) as caught:
                wechat_pay_support._wechat_api_request('GET', '/test')

        self.assertEqual(caught.exception.code, 'ORDER_NOT_EXIST')
        self.assertEqual(caught.exception.status_code, 404)

    def test_close_api_verifies_signed_empty_response(self):
        private_key, certificate = _build_test_certificate()
        timestamp = str(int(time.time()))
        nonce = 'close-response-nonce'
        headers = {
            'Wechatpay-Timestamp': timestamp,
            'Wechatpay-Nonce': nonce,
            'Wechatpay-Serial': 'TEST_SERIAL_001',
            'Wechatpay-Signature': _sign_callback_body(private_key, timestamp, nonce, '')
        }
        with patch.object(wechat_pay_support, '_build_auth_header', return_value='TEST'), \
             patch.object(wechat_pay_support, '_get_platform_certificate', return_value=certificate), \
             patch.object(wechat_pay_support, 'urlopen',
                          return_value=FakeWeChatResponse('', headers)):
            self.assertEqual(wechat_pay_support.close_jsapi_order_by_out_trade_no(self.order.order_sn), {})

    def test_create_wechat_pay_returns_payment_payload(self):
        fake_payment = {
            'prepay_id': 'prepay-test-001',
            'payment': {
                'timeStamp': '1720000000',
                'nonceStr': 'nonce-test',
                'package': 'prepay_id=prepay-test-001',
                'signType': 'RSA',
                'paySign': 'sign-test'
            }
        }

        with patch.object(wechat_pay_support, 'create_jsapi_prepay', return_value=fake_payment):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/wechat-pay', headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['order_sn'], self.order.order_sn)
        self.assertEqual(payload['prepay_id'], 'prepay-test-001')
        self.assertEqual(payload['payment']['package'], 'prepay_id=prepay-test-001')

    def test_order_detail_and_list_include_can_pay_flag(self):
        list_response = self.client.get('/client/orders', headers=self.auth_headers)
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertTrue(list_payload['orders'][0]['can_pay'])

        detail_response = self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.auth_headers)
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json()
        self.assertTrue(detail_payload['can_pay'])

    def test_paid_order_cannot_be_cancelled_without_refund(self):
        self.order.order_status = 20
        db.session.commit()
        response = self.client.post(f'/client/orders/{self.order.order_sn}/cancel', headers=self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._reload_order().order_status, 20)


if __name__ == '__main__':
    unittest.main()



