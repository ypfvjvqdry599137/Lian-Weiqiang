import base64
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID
from flask import Flask
import werkzeug

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

from client_routes import client_bp  # noqa: E402
from extensions import db  # noqa: E402
from models import Category, OrderItem, OrderMaster, Product, ProductStock, User  # noqa: E402
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


class WeChatPayTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(prefix='wechat-pay-test-', suffix='.sqlite')
        os.close(fd)

        self.app = Flask(__name__)
        self.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path.replace("\\", "/")}',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
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

    def test_parse_wechatpay_notification_round_trip(self):
        private_key, certificate = _build_test_certificate()
        api_v3_key = self.app.config['WECHAT_PAY_API_V3_KEY']
        resource_payload = {
            'appid': self.app.config['WECHAT_MINI_PROGRAM_APPID'],
            'mchid': self.app.config['WECHAT_PAY_MCHID'],
            'out_trade_no': self.order.order_sn,
            'transaction_id': '4200001234567890',
            'trade_state': 'SUCCESS',
            'trade_state_desc': '支付成功',
            'success_time': '2026-08-15T08:00:00+08:00'
        }
        resource = _encrypt_resource(api_v3_key, resource_payload)
        notification = {
            'id': 'notify-001',
            'create_time': '2026-08-15T08:00:00+08:00',
            'event_type': 'TRANSACTION.SUCCESS',
            'resource': resource
        }
        body_text = json.dumps(notification, ensure_ascii=False, separators=(',', ':'))
        timestamp = '1720000000'
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
        resource = {
            'appid': self.app.config['WECHAT_MINI_PROGRAM_APPID'],
            'mchid': self.app.config['WECHAT_PAY_MCHID'],
            'out_trade_no': self.order.order_sn,
            'transaction_id': '4200001234567890',
            'trade_state': 'SUCCESS'
        }
        notification = {'resource': resource}

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

    def test_pay_order_finalizes_paid_order(self):
        with patch.object(
            wechat_pay_support,
            'query_jsapi_order_by_out_trade_no',
            return_value={
                'trade_state': 'SUCCESS',
                'transaction_id': '4200000987654321',
                'trade_state_desc': '支付成功'
            }
        ):
            response = self.client.post(f'/client/orders/{self.order.order_sn}/pay')

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
            response = self.client.post(f'/client/orders/{self.order.order_sn}/wechat-pay')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['order_sn'], self.order.order_sn)
        self.assertEqual(payload['prepay_id'], 'prepay-test-001')
        self.assertEqual(payload['payment']['package'], 'prepay_id=prepay-test-001')

    def test_order_detail_and_list_include_can_pay_flag(self):
        list_response = self.client.get('/client/orders')
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertTrue(list_payload['orders'][0]['can_pay'])

        detail_response = self.client.get(f'/client/orders/{self.order.order_sn}')
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json()
        self.assertTrue(detail_payload['can_pay'])


if __name__ == '__main__':
    unittest.main()



