import os
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
import werkzeug
from werkzeug.security import generate_password_hash

if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_routes import admin_bp
from auth import issue_token
from client_routes import client_bp
from extensions import db
from fulfillment_admin_routes import fulfillment_admin_bp
from merchant_routes import get_merchant_key, merchant_bp
from models import Cart, Category, ClientIdentity, DeliveryZone, ManualRefund, OrderItem, OrderMaster, Product, Supplier, SupplierOrder, User, UserAddress
from supplier_routes import supplier_bp
from wechat_pay_support import WeChatPayError


class AuthIsolationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            AUTH_SIGNING_KEY='auth-test-signing-key-with-more-than-32-chars',
            ADMIN_PASSWORD_HASH=generate_password_hash('admin-test-password', method='pbkdf2:sha256:1000'),
            WECHAT_MINI_PROGRAM_APPID='wx-test',
            WECHAT_PAY_MCHID='mch-test',
        )
        db.init_app(self.app)
        for blueprint in (client_bp, admin_bp, fulfillment_admin_bp, supplier_bp, merchant_bp):
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

    def test_bulk_product_delete_is_atomic_and_preserves_order_history(self):
        first = Product.query.first()
        first.image_url = 'https://example.com/first.jpg'
        second = Product(name='second product', price=Decimal('3.00'), unit='item', is_active=True)
        db.session.add(second)
        db.session.flush()
        order_item = OrderItem(
            order_sn=self.order.order_sn, product_id=first.id,
            product_name=first.name, price=first.price, quantity=1, unit=first.unit,
        )
        db.session.add(order_item)
        db.session.commit()

        url = '/admin/products/batch'
        ids = [first.id, second.id]
        self.assertEqual(self.client.delete(url, json={'ids': ids}).status_code, 401)
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        self.assertEqual(self.client.delete(url, headers=headers, json=[first.id]).status_code, 400)
        for invalid in ([], [first.id, first.id], [first.id, True], ['1'], list(range(1, 202))):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.client.delete(url, headers=headers, json={'ids': invalid}).status_code, 400)
        self.assertEqual(self.client.delete(url, headers=headers, json={'ids': [first.id, 99999]}).status_code, 409)
        self.assertTrue(db.session.get(Product, first.id).is_active)
        self.assertTrue(db.session.get(Product, second.id).is_active)

        response = self.client.delete(url, headers=headers, json={'ids': ids})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['count'], 2)
        self.assertFalse(db.session.get(Product, first.id).is_active)
        self.assertFalse(db.session.get(Product, second.id).is_active)
        self.assertEqual(db.session.get(Product, first.id).image_url, 'https://example.com/first.jpg')
        self.assertEqual(OrderItem.query.filter_by(order_sn=self.order.order_sn).count(), 1)
        self.assertEqual(self.client.get('/admin/products?is_active=true', headers=headers).get_json()['products'], [])
        self.assertEqual(self.client.delete(url, headers=headers, json={'ids': ids}).status_code, 409)

        zone = SimpleNamespace(id=1, delivery_fee=Decimal('0'))
        with patch('client_routes.check_delivery_available', return_value={'available': True, 'zone': zone}):
            checkout = self.client.post('/client/orders', headers=self.a, json={'address_id': self.address_id})
        self.assertEqual(checkout.status_code, 400)
        self.assertIn('已下架', checkout.get_json()['message'])
        self.assertEqual(OrderMaster.query.count(), 1)

    def test_order_status_labels_are_readable_in_list_and_detail(self):
        labels = {
            10: '待付款', 20: '待配货', 30: '配送中',
            40: '已送达', 50: '已完成', 60: '已取消',
        }
        for status, expected in labels.items():
            with self.subTest(status=status):
                self.order.order_status = status
                db.session.commit()
                listed = self.client.get('/client/orders', headers=self.a)
                detail = self.client.get('/client/orders/ORDER_A', headers=self.a)
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(listed.get_json()['orders'][0]['status_text'], expected)
                self.assertEqual(detail.get_json()['status_text'], expected)

    def test_admin_order_filters_use_refund_display_status_without_changing_payment_state(self):
        headers = self._paid_admin_headers()
        canceled = OrderMaster(order_sn='CANCELED_ORDER', user_id=self.a_id, order_status=60)
        db.session.add(canceled)
        db.session.commit()

        pending = self.client.get('/admin/orders?status=20', headers=headers).get_json()['orders']
        self.assertEqual([item['order_sn'] for item in pending], [self.order.order_sn])
        self.assertEqual(pending[0]['status_text'], '待配货')
        self.assertEqual(pending[0]['display_status'], 20)

        refund = ManualRefund(
            order_sn=self.order.order_sn, out_refund_no='REFUND_ORDER_A',
            transaction_id=self.order.transaction_id, order_total_fen=1600,
            refund_fen=1600, status='SUCCESS',
        )
        db.session.add(refund)
        db.session.commit()

        refunded = self.client.get('/admin/orders?status=70', headers=headers).get_json()['orders']
        self.assertEqual(len(refunded), 1)
        self.assertEqual(refunded[0]['order_status'], 20)
        self.assertEqual(refunded[0]['display_status'], 70)
        self.assertEqual(refunded[0]['status_text'], '已退款')
        self.assertFalse(refunded[0]['can_request_refund'])
        self.assertEqual(self.client.get('/admin/orders?status=20', headers=headers).get_json()['orders'], [])
        canceled_list = self.client.get('/admin/orders?status=60', headers=headers).get_json()['orders']
        self.assertEqual([item['order_sn'] for item in canceled_list], [canceled.order_sn])
        self.assertEqual(canceled_list[0]['status_text'], '已取消')

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

    def test_legacy_category_request_only_exposes_public_categories_to_clients(self):
        db.session.add_all((
            Category(name='Visible', is_active=True),
            Category(name='Hidden', is_active=False),
        ))
        db.session.commit()

        public = self.client.get('/client/categories').get_json()
        legacy = self.client.get('/admin/categories', headers=self.a)
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.get_json(), public)
        self.assertEqual([category['name'] for category in public['categories']], ['Visible'])
        self.assertEqual(self.client.get('/admin/categories').status_code, 401)
        self.assertEqual(self.client.get('/admin/categories', headers={'Authorization': 'Bearer invalid'}).status_code, 401)
        self.assertEqual(self.client.post('/admin/categories', headers=self.a, json={'name': 'Nope'}).status_code, 401)

        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        admin = self.client.get('/admin/categories', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(admin.status_code, 200)
        self.assertEqual({category['name'] for category in admin.get_json()['categories']}, {'Visible', 'Hidden'})

    def test_admin_rejects_blank_password_even_if_configured_hash_matches(self):
        for password in ('', '   '):
            with self.subTest(password=password):
                password_hash = generate_password_hash(password, method='pbkdf2:sha256:1000')
                self.app.config['ADMIN_PASSWORD_HASH'] = password_hash
                self.assertEqual(self.client.post('/admin/auth/login', json={'password': password}).status_code, 401)

                token = issue_token('admin', 1, password_hash)
                response = self.client.post(
                    f'/admin/orders/{self.order.order_sn}/wechat-refunds',
                    headers={'Authorization': f'Bearer {token}'},
                    json={'admin_password': password, 'confirm_order_sn': self.order.order_sn, 'confirm_amount_fen': 1600},
                )
                self.assertEqual(response.status_code, 403)

    def test_admin_cannot_fake_payment_or_delete_paid_order(self):
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        path = f'/admin/orders/{self.order.order_sn}'
        self.assertEqual(self.client.put(f'{path}/status', json={'status': 20}, headers=headers).status_code, 400)
        self.order.order_status = 20
        db.session.commit()
        self.assertEqual(self.client.put(f'{path}/status', json={'status': 60}, headers=headers).status_code, 400)
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 400)

    def test_admin_cannot_delete_unclosed_or_paid_cancelled_order(self):
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        path = f'/admin/orders/{self.order.order_sn}'

        orders = self.client.get('/admin/orders', headers=headers).get_json()['orders']
        self.assertFalse(orders[0]['can_delete'])
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 400)
        self.assertIsNotNone(db.session.get(OrderMaster, self.order.order_sn))

        self.order.order_status = 60
        self.order.transaction_id = 'wechat-transaction-id'
        db.session.commit()
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 400)
        self.assertIsNotNone(db.session.get(OrderMaster, self.order.order_sn))
        orders = self.client.get('/admin/orders', headers=headers).get_json()['orders']
        self.assertFalse(orders[0]['can_delete'])

        self.order.transaction_id = None
        self.order.refund_status = 1
        db.session.commit()
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 400)
        orders = self.client.get('/admin/orders', headers=headers).get_json()['orders']
        self.assertFalse(orders[0]['can_delete'])

    def test_admin_can_delete_unpaid_cancelled_order(self):
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        self.order.order_status = 60
        db.session.commit()

        orders = self.client.get('/admin/orders', headers=headers).get_json()['orders']
        self.assertTrue(orders[0]['can_delete'])
        self.assertEqual(self.client.delete(f'/admin/orders/{self.order.order_sn}', headers=headers).status_code, 200)
        self.assertIsNone(db.session.get(OrderMaster, self.order.order_sn))

    def _manual_refund_payload(self, out_refund_no='REFUND_ORDER_A', status='PROCESSING'):
        return {
            'out_refund_no': out_refund_no,
            'out_trade_no': self.order.order_sn,
            'transaction_id': 'wechat-transaction-id',
            'refund_id': f'wx-{out_refund_no}',
            'status': status,
            'amount': {'total': 1600, 'refund': 1600, 'currency': 'CNY'},
        }

    def _paid_admin_headers(self):
        self.order.order_status = 20
        self.order.transaction_id = 'wechat-transaction-id'
        db.session.commit()
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        return {'Authorization': f'Bearer {token}'}

    def _wechat_refund_data(self):
        return {
            'reason': '用户申请退款', 'confirm_order_sn': self.order.order_sn,
            'confirm_amount_fen': 1600, 'admin_password': 'admin-test-password',
        }

    def _paid_trade_payload(self):
        return {
            'appid': 'wx-test', 'mchid': 'mch-test',
            'transaction_id': self.order.transaction_id,
            'out_trade_no': self.order.order_sn,
            'trade_state': 'SUCCESS',
            'amount': {'total': 1600, 'currency': 'CNY'},
            'payer': {'openid': self.order.user.openid},
        }

    def test_wechat_refund_requires_reauth_and_exact_order_amount(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        self.assertEqual(self.client.post(path, json=self._wechat_refund_data()).status_code, 401)
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no') as query:
            for key, value, expected in (
                ('admin_password', 'wrong', 403),
                ('confirm_order_sn', 'OTHER', 400),
                ('confirm_amount_fen', 1500, 409),
                ('reason', '退款' * 50, 400),
            ):
                data = self._wechat_refund_data()
                data[key] = value
                self.assertEqual(self.client.post(path, headers=headers, json=data).status_code, expected)
            query.assert_not_called()
        self.assertEqual(ManualRefund.query.count(), 0)

    def test_wechat_refund_acceptance_query_and_no_duplicate(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no', return_value=self._paid_trade_payload()), \
                patch('wechat_pay_support.create_wechat_refund') as create:
            create.side_effect = lambda _tx, refund_no, _fen, _reason: {
                **self._manual_refund_payload(refund_no), 'channel': 'ORIGINAL'
            }
            response = self.client.post(path, headers=headers, json=self._wechat_refund_data())
        self.assertEqual(response.status_code, 201)
        refund = ManualRefund.query.one()
        self.assertTrue(refund.out_refund_no.startswith('AR'))
        create.assert_called_once_with('wechat-transaction-id', refund.out_refund_no, 1600, '用户申请退款')
        self.assertEqual(refund.status, 'PROCESSING')
        self.assertEqual(refund.refund_channel, 'ORIGINAL')
        self.assertFalse(self.client.get('/admin/orders', headers=headers).get_json()['orders'][0]['can_request_refund'])
        self.assertEqual(self.client.put(f'/admin/orders/{self.order.order_sn}/status',
                                         headers=headers, json={'status': 30}).status_code, 409)
        with patch('wechat_pay_support.create_wechat_refund') as create:
            self.assertEqual(self.client.post(path, headers=headers, json=self._wechat_refund_data()).status_code, 409)
            create.assert_not_called()
        with patch('wechat_pay_support.query_manual_refund',
                   return_value=self._manual_refund_payload(refund.out_refund_no, status='SUCCESS')):
            verify = self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                      headers=headers, json={'out_refund_no': refund.out_refund_no})
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(ManualRefund.query.one().status, 'SUCCESS')
        self.assertEqual(ManualRefund.query.count(), 1)
        refunded = self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.a).get_json()
        self.assertEqual(refunded['order_status'], 70)
        self.assertEqual(refunded['status_text'], '已退款')
        self.assertIsNone(refunded['manual_refund_status_text'])
        self.assertEqual(db.session.get(OrderMaster, self.order.order_sn).order_status, 20)
        self.assertEqual(self.client.get('/client/orders?status=20', headers=self.a).get_json()['orders'], [])
        self.assertEqual(self.client.get('/client/orders?status=70', headers=self.a)
                         .get_json()['orders'][0]['status_text'], '已退款')
        self.assertEqual(self.client.get('/client/orders', headers=self.b).get_json()['orders'], [])

    def test_wechat_refund_timeout_reuses_same_number_or_can_query(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no', return_value=self._paid_trade_payload()), \
                patch('wechat_pay_support.create_wechat_refund', side_effect=WeChatPayError('timeout')) as create:
            self.assertEqual(self.client.post(path, headers=headers, json=self._wechat_refund_data()).status_code, 502)
        refund = ManualRefund.query.one()
        self.assertEqual(refund.status, 'APPLYING')
        self.assertEqual(create.call_args.args[1], refund.out_refund_no)
        self.assertTrue(self.client.get('/admin/orders', headers=headers).get_json()['orders'][0]['can_retry_wechat_refund'])
        retry_data = self._wechat_refund_data()
        retry_data.pop('reason')
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no') as query, \
                patch('wechat_pay_support.create_wechat_refund',
                      return_value=self._manual_refund_payload(refund.out_refund_no)) as create:
            self.assertEqual(self.client.post(path, headers=headers, json=retry_data).status_code, 200)
            query.assert_not_called()
        self.assertEqual(create.call_args.args[1], refund.out_refund_no)
        self.assertEqual(create.call_args.args[3], '用户申请退款')
        self.assertEqual(ManualRefund.query.count(), 1)
        self.assertEqual(ManualRefund.query.one().status, 'PROCESSING')

    def test_wechat_refund_timeout_can_be_resolved_by_query_without_reapplication(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no', return_value=self._paid_trade_payload()), \
                patch('wechat_pay_support.create_wechat_refund', side_effect=WeChatPayError('timeout')):
            self.assertEqual(self.client.post(path, headers=headers, json=self._wechat_refund_data()).status_code, 502)
        refund = ManualRefund.query.one()
        with patch('wechat_pay_support.query_manual_refund',
                   return_value=self._manual_refund_payload(refund.out_refund_no, status='SUCCESS')), \
                patch('wechat_pay_support.create_wechat_refund') as create:
            response = self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                        headers=headers, json={'out_refund_no': refund.out_refund_no})
            create.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ManualRefund.query.one().status, 'SUCCESS')
        self.assertEqual(ManualRefund.query.count(), 1)

    def test_wechat_refund_mismatched_application_response_stays_unconfirmed(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no', return_value=self._paid_trade_payload()), \
                patch('wechat_pay_support.create_wechat_refund') as create:
            create.side_effect = lambda _tx, refund_no, _fen, _reason: {
                **self._manual_refund_payload(refund_no),
                'out_trade_no': 'OTHER_ORDER',
            }
            response = self.client.post(path, headers=headers, json=self._wechat_refund_data())
        self.assertEqual(response.status_code, 502)
        self.assertEqual(ManualRefund.query.one().status, 'APPLYING')
        self.assertIsNone(ManualRefund.query.one().refund_id)
        self.assertEqual(self.client.put(f'/admin/orders/{self.order.order_sn}/status',
                                         headers=headers, json={'status': 30}).status_code, 409)

    def test_wechat_refund_rejects_wrong_trade_and_existing_manual_refund(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/wechat-refunds'
        bad_trade = self._paid_trade_payload()
        bad_trade['transaction_id'] = 'OTHER'
        with patch('wechat_pay_support.query_jsapi_order_by_out_trade_no', return_value=bad_trade), \
                patch('wechat_pay_support.create_wechat_refund') as create:
            self.assertEqual(self.client.post(path, headers=headers, json=self._wechat_refund_data()).status_code, 502)
            create.assert_not_called()
        self.assertEqual(ManualRefund.query.count(), 0)
        self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refund-requests',
                         headers=headers, json={'operator_note': '商户平台人工处理'})
        with patch('wechat_pay_support.create_wechat_refund') as create:
            self.assertEqual(self.client.post(path, headers=headers, json=self._wechat_refund_data()).status_code, 409)
            create.assert_not_called()

    def test_manual_refund_request_pauses_fulfillment_without_wechat_money_call(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/manual-refund-requests'
        self.assertEqual(self.client.post(path, json={'operator_note': 'test'}).status_code, 401)

        with patch('wechat_pay_support.query_manual_refund') as query:
            response = self.client.post(path, headers=headers, json={'operator_note': '客服 A：用户申请整单退款'})
            query.assert_not_called()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['refund']['status'], 'REQUESTED')
        refund = ManualRefund.query.one()
        self.assertIsNone(refund.out_refund_no)
        self.assertIsNone(refund.checked_at)
        self.assertEqual(refund.refund_fen, 1600)
        self.assertEqual(self.client.put(f'/admin/orders/{self.order.order_sn}/status',
                                         headers=headers, json={'status': 30}).status_code, 409)
        self.assertEqual(self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.a)
                         .get_json()['manual_refund_status_text'], '待人工退款，配送已暂停')
        self.assertFalse(self.client.get('/admin/orders', headers=headers).get_json()['orders'][0]['can_request_refund'])
        self.assertEqual(self.client.post(path, headers=headers, json={'operator_note': '重复请求'}).status_code, 409)
        self.assertEqual(ManualRefund.query.count(), 1)

    def test_failed_manual_refund_query_keeps_requested_hold(self):
        headers = self._paid_admin_headers()
        request_path = f'/admin/orders/{self.order.order_sn}/manual-refund-requests'
        self.assertEqual(self.client.post(request_path, headers=headers,
                                          json={'operator_note': '客服 A：用户申请整单退款'}).status_code, 201)
        with patch('wechat_pay_support.query_manual_refund', side_effect=WeChatPayError('暂时不可查询')):
            response = self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                        headers=headers, json={'out_refund_no': 'REFUND_ORDER_A'})
        self.assertEqual(response.status_code, 502)
        refund = ManualRefund.query.one()
        self.assertEqual(refund.status, 'REQUESTED')
        self.assertIsNone(refund.out_refund_no)
        self.assertEqual(self.client.put(f'/admin/orders/{self.order.order_sn}/status',
                                         headers=headers, json={'status': 30}).status_code, 409)

    def test_manual_refund_query_fills_request_in_place(self):
        headers = self._paid_admin_headers()
        request_path = f'/admin/orders/{self.order.order_sn}/manual-refund-requests'
        self.assertEqual(self.client.post(request_path, headers=headers,
                                          json={'operator_note': '客服 A：用户申请整单退款'}).status_code, 201)
        pending_id = ManualRefund.query.one().id
        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload()):
            response = self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                        headers=headers, json={'out_refund_no': 'REFUND_ORDER_A'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ManualRefund.query.count(), 1)
        refund = ManualRefund.query.one()
        self.assertEqual(refund.id, pending_id)
        self.assertEqual(refund.out_refund_no, 'REFUND_ORDER_A')
        self.assertEqual(refund.status, 'PROCESSING')
        self.assertIsNotNone(refund.checked_at)

    def test_manual_refund_is_verified_and_refreshed_without_sending_money(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/manual-refunds'
        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload()):
            response = self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_A', 'operator_note': '客服在商户平台人工退款'
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['refund']['status'], 'PROCESSING')
        self.assertEqual(ManualRefund.query.count(), 1)
        self.assertEqual(self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.a)
                         .get_json()['manual_refund_status_text'], '退款处理中')
        self.assertEqual(self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.a)
                         .get_json()['order_status'], 20)
        self.assertEqual(self.client.put(f'/admin/orders/{self.order.order_sn}/status',
                                         headers=headers, json={'status': 30}).status_code, 409)

        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload(status='SUCCESS')):
            response = self.client.post(path, headers=headers, json={'out_refund_no': 'REFUND_ORDER_A'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['refund']['status'], 'SUCCESS')
        self.assertEqual(ManualRefund.query.count(), 1)
        refunded = self.client.get(f'/client/orders/{self.order.order_sn}', headers=self.a).get_json()
        self.assertEqual(refunded['order_status'], 70)
        self.assertEqual(refunded['status_text'], '已退款')
        self.assertIsNone(refunded['manual_refund_status_text'])

    def test_manual_refund_rejects_wrong_trade_and_amount(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/manual-refunds'
        for field, value in [('out_trade_no', 'OTHER_ORDER'), ('transaction_id', 'OTHER_TX')]:
            payload = self._manual_refund_payload()
            payload[field] = value
            with self.subTest(field=field), patch('wechat_pay_support.query_manual_refund', return_value=payload):
                self.assertEqual(self.client.post(path, headers=headers, json={
                    'out_refund_no': 'REFUND_ORDER_A', 'operator_note': '人工退款'
                }).status_code, 502)
        for key, value in [('total', 1500), ('refund', 1500), ('currency', 'USD')]:
            payload = self._manual_refund_payload()
            payload['amount'][key] = value
            with self.subTest(key=key), patch('wechat_pay_support.query_manual_refund', return_value=payload):
                self.assertEqual(self.client.post(path, headers=headers, json={
                    'out_refund_no': 'REFUND_ORDER_A', 'operator_note': '人工退款'
                }).status_code, 502)
        self.assertEqual(ManualRefund.query.count(), 0)

    def test_manual_refund_cannot_replace_active_attempt_but_can_retry_closed(self):
        headers = self._paid_admin_headers()
        path = f'/admin/orders/{self.order.order_sn}/manual-refunds'
        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload()):
            self.assertEqual(self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_A', 'operator_note': '首次人工退款'
            }).status_code, 201)
        next_payload = self._manual_refund_payload('REFUND_ORDER_B')
        with patch('wechat_pay_support.query_manual_refund', return_value=next_payload):
            self.assertEqual(self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_B', 'operator_note': '第二次人工退款'
            }).status_code, 409)

        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload(status='CLOSED')):
            self.assertEqual(self.client.post(path, headers=headers,
                                              json={'out_refund_no': 'REFUND_ORDER_A'}).status_code, 200)
        with patch('wechat_pay_support.query_manual_refund', return_value=next_payload):
            self.assertEqual(self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_B', 'operator_note': '首次退款关闭后重试'
            }).status_code, 201)
        self.assertEqual(ManualRefund.query.count(), 2)
        self.assertEqual(self.client.get(path, headers=headers).get_json()['refunds'][0]['out_refund_no'],
                         'REFUND_ORDER_B')

    def test_manual_refund_requires_paid_order_and_admin_auth(self):
        path = f'/admin/orders/{self.order.order_sn}/manual-refunds'
        self.assertEqual(self.client.post(path, json={'out_refund_no': 'REFUND_ORDER_A'}).status_code, 401)
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        with patch('wechat_pay_support.query_manual_refund') as query:
            self.assertEqual(self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_A', 'operator_note': 'test'
            }).status_code, 409)
            query.assert_not_called()

    def test_manual_refund_rejects_legacy_after_sale_state(self):
        headers = self._paid_admin_headers()
        self.order.refund_status = 30
        db.session.commit()
        path = f'/admin/orders/{self.order.order_sn}/manual-refunds'
        with patch('wechat_pay_support.query_manual_refund') as query:
            self.assertEqual(self.client.post(path, headers=headers, json={
                'out_refund_no': 'REFUND_ORDER_A', 'operator_note': '人工退款'
            }).status_code, 409)
            query.assert_not_called()
        self.assertFalse(self.client.get('/admin/orders', headers=headers).get_json()['orders'][0]['can_verify_refund'])

    def test_manual_refund_blocks_supplier_and_station_progress(self):
        headers = self._paid_admin_headers()
        zone = DeliveryZone(
            zone_name='退款测试区域', center_lng=Decimal('116.1'), center_lat=Decimal('39.9'),
            merchant_username='merchant-refund', merchant_password='merchant-test-password', is_active=True
        )
        supplier = Supplier(name='退款测试供应商', username='supplier-refund', password='supplier-test-password',
                            is_active=True, is_deleted=False)
        db.session.add_all((zone, supplier))
        db.session.flush()
        self.order.zone_id = zone.id
        supplier_order = SupplierOrder(order_sn=self.order.order_sn, supplier_id=supplier.id, status=10)
        db.session.add(supplier_order)
        db.session.commit()

        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload()):
            self.assertEqual(self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                              headers=headers, json={'out_refund_no': 'REFUND_ORDER_A',
                                                                     'operator_note': '人工退款'}).status_code, 201)

        supplier_token = self.client.post('/supplier/login',
                                          json={'username': supplier.username, 'password': 'supplier-test-password'})
        supplier_headers = {'Authorization': f"Bearer {supplier_token.get_json()['token']}"}
        supplier_path = f'/supplier/orders/{supplier_order.id}/status?supplier_id={supplier.id}'
        self.assertEqual(self.client.put(supplier_path, headers=supplier_headers,
                                         json={'status': 20}).status_code, 409)
        self.assertEqual(self.client.put(f'/admin/supplier-orders/{supplier_order.id}/status', headers=headers,
                                         json={'status': 20}).status_code, 409)
        merchant_path = f'/merchant/orders/{self.order.order_sn}/start-delivery?zone_id={zone.id}'
        self.assertEqual(self.client.post(merchant_path, headers={'X-Merchant-Key': get_merchant_key(zone)}).status_code, 409)

        with patch('wechat_pay_support.query_manual_refund',
                   return_value=self._manual_refund_payload(status='CLOSED')):
            self.assertEqual(self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                              headers=headers, json={'out_refund_no': 'REFUND_ORDER_A'}).status_code, 200)
        self.assertEqual(self.client.put(supplier_path, headers=supplier_headers,
                                         json={'status': 20}).status_code, 200)

    def test_admin_can_cancel_supplier_preparation_during_manual_refund(self):
        headers = self._paid_admin_headers()
        supplier = Supplier(name='取消备货供应商', username='cancel-supplier', password='supplier-password',
                            is_active=True, is_deleted=False)
        db.session.add(supplier)
        db.session.flush()
        supplier_order = SupplierOrder(order_sn=self.order.order_sn, supplier_id=supplier.id, status=10)
        db.session.add(supplier_order)
        db.session.commit()
        with patch('wechat_pay_support.query_manual_refund', return_value=self._manual_refund_payload()):
            self.assertEqual(self.client.post(f'/admin/orders/{self.order.order_sn}/manual-refunds',
                                              headers=headers, json={'out_refund_no': 'REFUND_ORDER_A',
                                                                     'operator_note': '人工退款'}).status_code, 201)
        self.assertEqual(self.client.put(f'/admin/supplier-orders/{supplier_order.id}/status', headers=headers,
                                         json={'status': 40}).status_code, 200)
        self.assertEqual(db.session.get(SupplierOrder, supplier_order.id).status, 40)

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
