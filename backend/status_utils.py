def get_order_status_text(status):
    return {
        10: '待付款',
        20: '待配货',
        30: '配送中',
        40: '已送达',
        50: '已完成',
        60: '已取消',
        70: '已退款',
    }.get(status, '未知')


def get_supplier_order_status_text(status):
    return {
        10: '待备货',
        20: '备货中',
        30: '已完成',
        40: '已取消'
    }.get(status, '未知')


def latest_manual_refund(order):
    refunds = sorted(order.manual_refunds, key=lambda item: item.id or 0, reverse=True)
    return refunds[0] if refunds else None


def display_order_status(order):
    if any(refund.status == 'SUCCESS' and refund.refund_fen == refund.order_total_fen
           for refund in order.manual_refunds):
        return 70
    return order.order_status


def manual_refund_status_text(order):
    if display_order_status(order) == 70:
        return None
    refund = latest_manual_refund(order)
    if not refund:
        return None
    return {
        'REQUESTED': '待人工退款，配送已暂停',
        'APPLYING': '退款申请待确认，配送已暂停',
        'PROCESSING': '退款处理中',
        'SUCCESS': '退款成功',
        'CLOSED': '退款已关闭',
        'ABNORMAL': '退款异常，请联系客服',
    }.get(refund.status)


def has_refund_hold(order):
    if order.refund_status in (10, 20, 30):
        return True
    return any(refund.status != 'CLOSED' for refund in order.manual_refunds)


def serialize_manual_refund(refund):
    return {
        'id': refund.id,
        'out_refund_no': refund.out_refund_no,
        'refund_id': refund.refund_id,
        'refund_fen': refund.refund_fen,
        'status': refund.status,
        'refund_channel': refund.refund_channel,
        'operator_note': refund.operator_note,
        'checked_at': refund.checked_at.isoformat() if refund.checked_at else None,
        'success_time': refund.success_time,
    }


def sync_order_status_after_supplier_update(order_sn):
    from models import OrderMaster, SupplierOrder

    order = OrderMaster.query.get(order_sn)
    if not order:
        return None, False

    supplier_orders = SupplierOrder.query.filter_by(order_sn=order_sn).all()
    active_supplier_orders = [item for item in supplier_orders if item.status != 40]
    all_ready = active_supplier_orders and all(item.status == 30 for item in active_supplier_orders)

    if all_ready and order.order_status in [10, 20] and not has_refund_hold(order):
        order.order_status = 20
        return order, True

    return order, False
