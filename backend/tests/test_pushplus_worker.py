import os
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from models import OrderMaster, Supplier, SupplierOrder, SupplierOrderItem, SupplierPushNotice, User
from pushplus_worker import activation_time, collect_notices, dispatch_one


class PushplusWorkerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.now = datetime.utcnow().replace(microsecond=0)
        self.cutoff = self.now - timedelta(minutes=1)
        user = User(openid='pushplus-test')
        supplier = Supplier(name='蔬菜供应商', username='pushplus-supplier', password='test',
                            is_active=True, pushplus_topic='vegetables_private')
        db.session.add_all([user, supplier])
        db.session.flush()
        order = OrderMaster(order_sn='PUSHPLUS_ORDER', user_id=user.id, order_status=10,
                            total_amount=Decimal('9.00'), delivery_fee=Decimal('0'),
                            final_amount=Decimal('9.00'), receiver_phone='13900000000',
                            receiver_address='private delivery address')
        db.session.add(order)
        db.session.flush()
        supplier_order = SupplierOrder(order_sn=order.order_sn, supplier_id=supplier.id, status=10,
                                       created_at=self.now)
        db.session.add(supplier_order)
        db.session.flush()
        db.session.add(SupplierOrderItem(supplier_order_id=supplier_order.id, ingredient_id=1,
                                         ingredient_name='青菜', quantity=Decimal('2'), unit='斤'))
        db.session.commit()
        self.order = order
        self.supplier_order = supplier_order

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_paid_order_is_sent_once_and_cancellation_is_notified(self):
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 0)
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 1)
        notice = SupplierPushNotice.query.one()
        self.assertEqual(notice.topic, 'vegetables_private')
        self.assertNotIn('13900000000', notice.content)
        self.assertNotIn('private delivery address', notice.content)
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'receipt-1'}) as send:
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            send.assert_called_once()
        self.assertEqual(notice.status, 'accepted')
        self.order.order_status = 60
        db.session.commit()
        collect_notices(self.cutoff)
        stop = SupplierPushNotice.query.filter_by(kind='stop').one()
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'receipt-2'}):
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=2)))
        self.assertEqual(stop.status, 'accepted')
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 2)

    def test_refund_hold_resume_and_success_stop(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'new'}):
            dispatch_one('secret-token', self.now + timedelta(minutes=1))

        self.order.refund_status = 10
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='hold').count(), 1)
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'hold'}):
            dispatch_one('secret-token', self.now + timedelta(minutes=2))

        self.order.refund_status = 0
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='resume').count(), 1)
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'resume'}):
            dispatch_one('secret-token', self.now + timedelta(minutes=3))

        self.order.refund_status = 30
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='stop').count(), 1)
        with patch('pushplus_worker.send_message', return_value={'code': 200, 'data': 'stop'}):
            dispatch_one('secret-token', self.now + timedelta(minutes=4))
        self.assertEqual(SupplierPushNotice.query.filter_by(status='accepted').count(), 4)

    def test_refund_hold_suppresses_pending_new_notice(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        self.order.refund_status = 10
        db.session.commit()
        with patch('pushplus_worker.send_message') as send:
            self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            send.assert_not_called()
        self.assertEqual(SupplierPushNotice.query.one().status, 'pending')
        self.order.refund_status = 30
        db.session.commit()
        self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=6)))
        self.assertEqual(SupplierPushNotice.query.one().status, 'skipped')

    def test_old_unpaid_order_paid_after_activation_is_notified(self):
        self.supplier_order.created_at = self.cutoff - timedelta(days=1)
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='new').count(), 1)

    def test_paid_before_activation_is_not_backfilled(self):
        self.order.order_status = 20
        self.order.paid_at = self.cutoff - timedelta(seconds=1)
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 0)

    def test_failed_request_retries_without_blocking_order(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        with patch('pushplus_worker.send_message', return_value={'code': 900, 'msg': 'limited'}):
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
        notice = SupplierPushNotice.query.one()
        self.assertEqual(notice.status, 'pending')
        self.assertGreater(notice.next_attempt_at, self.now + timedelta(hours=23))
        with patch('pushplus_worker.send_message') as send:
            self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=2)))
            send.assert_not_called()

    def test_activation_requires_timezone(self):
        self.assertEqual(activation_time('2026-11-17T08:00:00+08:00'), datetime(2026, 11, 17))
        with self.assertRaises(ValueError):
            activation_time('2026-11-17T08:00:00')


if __name__ == '__main__':
    unittest.main()
