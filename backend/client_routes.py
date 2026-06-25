from flask import Blueprint, request, jsonify
from app import db
from models import CommunityStation, Category, Product, ProductStock, User, Cart, OrderMaster, OrderItem
from decimal import Decimal
import random
import string
from datetime import datetime

client_bp = Blueprint('client', __name__, url_prefix='/client')

# ==================== 自提点/小区管理 ====================

@client_bp.route('/stations', methods=['GET'])
def get_stations():
    """获取所有自提点列表"""
    stations = CommunityStation.query.all()
    output = []
    for station in stations:
        output.append({
            'id': station.id,
            'station_name': station.station_name,
            'address': station.address
        })
    return jsonify({'stations': output}), 200

# ==================== 商品浏览 ====================

@client_bp.route('/categories', methods=['GET'])
def get_categories():
    """获取所有上架的商品分类"""
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    output = []
    for cat in categories:
        output.append({
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon
        })
    return jsonify({'categories': output}), 200

@client_bp.route('/products', methods=['GET'])
def get_products():
    """获取商品列表（用户端）"""
    category_id = request.args.get('category_id')
    is_recommend = request.args.get('is_recommend')
    
    query = Product.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    if is_recommend == 'true':
        query = query.filter_by(is_recommend=True)
    
    products = query.order_by(Product.sort_order.desc(), Product.sales_count.desc()).all()
    output = []
    for product in products:
        available_stock = 0
        if product.stock:
            available_stock = product.stock.total_stock - product.stock.lock_stock
        
        output.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'category_id': product.category_id,
            'category_name': product.category.name if product.category else None,
            'price': str(product.price),
            'original_price': str(product.original_price) if product.original_price else None,
            'image_url': product.image_url,
            'unit': product.unit,
            'sales_count': product.sales_count,
            'available_stock': available_stock
        })
    return jsonify({'products': output}), 200

@client_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product_detail(product_id):
    """获取商品详情"""
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        return jsonify({'message': '商品已下架'}), 404
    
    available_stock = 0
    if product.stock:
        available_stock = product.stock.total_stock - product.stock.lock_stock
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'category_id': product.category_id,
        'category_name': product.category.name if product.category else None,
        'price': str(product.price),
        'original_price': str(product.original_price) if product.original_price else None,
        'image_url': product.image_url,
        'images': product.images,
        'unit': product.unit,
        'specs': product.specs,
        'sales_count': product.sales_count,
        'available_stock': available_stock
    }), 200

# ==================== 购物车管理 ====================

def get_or_create_test_user():
    """临时：获取或创建一个测试用户（实际项目中应通过微信登录获取）"""
    user = User.query.first()
    if not user:
        user = User(
            nickname='测试用户',
            phone='13800138000'
        )
        db.session.add(user)
        db.session.commit()
    return user

@client_bp.route('/cart', methods=['GET'])
def get_cart():
    """获取购物车"""
    user = get_or_create_test_user()
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    
    output = []
    total_price = Decimal('0.00')
    
    for item in cart_items:
        product = item.product
        if not product or not product.is_active:
            continue
        
        item_price = product.price * item.quantity
        total_price += item_price
        
        output.append({
            'id': item.id,
            'product_id': product.id,
            'product_name': product.name,
            'product_image': product.image_url,
            'price': str(product.price),
            'unit': product.unit,
            'quantity': item.quantity,
            'item_price': str(item_price)
        })
    
    return jsonify({
        'cart_items': output,
        'total_price': str(total_price)
    }), 200

@client_bp.route('/cart', methods=['POST'])
def add_to_cart():
    """添加商品到购物车"""
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    if not product_id:
        return jsonify({'message': '请选择商品'}), 400
    
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        return jsonify({'message': '商品已下架'}), 400
    
    user = get_or_create_test_user()
    
    # 检查是否已在购物车
    cart_item = Cart.query.filter_by(user_id=user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(
            user_id=user.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    return jsonify({'message': '已添加到购物车'}), 200

@client_bp.route('/cart/<int:cart_id>', methods=['PUT'])
def update_cart_item(cart_id):
    """更新购物车商品数量"""
    user = get_or_create_test_user()
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first_or_404()
    
    data = request.get_json()
    quantity = data.get('quantity')
    
    if quantity <= 0:
        db.session.delete(cart_item)
    else:
        cart_item.quantity = quantity
    
    db.session.commit()
    return jsonify({'message': '购物车已更新'}), 200

@client_bp.route('/cart/<int:cart_id>', methods=['DELETE'])
def remove_from_cart(cart_id):
    """从购物车移除商品"""
    user = get_or_create_test_user()
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first_or_404()
    
    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'message': '已从购物车移除'}), 200

# ==================== 订单管理 ====================

