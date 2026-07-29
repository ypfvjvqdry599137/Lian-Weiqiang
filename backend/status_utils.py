def get_order_status_text(status):
    return {
        10: '待付款',
        20: '待配货',
        30: '配送中',
        40: '已送达',
        50: '已完成',
        60: '已取消'
    }.get(status, '未知')


def get_supplier_order_status_text(status):
    return {
        10: '待备货',
        20: '备货中',
        30: '已完成',
        40: '已取消'
    }.get(status, '未知')


def sync_order_status_after_supplier_update(order_sn):
    from models import OrderMaster, SupplierOrder

    order = OrderMaster.query.get(order_sn)
    if not order:
        return None, False

    supplier_orders = SupplierOrder.query.filter_by(order_sn=order_sn).all()
    active_supplier_orders = [item for item in supplier_orders if item.status != 40]
    all_ready = active_supplier_orders and all(item.status == 30 for item in active_supplier_orders)

    if all_ready and order.order_status in [10, 20]:
        order.order_status = 20
        return order, True

    return order, False
