"""Confirm unfinished WeChat refunds without initiating any new refund."""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from app import create_app
from extensions import db
from models import ManualRefund, OrderMaster
from wechat_pay_support import WeChatPayError, query_manual_refund, validate_manual_refund


LOG = logging.getLogger(__name__)
PENDING_STATUSES = ('APPLYING', 'PROCESSING', 'ABNORMAL')
ALLOWED_RESULTS = {
    'APPLYING': ('APPLYING', 'PROCESSING', 'SUCCESS', 'CLOSED', 'ABNORMAL'),
    'PROCESSING': ('PROCESSING', 'SUCCESS', 'CLOSED', 'ABNORMAL'),
    'ABNORMAL': ('ABNORMAL', 'SUCCESS'),
}


def pending_refund_ids(after_id=0, limit=20):
    return [row.id for row in (
        ManualRefund.query.filter(ManualRefund.id > after_id,
                                  ManualRefund.status.in_(PENDING_STATUSES),
                                  ManualRefund.out_refund_no.isnot(None))
        .order_by(ManualRefund.id).limit(limit).all()
    )]


def reconcile_one(refund_id):
    refund = db.session.get(ManualRefund, refund_id)
    if not refund or refund.status not in PENDING_STATUSES or not refund.out_refund_no:
        return False
    order = db.session.get(OrderMaster, refund.order_sn)
    if not order or not order.transaction_id:
        LOG.warning('Refund %s has no matching paid order; manual review required', refund_id)
        return False

    out_refund_no = refund.out_refund_no
    order_sn = order.order_sn
    transaction_id = order.transaction_id
    total_amount = order.final_amount
    db.session.rollback()  # Release the read transaction during the remote API request.
    try:
        payload = query_manual_refund(out_refund_no)
        status, amount_fen = validate_manual_refund(
            payload, out_refund_no, order_sn, transaction_id, total_amount
        )
    except WeChatPayError as exc:
        LOG.warning('Could not verify WeChat refund %s: %s', refund_id, exc)
        return False

    order = (OrderMaster.query.filter_by(order_sn=order_sn)
             .populate_existing().with_for_update().first())
    refund = (ManualRefund.query.filter_by(id=refund_id)
              .populate_existing().with_for_update().first())
    if (not order or not refund or refund.status not in PENDING_STATUSES
            or refund.out_refund_no != out_refund_no
            or refund.order_sn != order_sn
            or refund.transaction_id != transaction_id
            or order.transaction_id != transaction_id
            or refund.refund_fen != amount_fen
            or refund.order_total_fen != amount_fen
            or int(Decimal(str(order.final_amount)) * 100) != amount_fen
            or (refund.refund_id and refund.refund_id != payload['refund_id'])
            or status not in ALLOWED_RESULTS[refund.status]):
        db.session.rollback()
        LOG.warning('Refund %s changed or conflicted during verification; manual review required', refund_id)
        return False

    previous_status = refund.status
    refund.refund_id = payload['refund_id']
    refund.status = status
    refund.refund_channel = payload.get('channel') or refund.refund_channel
    refund.success_time = payload.get('success_time') if status == 'SUCCESS' else None
    refund.checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    if status != previous_status:
        LOG.info('Refund %s verified: %s -> %s', refund_id, previous_status, status)
    return status != previous_status


def main():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    with app.app_context():
        cursor = 0
        while True:
            try:
                ids = pending_refund_ids(cursor)
                db.session.remove()
                if not ids:
                    cursor = 0
                for refund_id in ids:
                    try:
                        reconcile_one(refund_id)
                    except Exception:
                        db.session.rollback()
                        LOG.exception('Refund %s reconciliation failed', refund_id)
                    finally:
                        db.session.remove()
                    time.sleep(1)
                if ids:
                    cursor = ids[-1] if len(ids) == 20 else 0
            except Exception:
                db.session.rollback()
                db.session.remove()
                LOG.exception('Refund reconciliation scan failed')
            time.sleep(60)


if __name__ == '__main__':
    main()
