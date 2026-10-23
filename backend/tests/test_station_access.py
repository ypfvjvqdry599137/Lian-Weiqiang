import os
import sys
import unittest
from decimal import Decimal

from flask import Flask
import werkzeug
from werkzeug.security import check_password_hash, generate_password_hash

if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_routes import admin_bp
from extensions import db
from fulfillment_admin_routes import fulfillment_admin_bp
from models import DeliveryStation, DeliveryZone, ManualRefund, OrderMaster, User
from station_routes import station_bp


class StationAccessTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            AUTH_SIGNING_KEY='station-test-signing-key-more-than-32-characters',
            ADMIN_PASSWORD_HASH=generate_password_hash('admin-password'),
        )
        db.init_app(self.app)
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(fulfillment_admin_bp)
        self.app.register_blueprint(station_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        zone_a = DeliveryZone(zone_name='A', center_lng=Decimal('118'), center_lat=Decimal('25'), is_active=True)
        zone_b = DeliveryZone(zone_name='B', center_lng=Decimal('119'), center_lat=Decimal('26'), is_active=True)
        zone_c = DeliveryZone(zone_name='C', center_lng=Decimal('120'), center_lat=Decimal('27'), is_active=True)
        user = User(openid='station-user')
        db.session.add_all([zone_a, zone_b, zone_c, user])
        db.session.flush()
        self.zone_a_id = zone_a.id
        self.zone_b_id = zone_b.id
        self.zone_c_id = zone_c.id
        db.session.add_all([
            OrderMaster(order_sn='A_PAID', user_id=user.id, zone_id=zone_a.id, order_status=20,
                        receiver_name='A customer'),
            OrderMaster(order_sn='A_UNPAID', user_id=user.id, zone_id=zone_a.id, order_status=10),
            OrderMaster(order_sn='B_PAID', user_id=user.id, zone_id=zone_b.id, order_status=20,
                        receiver_name='B customer'),
        ])
        db.session.commit()
        token = self.client.post('/admin/auth/login', json={'password': 'admin-password'}).get_json()['token']
        self.admin_headers = {'Authorization': f'Bearer {token}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def create_station(self, zone_id, username, password='strong-station-password'):
        response = self.client.post('/admin/stations', headers=self.admin_headers, json={
            'zone_id': zone_id, 'station_name': username, 'username': username,
            'password': password, 'is_active': True,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['id']

    def login_station(self, username, password='strong-station-password'):
        response = self.client.post('/station/login', json={'username': username, 'password': password})
        self.assertEqual(response.status_code, 200, response.get_json())
        return {'Authorization': f"Bearer {response.get_json()['token']}"}

    def test_station_orders_are_scoped_to_authenticated_zone(self):
        station_a_id = self.create_station(self.zone_a_id, 'station-a')
        self.create_station(self.zone_b_id, 'station-b')
        headers_a = self.login_station('station-a')
        headers_b = self.login_station('station-b')

        self.assertEqual(self.client.get('/station/orders').status_code, 401)
        self.assertEqual(self.client.get('/station/orders', headers=self.admin_headers).status_code, 401)
        orders_a = self.client.get(
            f'/station/orders?zone_id={self.zone_b_id}&station_id={station_a_id}', headers=headers_a
        ).get_json()['orders']
        self.assertEqual([order['order_sn'] for order in orders_a], ['A_PAID'])
        self.assertNotIn('B customer', str(orders_a))
        self.assertEqual([order['order_sn'] for order in
                          self.client.get('/station/orders', headers=headers_b).get_json()['orders']], ['B_PAID'])
        self.assertEqual(self.client.get('/station/orders?status=invalid', headers=headers_a).status_code, 400)
        self.assertEqual(self.client.get('/station/orders?page=0', headers=headers_a).status_code, 400)
        self.assertEqual(self.client.get('/station/orders?page=2', headers=headers_a).get_json()['orders'], [])

    def test_credentials_are_hashed_hidden_and_revocable(self):
        station_id = self.create_station(self.zone_a_id, 'station-a')
        station = db.session.get(DeliveryStation, station_id)
        self.assertNotEqual(station.password_hash, 'strong-station-password')
        self.assertTrue(check_password_hash(station.password_hash, 'strong-station-password'))
        details = self.client.get(f'/admin/stations/{station_id}', headers=self.admin_headers).get_json()
        self.assertTrue(details['has_login'])
        self.assertNotIn('password_hash', details)
        self.assertNotIn('password', details)

        old_headers = self.login_station('station-a')
        response = self.client.put(f'/admin/stations/{station_id}', headers=self.admin_headers,
                                   json={'password': 'another-strong-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/station/orders', headers=old_headers).status_code, 401)
        self.assertEqual(self.client.post('/station/login', json={
            'username': 'station-a', 'password': 'strong-station-password'
        }).status_code, 401)
        new_headers = self.login_station('station-a', 'another-strong-password')
        self.assertEqual(self.client.put(f'/admin/stations/{station_id}', headers=self.admin_headers,
                                         json={'is_active': False}).status_code, 200)
        self.assertEqual(self.client.get('/station/orders', headers=new_headers).status_code, 401)

    def test_username_is_unique_and_zone_change_invalidates_token(self):
        first_id = self.create_station(self.zone_a_id, 'station-a')
        second_id = self.create_station(self.zone_b_id, 'station-b')
        self.assertEqual(self.client.put(f'/admin/stations/{second_id}', headers=self.admin_headers,
                                         json={'username': 'station-a'}).status_code, 409)
        token = self.login_station('station-a')
        self.assertEqual(self.client.put(f'/admin/stations/{first_id}', headers=self.admin_headers,
                                         json={'zone_id': self.zone_b_id}).status_code, 409)
        self.assertEqual(self.client.put(f'/admin/stations/{first_id}', headers=self.admin_headers,
                                         json={'zone_id': self.zone_c_id}).status_code, 200)
        self.assertEqual(self.client.get('/station/orders', headers=token).status_code, 401)
        token = self.login_station('station-a')
        self.assertEqual(self.client.get('/station/orders', headers=token).get_json()['orders'], [])
        self.assertEqual(self.client.put(f'/admin/stations/{first_id}', headers=self.admin_headers,
                                         json={'username': 'station-new'}).status_code, 200)
        self.assertEqual(self.client.get('/station/orders', headers=token).status_code, 401)

    def test_refunded_order_is_not_pending(self):
        self.create_station(self.zone_a_id, 'station-a')
        headers = self.login_station('station-a')
        db.session.add(ManualRefund(
            order_sn='A_PAID', transaction_id='transaction-a', order_total_fen=100,
            refund_fen=100, status='SUCCESS',
        ))
        db.session.commit()
        pending = self.client.get('/station/orders?status=pending', headers=headers).get_json()['orders']
        refunded = self.client.get('/station/orders?status=refunded', headers=headers).get_json()['orders']
        self.assertEqual(pending, [])
        self.assertEqual([(row['order_sn'], row['status_text']) for row in refunded], [('A_PAID', '已退款')])

    def test_admin_can_delete_only_station_account(self):
        station_id = self.create_station(self.zone_a_id, 'station-a')
        token = self.login_station('station-a')

        self.assertEqual(self.client.delete(f'/admin/stations/{station_id}/account').status_code, 401)
        response = self.client.delete(f'/admin/stations/{station_id}/account', headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        station = db.session.get(DeliveryStation, station_id)
        self.assertIsNotNone(station)
        self.assertEqual(station.zone_id, self.zone_a_id)
        self.assertIsNone(station.username)
        self.assertIsNone(station.password_hash)
        self.assertIsNotNone(db.session.get(OrderMaster, 'A_PAID'))
        self.assertEqual(self.client.get('/station/orders', headers=token).status_code, 401)
        self.assertEqual(self.client.post('/station/login', json={
            'username': 'station-a', 'password': 'strong-station-password'
        }).status_code, 401)
        self.assertEqual(self.client.delete(f'/admin/stations/{station_id}/account',
                                            headers=self.admin_headers).status_code, 400)
        self.assertEqual(self.client.put(f'/admin/stations/{station_id}', headers=self.admin_headers,
                                         json={'username': 'station-a',
                                               'password': 'another-strong-password'}).status_code, 200)
        self.assertEqual(self.client.get('/station/orders',
                                         headers=self.login_station('station-a', 'another-strong-password')).status_code, 200)


if __name__ == '__main__':
    unittest.main()
