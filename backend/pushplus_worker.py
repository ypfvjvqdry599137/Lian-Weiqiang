"""Server-side PushPlus supplier alerts. Run as a single dedicated worker process."""

import logging
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from perk_pushplus import Channel, PushPlusClient, PushPlusError, SendRequest, Template

from app import create_app
from extensions import db
from models import OrderMaster, Supplier, SupplierOrder, SupplierPushNotice
from pushplus_templates import render_notice
from status_utils import supplier_order_block_reason
from sqlalchemy import or_


LOG = logging.getLogger(__name__)
SUPPLIER_URL = 'https://admin.xianpeiju.site/admin-panel/supplier_login.html'
STOP_REASONS = ('订单申请退款，停止备货', '已退款，停止备货',
                '订单已取消，停止备货', '备货单已取消，停止备货')


def activation_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError as exc:
        raise ValueError('PUSHPLUS_ACTIVATED_AT must be an ISO 8601 timestamp with timezone') from exc


def notice_for(supplier_order, kind, topic, reason=None):
    items = '、'.join(f'{item.ingredient_name} {item.quantity}{item.unit}' for item in supplier_order.items[:8])
    title, content = render_notice(kind, {
        'order_sn': supplier_order.order_sn,
        'supplier_order_id': supplier_order.id,
        'items': items,
        'reason': reason or '',
        'supplier_url': SUPPLIER_URL,
    })
    return SupplierPushNotice(
        supplier_order_id=supplier_order.id, kind=kind, topic=topic,
        title=title, content=content,
    )


def current_block_reason(supplier_order):
    if not supplier_order or not supplier_order.order:
        return '备货单不存在'
    if supplier_order.status == 40:
        return '备货单已取消，停止备货'
    return supplier_order_block_reason(supplier_order.order)


def collect_notices(cutoff):
    """Build a durable, deduplicated outbox from committed order state."""
    candidates = (SupplierOrder.query.join(Supplier, Supplier.id == SupplierOrder.supplier_id)
                  .join(OrderMaster, OrderMaster.order_sn == SupplierOrder.order_sn)
                  .filter(OrderMaster.paid_at >= cutoff,
                          SupplierOrder.status.in_([10, 20]),
                          Supplier.is_active.is_(True), Supplier.is_deleted.is_(False),
                          Supplier.pushplus_topic.isnot(None))
                  .order_by(SupplierOrder.id).all())
    for so in candidates:
        if (not so.supplier or not so.supplier.pushplus_topic or not so.order
                or not so.order.paid_at or so.order.paid_at < cutoff
                or so.order.order_status != 20
                or current_block_reason(so)):
            continue
        exists = SupplierPushNotice.query.filter_by(supplier_order_id=so.id, kind='new').first()
        if not exists:
            db.session.add(notice_for(so, 'new', so.supplier.pushplus_topic))
    db.session.commit()

    initial_notices = (SupplierPushNotice.query.filter_by(kind='new')
                       .filter(SupplierPushNotice.created_at >= cutoff).all())
    for first in initial_notices:
        so = first.supplier_order
        if not so or not so.order:
            continue
        reason = current_block_reason(so)
        if reason in STOP_REASONS and not SupplierPushNotice.query.filter_by(
                supplier_order_id=so.id, kind='stop').first():
            db.session.add(notice_for(so, 'stop', first.topic, reason))
    db.session.commit()


@lru_cache(maxsize=1)
def pushplus_client(token):
    return (PushPlusClient.builder().token(token)
            .connect_timeout(5).read_timeout(5).build())


def send_message(token, notice):
    return pushplus_client(token).send(SendRequest(
        title=notice.title, content=notice.content, topic=notice.topic,
        channel=Channel.WECHAT, template=Template.TXT,
    ))


def dispatch_one(token, now=None):
    now = now or datetime.utcnow()
    account_pause = (SupplierPushNotice.query.filter_by(status='pending')
                     .filter(SupplierPushNotice.next_attempt_at > now,
                             or_(SupplierPushNotice.last_error.like('900:%'),
                                 SupplierPushNotice.last_error.like('903:%'),
                                 SupplierPushNotice.last_error.like('905:%')))
                     .first())
    if account_pause:
        return False
    notice = (SupplierPushNotice.query.filter_by(status='pending')
              .filter(SupplierPushNotice.next_attempt_at <= now)
              .order_by(SupplierPushNotice.id).first())
    if not notice:
        return False
    so = notice.supplier_order
    reason = current_block_reason(so)
    if notice.kind not in ('new', 'stop'):
        # Retire hold/resume messages already queued by older worker versions.
        notice.status = 'skipped'
        db.session.commit()
        return False
    if notice.kind == 'new' and (reason or so.status not in (10, 20)
                                 or so.order.order_status != 20):
        notice.status = 'skipped'
        db.session.commit()
        return False
    if notice.kind == 'stop' and reason not in STOP_REASONS:
        notice.status = 'skipped'
        db.session.commit()
        return False

    notice.attempts += 1
    try:
        short_code = send_message(token, notice)
        notice.status = 'accepted'
        notice.pushplus_code = str(short_code or '')[:64] or None
        notice.accepted_at = now
        notice.last_error = None
        LOG.info('PushPlus accepted supplier notice %s, receipt %s', notice.id, notice.pushplus_code)
    except Exception as exc:
        delay = timedelta(hours=24) if isinstance(exc, PushPlusError) and exc.code in (900, 903, 905) else timedelta(seconds=min(3600, 30 * 2 ** min(notice.attempts, 7)))
        notice.next_attempt_at = now + delay
        notice.last_error = str(exc)[:255]
        LOG.warning('PushPlus supplier notice %s failed: %s', notice.id, type(exc).__name__)
    db.session.commit()
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    with app.app_context():
        token = app.config.get('PUSHPLUS_TOKEN')
        try:
            cutoff = activation_time(app.config.get('PUSHPLUS_ACTIVATED_AT'))
        except ValueError as exc:
            LOG.error('%s', exc)
            return
        if not token or not cutoff:
            LOG.info('PushPlus worker idle: configure PUSHPLUS_TOKEN and PUSHPLUS_ACTIVATED_AT')
            return
        next_scan = 0
        while True:
            try:
                if time.monotonic() >= next_scan:
                    collect_notices(cutoff)
                    next_scan = time.monotonic() + 15
                sent = dispatch_one(token)
                db.session.remove()
                time.sleep(2.1 if sent else 5)
            except Exception:
                db.session.rollback()
                db.session.remove()
                LOG.exception('PushPlus worker cycle failed')
                time.sleep(10)


if __name__ == '__main__':
    main()