def generate_order_sn():
    """生成订单号"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.digits, k=6))
    return f'ORD{timestamp}{random_str}'

@client_bp.route('/orders', methods=['POST'])
def create_order():
    """创建订单"""
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    user = get_or_create_test_user()
    
    # 获取购物车商品
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    if not cart_items:
        return jsonify({'message': '购物车为空'}), 400
    
    # 计算总金额并检查库存
    total_amount = Decimal('0.00')
    order_items_data = []
    
    for item in cart_items:
        product = item.product
        if not product or not product.is_active:
            continue
        
        # 检查库存
        if product.stock:
            available = product.stock.total_stock - product.stock.lock_stock
            if item.quantity > available:
                return jsonify({'message': f'{product.name} 库存不足'}), 400
        
        item_total = product.price * item.quantity
        total_amount += item_total
        
        order_items_data.append({
            'product': product,
            'quantity': item.quantity
        })
    
    # 创建订单
    order_sn = generate_order_sn()
    station_id = data.get('station_id')
    if not station_id:
        # 如果没选，默认选第一个
        station = CommunityStation.query.first()
        station_id = station.id if station else 1
    
    order = OrderMaster(
        order_sn=order_sn,
        user_id=user.id,
        station_id=station_id,
        shipping_type=data.get('shipping_type', 1),
        order_status=10,  # 待付款
        refund_status=0,
        total_amount=total_amount,
        pickup_time=data.get('pickup_time'),
        receiver_name=data.get('receiver_name', user.nickname),
        receiver_phone=data.get('receiver_phone', user.phone),
        remark=data.get('remark')
    )
    db.session.add(order)
    
    # 创建订单项
    for item_data in order_items_data:
        product = item_data['product']
        quantity = item_data['quantity']
        
        order_item = OrderItem(
            order_sn=order_sn,
            product_id=product.id,
            product_name=product.name,
            product_image=product.image_url,
            price=product.price,
            quantity=quantity,
            unit=product.unit
        )
        db.session.add(order_item)
        
        # 锁定库存
        if product.stock:
            product.stock.lock_stock += quantity
    
    # 清空购物车
    for item in cart_items:
        db.session.delete(item)
    
    db.session.commit()
    
    return jsonify({
        'message': '订单创建成功',
        'order_sn': order_sn,
        'total_amount': str(total_amount)
    }), 201

@client_bp.route('/orders', methods=['GET'])
def get_orders():
    """获取订单列表"""
    user = get_or_create_test_user()
    status = request.args.get('status')
    
    query = OrderMaster.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(order_status=int(status))
    
    orders = query.order_by(OrderMaster.created_at.desc()).all()
    output = []
    
    for order in orders:
        items = []
        for item in order.items:
            items.append({
                'product_name': item.product_name,
                'product_image': item.product_image,
                'price': str(item.price),
                'quantity': item.quantity,
                'unit': item.unit
            })
        
        output.append({
            'order_sn': order.order_sn,
            'order_status': order.order_status,
            'total_amount': str(order.total_amount),
            'pickup_time': order.pickup_time,
            'items': items,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': output}), 200

@client_bp.route('/orders/<order_sn>', methods=['GET'])
def get_order_detail(order_sn):
    """获取订单详情"""
    user = get_or_create_test_user()
    order = OrderMaster.query.filter_by(order_sn=order_sn, user_id=user.id).first_or_404()
    
    items = []
    for item in order.items:
        items.append({
            'product_name': item.product_name,
            'product_image': item.product_image,
            'price': str(item.price),
            'quantity': item.quantity,
            'unit': item.unit
        })
    
    return jsonify({
        'order_sn': order.order_sn,
        'order_status': order.order_status,
        'total_amount': str(order.total_amount),
        'pickup_time': order.pickup_time,
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'remark': order.remark,
        'items': items,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@client_bp.route('/orders/<order_sn>/pay', methods=['POST'])
def pay_order(order_sn):
    """模拟支付订单（实际项目中需要对接微信支付）"""
    user = get_or_create_test_user()
    order = OrderMaster.query.filter_by(order_sn=order_sn, user_id=user.id).first_or_404()
    
    if order.order_status != 10:  # 不是待付款状态
        return jsonify({'message': '订单状态异常'}), 400
    
    # 模拟支付成功
    order.order_status = 20  # 改为待配货
    
    # 扣减库存：锁定库存 -> 实际扣减
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product and product.stock:
            product.stock.total_stock -= item.quantity
            product.stock.lock_stock -= item.quantity
            product.sales_count += item.quantity
    
    db.session.commit()
    
    return jsonify({'message': '支付成功'}), 200

@client_bp.route('/orders/<order_sn>/cancel', methods=['POST'])
def cancel_order(order_sn):
    """取消订单"""
    user = get_or_create_test_user()
    order = OrderMaster.query.filter_by(order_sn=order_sn, user_id=user.id).first_or_404()
    
    if order.order_status not in [10, 20]:  # 只能取消待付款或待配货订单
        return jsonify({'message': '当前状态无法取消订单'}), 400
    
    # 释放锁定的库存
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product and product.stock:
            if order.order_status == 10:
                product.stock.lock_stock -= item.quantity
            # 如果已经扣减了库存（待配货），需要加回来
            elif order.order_status == 20:
                product.stock.total_stock += item.quantity
    
    order.order_status = 60  # 已关闭
    db.session.commit()
    
    return jsonify({'message': '订单已取消'}), 200
