from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

from auth import STAFF_TOKEN_AGE, issue_token, read_token, token_binding
from extensions import db
from status_utils import display_order_status, get_order_status_text, manual_refund_status_text


station_bp = Blueprint('station', __name__, url_prefix='/station')


def station_token_binding(station):
    return f'{station.zone_id}:{station.username}:{station.password_hash}'


@station_bp.before_request
def authenticate_station():
    if request.method == 'OPTIONS' or request.endpoint == 'station.login':
        return None

    from models import DeliveryStation

    payload = read_token('station', STAFF_TOKEN_AGE)
    if not payload:
        return jsonify({'message': '请先登录配送站后台'}), 401
    station = db.session.get(DeliveryStation, payload['sub'])
    if (not station or not station.is_active or not station.zone or not station.zone.is_active
            or not station.username or not station.password_hash
            or payload['bind'] != token_binding(station_token_binding(station))):
        return jsonify({'message': '登录已失效，请重新登录'}), 401
    g.station = station
    return None


@station_bp.after_request
def disable_private_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@station_bp.route('/login', methods=['POST'])
def login():
    from models import DeliveryStation

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'message': '请输入账号和密码'}), 400
    username = data.get('username')
    password = data.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        return jsonify({'message': '请输入账号和密码'}), 400

    station = DeliveryStation.query.filter_by(username=username.strip()).first()
    if not station or not station.password_hash or not check_password_hash(station.password_hash, password):
        return jsonify({'message': '账号或密码错误'}), 401
    if not station.is_active or not station.zone or not station.zone.is_active:
        return jsonify({'message': '配送站账号已停用'}), 403
    return jsonify({
        'token': issue_token('station', station.id, station_token_binding(station)),
        'station_name': station.station_name,
        'zone_name': station.zone.zone_name,
    }), 200


@station_bp.route('/profile', methods=['GET'])
def profile():
    station = g.station
    return jsonify({
        'station_name': station.station_name,
        'zone_name': station.zone.zone_name,
    }), 200


@station_bp.route('/orders', methods=['GET'])
def orders():
    from models import ManualRefund, OrderMaster

    status = (request.args.get('status') or 'all').strip().lower()
    status_map = {
        'all': None, 'pending': 20, 'delivering': 30,
        'delivered': 40, 'completed': 50, 'canceled': 60, 'refunded': 70,
    }
    if status not in status_map:
        return jsonify({'message': '订单状态不正确'}), 400
    page_value = request.args.get('page', '1')
    if not page_value.isdigit() or len(page_value) > 6 or int(page_value) < 1:
        return jsonify({'message': '页码不正确'}), 400
    page = int(page_value)

    query = OrderMaster.query.filter(
        OrderMaster.zone_id == g.station.zone_id,
        OrderMaster.order_status != 10,
    )
    full_refund = OrderMaster.manual_refunds.any(
        (ManualRefund.status == 'SUCCESS') & (ManualRefund.refund_fen == ManualRefund.order_total_fen)
    )
    if status == 'refunded':
        query = query.filter(full_refund)
    elif status != 'all':
        query = query.filter(~full_refund)
        query = query.filter(OrderMaster.order_status == status_map[status])

    # Station staff see only their zone's operational orders, never arbitrary zone IDs.
    rows = query.order_by(OrderMaster.created_at.desc(), OrderMaster.order_sn.desc()).offset((page - 1) * 100).limit(101).all()
    return jsonify({'page': page, 'has_more': len(rows) > 100, 'orders': [{
        'order_sn': order.order_sn,
        'status_text': get_order_status_text(display_order_status(order)),
        'refund_status_text': manual_refund_status_text(order),
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'receiver_address': order.receiver_address,
        'remark': order.remark,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else None,
        'items': [{'product_name': item.product_name, 'quantity': item.quantity, 'unit': item.unit}
                  for item in order.items],
    } for order in rows[:100]]}), 200
