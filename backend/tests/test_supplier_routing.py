import os
import sys
import unittest
from decimal import Decimal

from flask import Flask
import werkzeug
from werkzeug.security import generate_password_hash

if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = '3.0.0'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_routes import admin_bp
from extensions import db
from fulfillment import resolve_ingredient_route, split_order_to_supplier_orders
from fulfillment_admin_routes import fulfillment_admin_bp
from models import (
    Category,
    DeliveryStation,
    DeliveryZone,
    Ingredient,
    OrderItem,
    OrderMaster,
    Product,
    ProductIngredient,
    Supplier,
    SupplierOrder,
    User,
)


class SupplierRoutingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            AUTH_SIGNING_KEY='supplier-test-signing-key-with-more-than-32-chars',
            ADMIN_PASSWORD_HASH=generate_password_hash('admin-test-password'),
        )
        db.init_app(self.app)
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(fulfillment_admin_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()
        token = self.client.post('/admin/auth/login', json={'password': 'admin-test-password'}).get_json()['token']
        self.headers = {'Authorization': f'Bearer {token}'}

        self.vegetables = Category(name='蔬菜')
        self.meat = Category(name='肉类')
        self.zone = DeliveryZone(
            zone_name='测试区域', center_lng=Decimal('118.7'), center_lat=Decimal('24.8'), radius=3000
        )
        db.session.add_all((self.vegetables, self.meat, self.zone))
        db.session.flush()
        self.station = DeliveryStation(zone_id=self.zone.id, station_name='测试配送站')
        db.session.add(self.station)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def create_supplier(self, name, username, category_id):
        response = self.client.post('/admin/suppliers', headers=self.headers, json={
            'name': name,
            'username': username,
            'password': 'supplier-test-password',
            'service_zone_ids': [self.zone.id],
            'supply_category_ids': [category_id],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['id']

    def test_supplier_categories_are_saved_and_can_be_edited(self):
        supplier_id = self.create_supplier('蔬菜供应商', 'vegetable-supplier', self.vegetables.id)
        db.session.expire_all()
        response = self.client.get(f'/admin/suppliers/{supplier_id}', headers=self.headers)
        self.assertEqual(response.get_json()['supply_category_ids'], [self.vegetables.id])

        response = self.client.put(f'/admin/suppliers/{supplier_id}', headers=self.headers, json={
            'supply_category_ids': [self.vegetables.id, self.meat.id],
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        db.session.expire_all()
        saved = self.client.get(f'/admin/suppliers/{supplier_id}', headers=self.headers).get_json()
        self.assertEqual(saved['supply_category_ids'], [self.vegetables.id, self.meat.id])

        duplicate = self.client.post('/admin/suppliers', headers=self.headers, json={
            'name': '重复账号', 'username': 'vegetable-supplier', 'password': 'another-password',
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn('已存在', duplicate.get_json()['message'])

        retired = Supplier(name='已删除供应商', username='retired-supplier', password='unused', is_deleted=True)
        db.session.add(retired)
        db.session.commit()
        reused = self.client.post('/admin/suppliers', headers=self.headers, json={
            'name': '复用旧账号', 'username': 'retired-supplier', 'password': 'another-password',
        })
        self.assertEqual(reused.status_code, 409)
        self.assertIn('已存在', reused.get_json()['message'])

    def test_rule_does_not_route_vegetables_to_meat_supplier(self):
        vegetables_id = self.create_supplier('蔬菜供应商', 'vegetable-supplier', self.vegetables.id)
        meat_id = self.create_supplier('肉类供应商', 'meat-supplier', self.meat.id)
        ingredient = Ingredient(
            name='青菜', unit='份', category_id=self.vegetables.id,
            supplier_id=vegetables_id, stock=10,
        )
        db.session.add(ingredient)
        db.session.commit()
        wrong_rule = self.client.post('/admin/zone-supply-rules', headers=self.headers, json={
            'zone_id': self.zone.id,
            'station_id': self.station.id,
            'category_id': self.vegetables.id,
            'supplier_id': meat_id,
        })
        self.assertEqual(wrong_rule.status_code, 400, wrong_rule.get_json())
        self.assertIn('供货品类', wrong_rule.get_json()['message'])

        valid_rule = self.client.post('/admin/zone-supply-rules', headers=self.headers, json={
            'zone_id': self.zone.id,
            'station_id': self.station.id,
            'category_id': self.vegetables.id,
            'supplier_id': vegetables_id,
        })
        self.assertEqual(valid_rule.status_code, 201, valid_rule.get_json())
        rule_id = valid_rule.get_json()['id']
        invalid_update = self.client.put(f'/admin/zone-supply-rules/{rule_id}', headers=self.headers, json={
            'supplier_id': meat_id,
        })
        self.assertEqual(invalid_update.status_code, 400, invalid_update.get_json())
        saved_rule = self.client.get(f'/admin/zone-supply-rules/{rule_id}', headers=self.headers).get_json()
        self.assertEqual(saved_rule['supplier_id'], vegetables_id)

        route = resolve_ingredient_route(ingredient, self.zone)
        self.assertEqual(route['supplier'].id, vegetables_id)
        self.assertEqual(route['source'], 'zone_rule')

    def test_product_without_ingredients_creates_fulfillment_issue(self):
        user = User(openid='missing-recipe-user')
        product = Product(name='未配原料商品', price=Decimal('8.00'), unit='份')
        db.session.add_all((user, product))
        db.session.flush()
        order = OrderMaster(order_sn='MISSING_RECIPE_ORDER', user_id=user.id, zone_id=self.zone.id)
        db.session.add(order)
        db.session.add(OrderItem(
            order_sn=order.order_sn, product_id=product.id, product_name=product.name,
            price=product.price, quantity=1, unit=product.unit,
        ))
        db.session.commit()

        result = split_order_to_supplier_orders(order.order_sn)
        db.session.commit()
        self.assertEqual(result['supplier_order_count'], 0)
        self.assertEqual([issue['issue_type'] for issue in result['issues']], ['missing_ingredient'])

    def test_mixed_product_generates_one_supply_order_per_category_supplier(self):
        vegetables_id = self.create_supplier('蔬菜供应商', 'vegetable-supplier', self.vegetables.id)
        meat_id = self.create_supplier('肉类供应商', 'meat-supplier', self.meat.id)
        for category_id, supplier_id in ((self.vegetables.id, vegetables_id), (self.meat.id, meat_id)):
            response = self.client.post('/admin/zone-supply-rules', headers=self.headers, json={
                'zone_id': self.zone.id,
                'station_id': self.station.id,
                'category_id': category_id,
                'supplier_id': supplier_id,
                'is_primary': True,
            })
            self.assertEqual(response.status_code, 201, response.get_json())

        user = User(openid='supplier-routing-user')
        product = Product(name='蔬菜肉类组合', price=Decimal('20.00'), unit='份')
        vegetables = Ingredient(
            name='青菜', unit='份', category_id=self.vegetables.id,
            supplier_id=vegetables_id, stock=10,
        )
        meat = Ingredient(
            name='猪肉', unit='份', category_id=self.meat.id,
            supplier_id=meat_id, stock=10,
        )
        db.session.add_all((user, product, vegetables, meat))
        db.session.flush()
        db.session.add_all((
            ProductIngredient(product_id=product.id, ingredient_id=vegetables.id, quantity_needed=Decimal('1')),
            ProductIngredient(product_id=product.id, ingredient_id=meat.id, quantity_needed=Decimal('2')),
        ))
        order = OrderMaster(
            order_sn='MIXED_SUPPLIER_ORDER', user_id=user.id, zone_id=self.zone.id,
            order_status=20, total_amount=Decimal('20.00'), final_amount=Decimal('20.00'),
        )
        db.session.add(order)
        db.session.add(OrderItem(
            order_sn=order.order_sn, product_id=product.id, product_name=product.name,
            price=product.price, quantity=1, unit=product.unit,
        ))
        db.session.commit()

        result = split_order_to_supplier_orders(order.order_sn)
        db.session.commit()
        self.assertEqual(result['supplier_order_count'], 2)
        self.assertEqual(result['issues'], [])
        orders = SupplierOrder.query.filter_by(order_sn=order.order_sn).all()
        self.assertEqual({item.supplier_id: [part.ingredient_name for part in item.items] for item in orders}, {
            vegetables_id: ['青菜'],
            meat_id: ['猪肉'],
        })


if __name__ == '__main__':
    unittest.main()
