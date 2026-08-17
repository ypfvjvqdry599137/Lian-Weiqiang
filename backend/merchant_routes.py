from flask import Blueprint, request, jsonify
from extensions import db
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256

merchant_bp = Blueprint('merchant', __name__, url_prefix='/merchant')
BUSINESS_TZ = timezone(timedelta(hours=8))



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


def money(value):
    return value if value is not None else Decimal('0')


def to_business_datetime(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TZ)


def get_month_range(month_value):
    now = datetime.now(BUSINESS_TZ)
    if month_value:
        try:
            year, month = [int(part) for part in month_value.split('-', 1)]
            start_local = datetime(year, month, 1, tzinfo=BUSINESS_TZ)
        except (ValueError, TypeError):
            return None
    else:
        start_local = datetime(now.year, now.month, 1, tzinfo=BUSINESS_TZ)

    if start_local.month == 12:
        end_local = datetime(start_local.year + 1, 1, 1, tzinfo=BUSINESS_TZ)
    else:
        end_local = datetime(start_local.year, start_local.month + 1, 1, tzinfo=BUSINESS_TZ)

    return start_local, end_local, start_local.strftime('%Y-%m')


def get_supplier_order_item_total(item):
    if item.total_price is not None:
        return item.total_price

    unit_price = item.unit_price
    if unit_price is None and item.ingredient:
        unit_price = item.ingredient.price
    if unit_price is None:
        return Decimal('0')
    return item.quantity * unit_price


def get_supplier_order_total(order):
    if order.status == 40:
        return Decimal('0')
    return sum((get_supplier_order_item_total(item) for item in order.items), Decimal('0'))


def get_order_supplier_cost(order):
    return sum((get_supplier_order_total(supplier_order) for supplier_order in order.supplier_orders), Decimal('0'))


def serialize_order(order, include_items=True, include_supplier_orders=True):
    station = order.zone.station if order.zone and order.zone.station else None
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
        'station_id': station.id if station else None,
        'station_name': station.station_name if station else None,
        'station_address': station.address if station else None,
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


@merchant_bp.route('/settlement', methods=['GET'])
def get_merchant_settlement():
    from models import OrderMaster
    zone, error = require_merchant_zone()
    if error:
        return error

    month_range = get_month_range(request.args.get('month'))
    if month_range is None:
        return jsonify({'message': '月份格式错误，请使用 YYYY-MM'}), 400

    start_local, end_local, normalized_month = month_range
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)

    orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone.id,
        OrderMaster.created_at >= start_utc,
        OrderMaster.created_at < end_utc
    ).order_by(OrderMaster.created_at.desc()).all()

    completed_statuses = [40, 50]
    pending_statuses = [10, 20, 30]
    summary = {
        'month': normalized_month,
        'zone_id': zone.id,
        'zone_name': zone.zone_name,
        'order_count': len(orders),
        'completed_count': 0,
        'pending_count': 0,
        'canceled_count': 0,
        'total_sales': Decimal('0'),
        'settled_sales': Decimal('0'),
        'pending_sales': Decimal('0'),
        'delivery_fee_total': Decimal('0'),
        'final_amount_total': Decimal('0')
    }
    daily_totals = {}
    orders_output = []

    for order in orders:
        order_total = money(order.total_amount)
        delivery_fee = money(order.delivery_fee)
        final_amount = money(order.final_amount)

        created_at = to_business_datetime(order.created_at) if order.created_at else None
        day_key = created_at.strftime('%Y-%m-%d') if created_at else '未记录日期'
        daily = daily_totals.setdefault(day_key, {
            'date': day_key,
            'order_count': 0,
            'completed_count': 0,
            'pending_count': 0,
            'canceled_count': 0,
            'settled_sales': Decimal('0'),
            'delivery_fee_total': Decimal('0')
        })

        daily['order_count'] += 1
        if order.order_status == 60:
            summary['canceled_count'] += 1
            daily['canceled_count'] += 1
        else:
            summary['total_sales'] += order_total


        if order.order_status in completed_statuses:
            summary['completed_count'] += 1
            summary['settled_sales'] += order_total
            summary['delivery_fee_total'] += delivery_fee
            summary['final_amount_total'] += final_amount

            daily['completed_count'] += 1
            daily['settled_sales'] += order_total
            daily['delivery_fee_total'] += delivery_fee
        elif order.order_status in pending_statuses:
            summary['pending_count'] += 1
            summary['pending_sales'] += order_total
            daily['pending_count'] += 1

        orders_output.append({
            'order_sn': order.order_sn,
            'status': order.order_status,
            'status_text': get_order_status_text(order.order_status),
            'receiver_name': order.receiver_name,
            'receiver_phone': order.receiver_phone,
            'total_amount': str(order_total),
            'delivery_fee': str(delivery_fee),
            'final_amount': str(final_amount),

            'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else None
        })


    summary_output = {key: (str(value) if isinstance(value, Decimal) else value) for key, value in summary.items()}
    daily_output = [
        {key: (str(value) if isinstance(value, Decimal) else value) for key, value in item.items()}
        for _, item in sorted(daily_totals.items(), reverse=True)
    ]

    return jsonify({
        'month': normalized_month,
        'summary': summary_output,
        'daily_totals': daily_output,
        'orders': orders_output
    }), 200


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

    return jsonify({'message': '已送达'}), 200


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