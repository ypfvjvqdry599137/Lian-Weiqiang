import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Flask
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_routes import admin_bp
from auth import issue_token
from client_routes import client_bp
from extensions import db
from fulfillment_admin_routes import fulfillment_admin_bp
from models import Cart, ClientIdentity, DeliveryZone, OrderMaster, Product, Supplier, User, UserAddress
from supplier_routes import supplier_bp


class AuthIsolationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            AUTH_SIGNING_KEY='auth-test-signing-key-with-more-than-32-chars',
            ADMIN_PASSWORD_HASH=generate_password_hash('admin-test-password', method='pbkdf2:sha256:1000'),
        )
        db.init_app(self.app)
        for blueprint in (client_bp, admin_bp, fulfillment_admin_bp, supplier_bp):
            self.app.register_blueprint(blueprint)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        with patch('wechat_pay_support.exchange_code_for_openid', side_effect=lambda code: {'openid': code}):
            first = self.client.post('/client/wechat/login', json={'code': 'openid-a'}).get_json()
            second = self.client.post('/client/wechat/login', json={'code': 'openid-b'}).get_json()
        self.assertNotEqual(first['user']['id'], second['user']['id'])
        self.a = {'Authorization': f"Bearer {first['token']}"}
        self.b = {'Authorization': f"Bearer {second['token']}"}
        self.a_id = first['user']['id']
        self.b_id = second['user']['id']

        product = Product(name='test product', price=Decimal('8.00'), unit='item', is_active=True)
        db.session.add(product)
        db.session.flush()
        self.cart = Cart(user_id=self.a_id, product_id=product.id, quantity=2)
        self.address = UserAddress(
            user_id=self.a_id, receiver_name='A', receiver_phone='13800000000',
            detail_address='A street', full_address='A street',
            lng=Decimal('116.1'), lat=Decimal('39.9'),
        )
        self.order = OrderMaster(
            order_sn='ORDER_A', user_id=self.a_id, order_status=10,
            total_amount=Decimal('16.00'), delivery_fee=Decimal('0'),
            final_amount=Decimal('16.00'),
        )
        db.session.add_all((self.cart, self.address, self.order))
        db.session.commit()
        self.cart_id = self.cart.id
        self.address_id = self.address.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_private_routes_require_a_valid_client_token(self):
        for path in ('/client/cart', '/client/orders', '/client/addresses'):
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path, headers={'Authorization': 'Bearer invalid'}).status_code, 401)
        admin_token = issue_token('admin', 1, self.app.config['ADMIN_PASSWORD_HASH'])
        self.assertEqual(self.client.get('/client/orders', headers={'Authorization': f'Bearer {admin_token}'}).status_code, 401)

    def test_each_openid_has_its_own_lists(self):
        self.assertEqual(len(self.client.get('/client/cart', headers=self.a).get_json()['cart_items']), 1)
        self.assertEqual(self.client.get('/client/cart', headers=self.b).get_json()['cart_items'], [])
        self.assertEqual(len(self.client.get('/client/addresses', headers=self.a).get_json()['addresses']), 1)
        self.assertEqual(self.client.get('/client/addresses', headers=self.b).get_json()['addresses'], [])
        self.assertEqual(len(self.client.get('/client/orders', headers=self.a).get_json()['orders']), 1)
        self.assertEqual(self.client.get('/client/orders', headers=self.b).get_json()['orders'], [])

    def test_legacy_shared_account_is_quarantined_even_when_openid_matches(self):
        legacy = User(openid='legacy-openid', nickname='Legacy shared account')
        db.session.add(legacy)
        db.session.flush()
        legacy_order = OrderMaster(order_sn='LEGACY_ORDER', user_id=legacy.id, order_status=10)
        db.session.add(legacy_order)
        db.session.commit()
        legacy_id = legacy.id

        with patch('wechat_pay_support.exchange_code_for_openid', return_value={'openid': 'legacy-openid'}):
            login = self.client.post('/client/wechat/login', json={'code': 'legacy-code'}).get_json()
            again = self.client.post('/client/wechat/login', json={'code': 'legacy-code'}).get_json()

        self.assertNotEqual(login['user']['id'], legacy_id)
        self.assertEqual(again['user']['id'], login['user']['id'])
        self.assertIsNone(db.session.get(User, legacy_id).openid)
        self.assertEqual(db.session.get(ClientIdentity, 'legacy-openid').user_id, login['user']['id'])
        headers = {'Authorization': f"Bearer {login['token']}"}
        self.assertEqual(self.client.get('/client/orders', headers=headers).get_json()['orders'], [])
        self.assertEqual(db.session.get(OrderMaster, 'LEGACY_ORDER').user_id, legacy_id)

    def test_foreign_records_cannot_be_read_or_changed(self):
        paths = (
            ('get', f'/client/orders/{self.order.order_sn}'),
            ('post', f'/client/orders/{self.order.order_sn}/cancel'),
            ('post', f'/client/orders/{self.order.order_sn}/wechat-pay'),
            ('post', f'/client/orders/{self.order.order_sn}/pay'),
            ('put', f'/client/addresses/{self.address_id}'),
            ('delete', f'/client/addresses/{self.address_id}'),
            ('put', f'/client/cart/{self.cart_id}'),
            ('delete', f'/client/cart/{self.cart_id}'),
        )
        for method, path in paths:
            response = getattr(self.client, method)(path, headers=self.b, json={})
            self.assertEqual(response.status_code, 404, path)
        self.assertEqual(db.session.get(OrderMaster, self.order.order_sn).order_status, 10)

    def test_checkout_rejects_another_users_address(self):
        zone = DeliveryZone(zone_name='Test zone', center_lng=Decimal('116.1'), center_lat=Decimal('39.9'))
        db.session.add(zone)
        db.session.add(Cart(user_id=self.b_id, product_id=self.cart.product_id, quantity=1))
        db.session.commit()
        with patch('client_routes.check_delivery_available', return_value={'available': True, 'zone': zone}):
            response = self.client.post('/client/orders', headers=self.b, json={'address_id': self.address_id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(OrderMaster.query.count(), 1)

    def test_admin_apis_require_admin_login(self):
        for path in ('/admin/orders', '/admin/stations'):
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path, headers=self.a).status_code, 401)
        self.assertEqual(self.client.post('/admin/auth/login', json={'password': 'wrong'}).status_code, 401)
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        self.assertEqual(self.client.get('/admin/stations', headers={'Authorization': f'Bearer {token}'}).status_code, 200)

    def test_admin_cannot_fake_payment_or_delete_paid_order(self):
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        path = f'/admin/orders/{self.order.order_sn}'
        self.assertEqual(self.client.put(f'{path}/status', json={'status': 20}, headers=headers).status_code, 400)
        self.order.order_status = 20
        db.session.commit()
        self.assertEqual(self.client.put(f'{path}/status', json={'status': 60}, headers=headers).status_code, 400)
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 400)

    def test_supplier_id_cannot_be_switched(self):
        one = Supplier(name='One', username='one', password='supplier-password', is_active=True, is_deleted=False)
        two = Supplier(name='Two', username='two', password='supplier-password-2', is_active=True, is_deleted=False)
        db.session.add_all((one, two))
        db.session.commit()
        token = self.client.post('/supplier/login', json={'username': 'one', 'password': 'supplier-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.get(f'/supplier/profile?supplier_id={one.id}', headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f'/supplier/profile?supplier_id={two.id}', headers=headers).status_code, 403)
        self.assertEqual(self.client.get(f'/supplier/orders?supplier_id={two.id}', headers=headers).status_code, 403)
        self.assertEqual(self.client.get(f'/supplier/profile?supplier_id={one.id}').status_code, 401)


if __name__ == '__main__':
    unittest.main()
