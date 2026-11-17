import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from models import ManualRefund, OrderMaster, User
from refund_reconcile_worker import pending_refund_ids, reconcile_one
from status_utils import display_order_status
from wechat_pay_support import WeChatPayError


class RefundReconcileWorkerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://',
                               SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(openid='refund-test-user')
        db.session.add(user)
        db.session.flush()
        self.order = OrderMaster(order_sn='REFUND_SYNC_TEST', user_id=user.id,
                                 order_status=20, final_amount=Decimal('2.90'),
                                 transaction_id='wechat-transaction')
        self.refund = ManualRefund(order_sn=self.order.order_sn, out_refund_no='AR-TEST',
                                   transaction_id='wechat-transaction', order_total_fen=290,
                                   refund_fen=290, status='PROCESSING')
        db.session.add_all((self.order, self.refund))
        db.session.commit()
        self.refund_id = self.refund.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def payload(self, status='SUCCESS'):
        return {
            'out_refund_no': 'AR-TEST', 'out_trade_no': 'REFUND_SYNC_TEST',
            'transaction_id': 'wechat-transaction', 'refund_id': 'wx-refund-id',
            'status': status, 'amount': {'total': 290, 'refund': 290, 'currency': 'CNY'},
            'success_time': '2026-11-17T14:00:00+08:00' if status == 'SUCCESS' else None,
            'channel': 'ORIGINAL',
        }

    def test_successful_query_updates_order_and_stops_future_polling(self):
        self.assertEqual(pending_refund_ids(), [self.refund_id])
        with patch('refund_reconcile_worker.query_manual_refund', return_value=self.payload()) as query:
            self.assertTrue(reconcile_one(self.refund_id))
            query.assert_called_once_with('AR-TEST')
        db.session.expire_all()
        self.assertEqual(db.session.get(ManualRefund, self.refund_id).status, 'SUCCESS')
        self.assertEqual(display_order_status(db.session.get(OrderMaster, self.order.order_sn)), 70)
        self.assertEqual(pending_refund_ids(), [])

    def test_mismatched_wechat_result_never_marks_success(self):
        payload = self.payload()
        payload['transaction_id'] = 'another-transaction'
        with patch('refund_reconcile_worker.query_manual_refund', return_value=payload):
            self.assertFalse(reconcile_one(self.refund_id))
        db.session.expire_all()
        self.assertEqual(db.session.get(ManualRefund, self.refund_id).status, 'PROCESSING')
        self.assertEqual(display_order_status(db.session.get(OrderMaster, self.order.order_sn)), 20)

    def test_query_error_keeps_pending_status(self):
        with patch('refund_reconcile_worker.query_manual_refund', side_effect=WeChatPayError('timeout')):
            self.assertFalse(reconcile_one(self.refund_id))
        self.assertEqual(db.session.get(ManualRefund, self.refund_id).status, 'PROCESSING')

    def test_stale_processing_result_cannot_overwrite_success(self):
        def admin_updated_refund(_):
            row = db.session.get(ManualRefund, self.refund_id)
            row.status = 'SUCCESS'
            db.session.commit()
            return self.payload('PROCESSING')

        with patch('refund_reconcile_worker.query_manual_refund', side_effect=admin_updated_refund):
            self.assertFalse(reconcile_one(self.refund_id))
        db.session.expire_all()
        self.assertEqual(db.session.get(ManualRefund, self.refund_id).status, 'SUCCESS')


if __name__ == '__main__':
    unittest.main()
