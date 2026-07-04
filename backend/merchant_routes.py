from flask import Blueprint, request, jsonify
from app import db
from datetime import datetime, date
from decimal import Decimal

merchant_bp = Blueprint('merchant', __name__, url_prefix='/merchant')

# ==================== 合作商登录和获取信息 ====================

def get_zone_by_merchant(username, password):
    from models import DeliveryZone
    """根据合作商账号密码获取配送区域（简化版，生产环境密码需要加密）"""
    zone = DeliveryZone.query.filter_by(merchant_username=username).first()
    if zone and zone.merchant_password == password:
        return zone
    return None

@merchant_bp.route('/login', methods=['POST'])
def merchant_login():
    from models import DeliveryZone
    """合作商登录"""
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'message': '请输入账号和密码'}), 400
    
    zone = get_zone_by_merchant(username, password)
    if not zone:
        return jsonify({'message': '账号或密码错误'}), 401
    
    return jsonify({
        'message': '登录成功',
        'zone_id': zone.id,
        'zone_name': zone.zone_name
    }), 200

# ==================== 今日待办（工作台） ====================

@merchant_bp.route('/dashboard/today-arrival', methods=['GET'])
def get_today_arrival():
    from models import OrderMaster
    """获取今日待配送商品汇总"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone_id,
        OrderMaster.order_status.in_([20, 30])
    ).all()
    
    product_summary = {}
    for order in orders:
        for item in order.items:
            if item.product_id not in product_summary:
                product_summary[item.product_id] = {
                    'product_id': item.product_id,
                    'product_name': item.product_name,
                    'product_image': item.product_image,
                    'unit': item.unit,
                    'total_quantity': 0
                }
            product_summary[item.product_id]['total_quantity'] += item.quantity
    
    return jsonify({
        'total_orders': len(orders),
        'products': list(product_summary.values())
    }), 200

@merchant_bp.route('/dashboard/delivering', methods=['GET'])
def get_delivering():
    from models import OrderMaster
    """获取配送中订单列表"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    orders = OrderMaster.query.filter_by(
        zone_id=zone_id,
        order_status=30
    ).order_by(OrderMaster.created_at.desc()).all()
    
    output = []
    for order in orders:
        items = []
        for item in order.items:
            items.append({
                'product_name': item.product_name,
                'quantity': item.quantity,
                'unit': item.unit
            })
        
        output.append({
            'order_sn': order.order_sn,
            'receiver_name': order.receiver_name,
            'receiver_phone': order.receiver_phone,
            'receiver_address': order.receiver_address,
            'items': items,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': output}), 200

# ==================== 订单管理 ====================

@merchant_bp.route('/orders', methods=['GET'])
def get_merchant_orders():
    from models import OrderMaster
    """获取合作商的订单列表"""
    zone_id = request.args.get('zone_id')
    status = request.args.get('status')
    keyword = request.args.get('keyword')
    
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    query = OrderMaster.query.filter_by(zone_id=zone_id)
    
    if status == 'pending':
        query = query.filter_by(order_status=20)
    elif status == 'delivering':
        query = query.filter_by(order_status=30)
    elif status == 'completed':
        query = query.filter_by(order_status=50)
    
    if keyword:
        query = query.filter(
            (OrderMaster.receiver_name.contains(keyword)) |
            (OrderMaster.receiver_phone.contains(keyword)) |
            (OrderMaster.order_sn.contains(keyword))
        )
    
    orders = query.order_by(OrderMaster.created_at.desc()).all()
    output = []
    
    for order in orders:
        items = []
        for item in order.items:
            items.append({
                'product_name': item.product_name,
                'quantity': item.quantity,
                'unit': item.unit
            })
        
        status_text = {
            10: '待付款',
            20: '待配货',
            30: '配送中',
            40: '已送达',
            50: '已完成',
            60: '已关闭'
        }.get(order.order_status, '未知')
        
        output.append({
            'order_sn': order.order_sn,
            'order_status': order.order_status,
            'status_text': status_text,
            'receiver_name': order.receiver_name,
            'receiver_phone': order.receiver_phone,
            'receiver_address': order.receiver_address,
            'items': items,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': output}), 200

@merchant_bp.route('/orders/<order_sn>', methods=['GET'])
def get_merchant_order_detail(order_sn):
    from models import OrderMaster
    """获取订单详情"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone_id
    ).first_or_404()
    
    items = []
    for item in order.items:
        items.append({
            'product_name': item.product_name,
            'product_image': item.product_image,
            'price': str(item.price),
            'quantity': item.quantity,
            'unit': item.unit
        })
    
    status_text = {
        10: '待付款',
        20: '待配货',
        30: '配送中',
        40: '已送达',
        50: '已完成',
        60: '已关闭'
    }.get(order.order_status, '未知')
    
    return jsonify({
        'order_sn': order.order_sn,
        'order_status': order.order_status,
        'status_text': status_text,
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'receiver_address': order.receiver_address,
        'remark': order.remark,
        'items': items,
        'total_amount': str(order.total_amount),
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@merchant_bp.route('/orders/<order_sn>/start-delivery', methods=['POST'])
def start_delivery(order_sn):
    from models import OrderMaster
    """开始配送"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone_id
    ).first_or_404()
    
    if order.order_status != 20:
        return jsonify({'message': '订单状态异常，无法开始配送'}), 400
    
    order.order_status = 30
    db.session.commit()
    
    return jsonify({'message': '已开始配送'}), 200

@merchant_bp.route('/orders/<order_sn>/confirm-delivery', methods=['POST'])
def confirm_delivery(order_sn):
    from models import OrderMaster
    """确认送达"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        zone_id=zone_id
    ).first_or_404()
    
    if order.order_status != 30:
        return jsonify({'message': '订单状态异常，无法确认送达'}), 400
    
    order.order_status = 40
    db.session.commit()
    
    return jsonify({'message': '已确认送达'}), 200

# ==================== 数据统计 ====================

@merchant_bp.route('/statistics', methods=['GET'])
def get_statistics():
    from models import OrderMaster
    """获取数据统计：今日营业额、今日订单量"""
    zone_id = request.args.get('zone_id')
    if not zone_id:
        return jsonify({'message': '请先登录'}), 401
    
    today = date.today()
    
    today_orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone_id,
        OrderMaster.order_status.in_([40, 50]),
        db.func.date(OrderMaster.created_at) == today
    ).all()
    
    today_revenue = sum(order.total_amount for order in today_orders if order.total_amount)
    today_order_count = len(today_orders)
    
    month_start = today.replace(day=1)
    month_orders = OrderMaster.query.filter(
        OrderMaster.zone_id == zone_id,
        OrderMaster.order_status.in_([40, 50]),
        OrderMaster.created_at >= month_start
    ).all()
    
    month_revenue = sum(order.total_amount for order in month_orders if order.total_amount)
    
    return jsonify({
        'today_revenue': str(today_revenue),
        'today_order_count': today_order_count,
        'month_revenue': str(month_revenue)
    }), 200
