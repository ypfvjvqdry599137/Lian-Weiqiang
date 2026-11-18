import os
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from flask import Flask
from perk_pushplus import HttpResponse, PushPlusClient, PushPlusError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from models import ManualRefund, OrderMaster, Supplier, SupplierOrder, SupplierOrderItem, SupplierPushNotice, SupplierPushTemplate, User
from pushplus_worker import activation_time, collect_notices, dispatch_one, notice_for, send_message


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
        with patch('pushplus_worker.send_message', return_value='receipt-1') as send:
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            send.assert_called_once()
        self.assertEqual(notice.status, 'accepted')
        self.order.order_status = 60
        db.session.commit()
        collect_notices(self.cutoff)
        stop = SupplierPushNotice.query.filter_by(kind='stop').one()
        with patch('pushplus_worker.send_message', return_value='receipt-2'):
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=2)))
        self.assertEqual(stop.status, 'accepted')
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 2)

    def test_refund_request_sends_one_stop_and_never_resumes(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        with patch('pushplus_worker.send_message', return_value='new'):
            dispatch_one('secret-token', self.now + timedelta(minutes=1))

        self.order.refund_status = 10
        db.session.commit()
        collect_notices(self.cutoff)
        stop = SupplierPushNotice.query.filter_by(kind='stop').one()
        self.assertIn('停止备货', stop.content)
        with patch('pushplus_worker.send_message', return_value='stop'):
            dispatch_one('secret-token', self.now + timedelta(minutes=2))

        self.order.refund_status = 0
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 2)

        self.order.refund_status = 30
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='stop').count(), 1)
        self.assertEqual(SupplierPushNotice.query.filter_by(status='accepted').count(), 2)

    def test_refund_request_skips_pending_new_notice(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        self.order.refund_status = 10
        db.session.commit()
        with patch('pushplus_worker.send_message') as send:
            self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            send.assert_not_called()
        self.assertEqual(SupplierPushNotice.query.one().status, 'skipped')
        self.order.refund_status = 30
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='new').count(), 1)
        self.assertEqual(SupplierPushNotice.query.filter_by(kind='stop').count(), 1)
        with patch('pushplus_worker.send_message', return_value='stop') as send:
            self.assertTrue(dispatch_one('secret-token', self.now + timedelta(minutes=6)))
            send.assert_called_once()

    def test_manual_refund_request_stops_preparation_even_if_refund_closes(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.commit()
        collect_notices(self.cutoff)
        with patch('pushplus_worker.send_message', return_value='new'):
            dispatch_one('secret-token', self.now + timedelta(minutes=1))

        refund = ManualRefund(order_sn=self.order.order_sn, transaction_id='test-transaction',
                              order_total_fen=900, refund_fen=900, status='REQUESTED')
        db.session.add(refund)
        db.session.commit()
        collect_notices(self.cutoff)
        stop = SupplierPushNotice.query.filter_by(kind='stop').one()
        self.assertIn('停止备货', stop.content)
        with patch('pushplus_worker.send_message', return_value='stop'):
            dispatch_one('secret-token', self.now + timedelta(minutes=2))
        refund.status = 'CLOSED'
        db.session.commit()
        collect_notices(self.cutoff)
        self.assertEqual(SupplierPushNotice.query.count(), 2)
        self.assertEqual(stop.status, 'accepted')
        from status_utils import supplier_order_block_reason
        self.assertEqual(supplier_order_block_reason(self.order), '订单申请退款，停止备货')

    def test_legacy_pause_and_resume_notices_are_retired(self):
        self.order.order_status = 20
        self.order.paid_at = self.now
        db.session.add_all([
            SupplierPushNotice(supplier_order_id=self.supplier_order.id, kind='hold',
                               topic='vegetables_private', title='旧暂停', content='旧暂停'),
            SupplierPushNotice(supplier_order_id=self.supplier_order.id, kind='resume',
                               topic='vegetables_private', title='旧恢复', content='旧恢复'),
        ])
        db.session.commit()
        # An old queue may still contain these kinds after deployment.
        with patch('pushplus_worker.send_message') as send:
            self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            self.assertFalse(dispatch_one('secret-token', self.now + timedelta(minutes=1)))
            send.assert_not_called()
        self.assertEqual(SupplierPushNotice.query.filter_by(status='skipped').count(), 2)

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
        with patch('pushplus_worker.send_message', side_effect=PushPlusError('limited', code=900)):
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

    def test_official_sdk_sends_to_supplier_topic(self):
        import json

        class FakeHttp:
            def __init__(self):
                self.calls = []

            def execute(self, method, url, headers, body):
                self.calls.append((method, url, json.loads(body)))
                return HttpResponse(200, '{"code":200,"msg":"ok","data":"sdk-receipt"}')

        http = FakeHttp()
        client = PushPlusClient.builder().token('secret-token').http_requester(http).build()
        notice = notice_for(self.supplier_order, 'new', 'vegetables_private')
        with patch('pushplus_worker.pushplus_client', return_value=client):
            self.assertEqual(send_message('secret-token', notice), 'sdk-receipt')
        method, url, body = http.calls[0]
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://www.pushplus.plus/send')
        self.assertEqual(body['token'], 'secret-token')
        self.assertEqual(body['topic'], 'vegetables_private')
        self.assertEqual(body['channel'], 'wechat')
        self.assertEqual(body['template'], 'txt')

    def test_custom_template_changes_new_notice_only(self):
        first = notice_for(self.supplier_order, 'new', 'vegetables_private')
        self.assertEqual(first.title, '鲜配居：新备货单')
        db.session.add(SupplierPushTemplate(kind='new', content='订单 {order_sn}：请备货 {items}'))
        db.session.commit()
        second = notice_for(self.supplier_order, 'new', 'vegetables_private')
        self.assertIn('订单 PUSHPLUS_ORDER：请备货 青菜 2.00斤', second.content)
        self.assertNotEqual(first.content, second.content)
        self.assertEqual(first.title, second.title)


if __name__ == '__main__':
    unittest.main()
