from flask import Blueprint, request, jsonify
from app import db
from models import CommunityStation, OrderMaster, OrderItem, Product
from datetime import datetime, date
from decimal import Decimal

merchant_bp = Blueprint('merchant', __name__, url_prefix='/merchant')

# ==================== 合作商登录和获取信息 ====================

def get_station_by_merchant(username, password):
    """根据合作商账号密码获取自提点（简化版，生产环境密码需要加密）"""
    station = CommunityStation.query.filter_by(merchant_username=username).first()
    if station and station.merchant_password == password:  # 实际项目中密码应该加密比对
        return station
    return None

@merchant_bp.route('/login', methods=['POST'])
def merchant_login():
    """合作商登录"""
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'message': '请输入账号和密码'}), 400
    
    station = get_station_by_merchant(username, password)
    if not station:
        return jsonify({'message': '账号或密码错误'}), 401
    
    return jsonify({
        'message': '登录成功',
        'station_id': station.id,
        'station_name': station.station_name,
        'address': station.address
    }), 200

# ==================== 今日待办（工作台） ====================

@merchant_bp.route('/dashboard/today-arrival', methods=['GET'])
def get_today_arrival():
    """获取今日到货汇总（需要按商品汇总该小区今日的所有待自提订单）"""
    # 模拟：从 header 获取 station_id（实际项目中应该从 token 中获取）
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    # 获取该小区所有待自提或配送中的订单（状态为30-配送中，40-待自提）
    orders = OrderMaster.query.filter(
        OrderMaster.station_id == station_id,
        OrderMaster.order_status.in_([30, 40])
    ).all()
    
    # 按商品汇总
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

@merchant_bp.route('/dashboard/pending-pickup', methods=['GET'])
def get_pending_pickup():
    """获取待自提订单列表"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    orders = OrderMaster.query.filter_by(
        station_id=station_id,
        order_status=40  # 待自提
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
            'pickup_time': order.pickup_time,
            'items': items,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': output}), 200

# ==================== 订单管理 ====================

@merchant_bp.route('/orders', methods=['GET'])
def get_merchant_orders():
    """获取合作商的订单列表"""
    station_id = request.args.get('station_id')
    status = request.args.get('status')  # 可选：all, pending, completed
    keyword = request.args.get('keyword')  # 搜索：昵称/手机号/订单号
    
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    query = OrderMaster.query.filter_by(station_id=station_id)
    
    if status == 'pending':
        query = query.filter_by(order_status=40)  # 待自提
    elif status == 'completed':
        query = query.filter_by(order_status=50)  # 已完成
    
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
        
        # 订单状态文字说明
        status_text = {
            10: '待付款',
            20: '待配货',
            30: '配送中',
            40: '待自提',
            50: '已完成',
            60: '已关闭'
        }.get(order.order_status, '未知')
        
        output.append({
            'order_sn': order.order_sn,
            'order_status': order.order_status,
            'status_text': status_text,
            'receiver_name': order.receiver_name,
            'receiver_phone': order.receiver_phone,
            'pickup_time': order.pickup_time,
            'items': items,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': output}), 200

@merchant_bp.route('/orders/<order_sn>', methods=['GET'])
def get_merchant_order_detail(order_sn):
    """获取订单详情"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        station_id=station_id
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
        40: '待自提',
        50: '已完成',
        60: '已关闭'
    }.get(order.order_status, '未知')
    
    return jsonify({
        'order_sn': order.order_sn,
        'order_status': order.order_status,
        'status_text': status_text,
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'pickup_time': order.pickup_time,
        'remark': order.remark,
        'items': items,
        'total_amount': str(order.total_amount),
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@merchant_bp.route('/orders/<order_sn>/confirm-pickup', methods=['POST'])
def confirm_pickup(order_sn):
    """确认提货（核销订单）"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        station_id=station_id
    ).first_or_404()
    
    if order.order_status != 40:  # 必须是待自提状态
        return jsonify({'message': '订单状态异常，无法核销'}), 400
    
    order.order_status = 50  # 改为已完成
    db.session.commit()
    
    return jsonify({'message': '核销成功，订单已完成'}), 200

# ==================== 售后初审 ====================

@merchant_bp.route('/orders/<order_sn>/approve-refund', methods=['POST'])
def approve_refund(order_sn):
    """同意退款申请（初审）"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        station_id=station_id
    ).first_or_404()
    
    if order.refund_status != 10:  # 必须是待合作商初审状态
        return jsonify({'message': '当前状态无法进行此操作'}), 400
    
    order.refund_status = 20  # 改为待总后台终审
    db.session.commit()
    
    return jsonify({'message': '已同意退款，等待总后台审核'}), 200

@merchant_bp.route('/orders/<order_sn>/reject-refund', methods=['POST'])
def reject_refund(order_sn):
    """拒绝退款申请"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    order = OrderMaster.query.filter_by(
        order_sn=order_sn,
        station_id=station_id
    ).first_or_404()
    
    if order.refund_status != 10:
        return jsonify({'message': '当前状态无法进行此操作'}), 400
    
    order.refund_status = 40  # 售后驳回
    db.session.commit()
    
    return jsonify({'message': '已拒绝退款申请'}), 200

# ==================== 数据统计 ====================

@merchant_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """获取数据统计：今日营业额、今日订单量、本月预估佣金"""
    station_id = request.args.get('station_id')
    if not station_id:
        return jsonify({'message': '请先登录'}), 401
    
    station = CommunityStation.query.get_or_404(station_id)
    commission_rate = station.commission_rate or Decimal('0.00')
    
    today = date.today()
    
    # 今日订单
    today_orders = OrderMaster.query.filter(
        OrderMaster.station_id == station_id,
        OrderMaster.order_status.in_([40, 50]),
        db.func.date(OrderMaster.created_at) == today
    ).all()
    
    today_revenue = sum(order.total_amount for order in today_orders if order.total_amount)
    today_order_count = len(today_orders)
    
    # 本月订单
    month_start = today.replace(day=1)
    month_orders = OrderMaster.query.filter(
        OrderMaster.station_id == station_id,
        OrderMaster.order_status.in_([40, 50]),
        OrderMaster.created_at >= month_start
    ).all()
    
    month_revenue = sum(order.total_amount for order in month_orders if order.total_amount)
    estimated_commission = month_revenue * (commission_rate / 100)
    
    return jsonify({
        'today_revenue': str(today_revenue),
        'today_order_count': today_order_count,
        'month_estimated_commission': str(estimated_commission)
    }), 200
