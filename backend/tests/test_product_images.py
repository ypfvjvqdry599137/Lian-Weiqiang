import io
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from flask import Flask
from PIL import Image
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_routes import admin_bp
from auth import issue_token
from client_routes import client_bp
from extensions import db
from models import Product
from product_images import thumbnail_url


class ProductImageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            UPLOAD_FOLDER=self.temp_dir.name,
            AUTH_SIGNING_KEY='product-image-test-signing-key-with-32-chars',
            ADMIN_PASSWORD_HASH=generate_password_hash('image-test-password'),
        )
        db.init_app(self.app)
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(client_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()
        token = issue_token('admin', 1, self.app.config['ADMIN_PASSWORD_HASH'])
        self.admin_headers = {'Authorization': f'Bearer {token}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_upload_creates_two_jpegs_and_client_lists_thumbnail(self):
        image = Image.new('RGBA', (2000, 1600), (20, 120, 40, 180))
        data = io.BytesIO()
        image.save(data, format='PNG')
        data.seek(0)

        response = self.client.post(
            '/admin/uploads/product-image',
            data={'image': (data, 'vegetable.png')},
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        detail_path = Path(self.temp_dir.name) / payload['path'].lstrip('/').removeprefix('uploads/')
        thumb_path = Path(self.temp_dir.name) / 'products' / payload['thumbnail_url'].rsplit('/', 1)[-1]
        self.assertTrue(detail_path.is_file())
        self.assertTrue(thumb_path.is_file())
        with Image.open(detail_path) as detail, Image.open(thumb_path) as thumb:
            self.assertEqual(detail.format, 'JPEG')
            self.assertEqual(thumb.format, 'JPEG')
            self.assertLessEqual(max(detail.size), 1200)
            self.assertLessEqual(max(thumb.size), 600)

        db.session.add(Product(name='vegetable', price=Decimal('5'), image_url=payload['image_url']))
        db.session.commit()
        listed = self.client.get('/client/products?page=1&page_size=20').get_json()['products'][0]
        self.assertEqual(listed['thumbnail_url'], payload['thumbnail_url'])

    def test_pagination_is_opt_in_for_older_clients(self):
        db.session.add_all(
            Product(name=f'product-{index}', price=Decimal('5')) for index in range(3)
        )
        db.session.commit()

        self.assertEqual(len(self.client.get('/client/products').get_json()['products']), 3)
        first = self.client.get('/client/products?page=1&page_size=2').get_json()
        second = self.client.get('/client/products?page=2&page_size=2').get_json()
        self.assertEqual(len(first['products']), 2)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(second['products']), 1)
        self.assertFalse(second['has_more'])
        self.assertEqual(self.client.get('/client/products?page=0').status_code, 400)
        self.assertEqual(self.client.get('/client/products?page=oops').status_code, 400)

    def test_legacy_and_external_image_urls_are_preserved(self):
        self.assertEqual(thumbnail_url('https://example.com/vegetable.png'), 'https://example.com/vegetable.png')
        self.assertEqual(thumbnail_url('/uploads/products/old.jpg'), '/uploads/products/old.jpg')
