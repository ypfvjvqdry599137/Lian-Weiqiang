from flask import Blueprint, request, jsonify
from extensions import db
from datetime import date
from hashlib import sha256

merchant_bp = Blueprint('merchant', __name__, url_prefix='/merchant')


def get_merchant_key(zone):
    raw = f"{zone.id}:{zone.merchant_username or ''}:{zone.merchant_password or ''}:fresh-produce-merchant"
    return sha256(raw.encode('utf-8')).hexdigest()


def get_zone_by_merchant(username, password):
    from models import DeliveryZone
    zone = DeliveryZone.query.filter_by(merchant_username=username).first()
    if zone and zone.merchant_password == password and zone.is_active:
        return zone
    return None


def require_merchant_zone():
    from models import DeliveryZone
    zone_id = request.args.get('zone_id')
    merchant_key = request.args.get('merchant_key') or request.headers.get('X-Merchant-Key')

    if not zone_id or not str(zone_id).isdigit() or not merchant_key:
        return None, (jsonify({'message': '请先登录区域配送后台'}), 401)

    zone = DeliveryZone.query.get(int(zone_id))
    if not zone or not zone.is_active or get_merchant_key(zone) != merchant_key:
        return None, (jsonify({'message': '登录已失效，请重新登录'}), 401)

    return zone, None


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


def are_supplier_orders_ready(order):
    if not order.supplier_orders:
        return True
    return all(supplier_order.status == 30 for supplier_order in order.supplier_orders)


def serialize_order(order, include_items=True, include_supplier_orders=True):
    data = {
        'order_sn': order.order_sn,
        'order_status': order.order_status,
        'status_text': get_order_status_text(order.order_status),
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'receiver_address': order.receiver_address,
        'remark': order.remark,
        'total_amount': str(order.total_amount),
        'delivery_fee': str(order.delivery_fee),
        'final_amount': str(order.final_amount),
        'supplier_ready': are_supplier_orders_ready(order),
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else None
    }

    if include_items:
        data['items'] = [
            {
                'product_name': item.product_name,
                'product_image': item.product_image,
                'price': str(item.price),
                'quantity': item.quantity,
                'unit': item.unit
            }
            for item in order.items
        ]

    if include_supplier_orders:
        data['supplier_orders'] = [
            {
                'id': supplier_order.id,
                'supplier_name': supplier_order.supplier.name if supplier_order.supplier else None,
                'status': supplier_order.status,
                'status_text': get_supplier_order_status_text(supplier_order.status)
            }
            for supplier_order in order.supplier_orders
        ]

    return data


@merchant_bp.route('/login', methods=['POST'])
def merchant_login():
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400

    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({'message': '请输入账号和密码'}), 400

    zone = get_zone_by_merchant(username, password)
    if not zone:
        return jsonify({'message': '账号或密码错误，或该配送区域已禁用'}), 401

    return jsonify({
        'message': '登录成功',
        'zone_id': zone.id,
        'zone_name': zone.zone_name,
        'merchant_key': get_merchant_key(zone)
    }), 200


@merchant_bp.route('/dashboard/today-arrival', methods=['GET'])
def get_today_arrival():
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone.id,
        OrderMaster.order_status.in_([20, 30])
    ).all()

    product_summary = {}
    for order in orders:
        for item in order.items:
            product = product_summary.setdefault(item.product_id, {
                'product_id': item.product_id,
                'product_name': item.product_name,
                'product_image': item.product_image,
                'unit': item.unit,
                'total_quantity': 0
            })
            product['total_quantity'] += item.quantity

    return jsonify({
        'total_orders': len(orders),
        'ready_orders': len([order for order in orders if are_supplier_orders_ready(order)]),
        'products': list(product_summary.values())
    }), 200


@merchant_bp.route('/dashboard/delivering', methods=['GET'])
def get_delivering():
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    orders = OrderMaster.query.filter_by(
        zone_id=zone.id,
        order_status=30
    ).order_by(OrderMaster.created_at.desc()).all()

    return jsonify({'orders': [serialize_order(order) for order in orders]}), 200


@merchant_bp.route('/orders', methods=['GET'])
def get_merchant_orders():
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    status = (request.args.get('status') or 'all').strip().lower()
    keyword = (request.args.get('keyword') or '').strip()

    query = OrderMaster.query.filter_by(zone_id=zone.id)
    status_map = {
        'pending': 20,
        'delivering': 30,
        'delivered': 40,
        'completed': 50,
        'canceled': 60,
        '10': 10,
        '20': 20,
        '30': 30,
        '40': 40,
        '50': 50,
        '60': 60
    }
    if status != 'all':
        status_value = status_map.get(status)
        if status_value is None:
            return jsonify({'message': '订单状态不正确'}), 400
        query = query.filter_by(order_status=status_value)

    if keyword:
        query = query.filter(
            (OrderMaster.receiver_name.contains(keyword)) |
            (OrderMaster.receiver_phone.contains(keyword)) |
            (OrderMaster.order_sn.contains(keyword)) |
            (OrderMaster.receiver_address.contains(keyword))
        )

    orders = query.order_by(OrderMaster.created_at.desc()).all()
    return jsonify({'orders': [serialize_order(order) for order in orders]}), 200


@merchant_bp.route('/orders/<order_sn>', methods=['GET'])
def get_merchant_order_detail(order_sn):
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone.id
    ).first_or_404()

    return jsonify(serialize_order(order)), 200


@merchant_bp.route('/orders/<order_sn>/start-delivery', methods=['POST'])
def start_delivery(order_sn):
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone.id
    ).first_or_404()

    if order.order_status != 20:
        return jsonify({'message': '订单状态异常，无法开始配送'}), 400
    if not are_supplier_orders_ready(order):
        return jsonify({'message': '供应商备货未全部完成，暂不能开始配送'}), 400

    order.order_status = 30
    db.session.commit()

    return jsonify({'message': '已开始配送'}), 200


@merchant_bp.route('/orders/<order_sn>/confirm-delivery', methods=['POST'])
def confirm_delivery(order_sn):
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone.id
    ).first_or_404()

    if order.order_status != 30:
        return jsonify({'message': '订单状态异常，无法确认送达'}), 400

    order.order_status = 40
    db.session.commit()

    return jsonify({'message': '已确认送达'}), 200


@merchant_bp.route('/statistics', methods=['GET'])
def get_statistics():
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    today = date.today()

    today_created_orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone.id,
        OrderMaster.order_status != 60,
        db.func.date(OrderMaster.created_at) == today
    ).all()
    today_finished_orders = [order for order in today_created_orders if order.order_status in [40, 50]]

    month_start = today.replace(day=1)
    month_orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone.id,
        OrderMaster.order_status.in_([40, 50]),
        OrderMaster.created_at >= month_start
    ).all()

    pending_count = OrderMaster.query.filter_by(zone_id=zone.id, order_status=20).count()
    delivering_count = OrderMaster.query.filter_by(zone_id=zone.id, order_status=30).count()

    return jsonify({
        'zone_id': zone.id,
        'zone_name': zone.zone_name,
        'today_revenue': str(sum((order.total_amount for order in today_finished_orders if order.total_amount), 0)),
        'today_order_count': len(today_created_orders),
        'month_revenue': str(sum((order.total_amount for order in month_orders if order.total_amount), 0)),
        'pending_count': pending_count,
        'delivering_count': delivering_count
    }), 200