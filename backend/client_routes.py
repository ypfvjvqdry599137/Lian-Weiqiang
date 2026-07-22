from flask import Blueprint, request, jsonify
from decimal import Decimal
import random
import string
from datetime import datetime
import math
from extensions import db

client_bp = Blueprint('client', __name__, url_prefix='/client')

# ============================================
# 工具函数：获取/创建测试用户
# ============================================
def get_or_create_test_user():
    from models import User
    user = User.query.first()
    if not user:
        user = User(nickname='测试用户', phone='13800138000')
        db.session.add(user)
        db.session.commit()
    return user

# ============================================
# 工具函数：计算两点距离（Haversine公式）
# ============================================
def calculate_distance(lat1, lng1, lat2, lng2):
    R = 6371000  # 地球半径（米）
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2 - lat1))
    delta_lambda = math.radians(float(lng2 - lng1))
    
    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c  # 返回距离（米）

# ============================================
# 工具函数：检查地址是否在配送范围内
# ============================================
def check_delivery_available(lat, lng):
    from models import DeliveryZone
    zones = DeliveryZone.query.filter_by(is_active=True).all()
    for zone in zones:
        distance = calculate_distance(lat, lng, zone.center_lat, zone.center_lng)
        if distance <= zone.radius:
            return {
                'available': True,
                'zone': zone,
                'distance': distance
            }
    return {'available': False}

# ============================================
# 工具函数：生成订单号
# ============================================
def generate_order_sn():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.digits, k=6))
    return f'ORD{timestamp}{random_str}'

# ============================================
# 1. 用户地址管理API
# ============================================

@client_bp.route('/addresses', methods=['GET'])
def get_addresses():
    from models import UserAddress
    user = get_or_create_test_user()
    addresses = UserAddress.query.filter_by(user_id=user.id).order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc()).all()
    result = []
    for addr in addresses:
        result.append({
            'id': addr.id,
            'receiver_name': addr.receiver_name,
            'receiver_phone': addr.receiver_phone,
            'province': addr.province,
            'city': addr.city,
            'district': addr.district,
            'detail_address': addr.detail_address,
            'full_address': addr.full_address,
            'lng': str(addr.lng),
            'lat': str(addr.lat),
            'is_default': addr.is_default
        })
    return jsonify({'addresses': result})

@client_bp.route('/addresses', methods=['POST'])
def add_address():
    from models import UserAddress
    data = request.get_json()
    user = get_or_create_test_user()
    
    # 如果设为默认，先取消其他地址的默认
    if data.get('is_default'):
        UserAddress.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
    
    address = UserAddress(
        user_id=user.id,
        receiver_name=data.get('receiver_name'),
        receiver_phone=data.get('receiver_phone'),
        province=data.get('province'),
        city=data.get('city'),
        district=data.get('district'),
        detail_address=data.get('detail_address'),
        full_address=data.get('full_address'),
        lng=data.get('lng'),
        lat=data.get('lat'),
        is_default=data.get('is_default', False)
    )
    db.session.add(address)
    db.session.commit()
    
    return jsonify({'message': '添加成功', 'id': address.id})

@client_bp.route('/addresses/<int:addr_id>', methods=['PUT'])
def update_address(addr_id):
    from models import UserAddress
    data = request.get_json()
    user = get_or_create_test_user()
    address = UserAddress.query.filter_by(id=addr_id, user_id=user.id).first_or_404()
    
    # 如果设为默认，先取消其他地址的默认
    if data.get('is_default'):
        UserAddress.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
    
    address.receiver_name = data.get('receiver_name', address.receiver_name)
    address.receiver_phone = data.get('receiver_phone', address.receiver_phone)
    address.province = data.get('province', address.province)
    address.city = data.get('city', address.city)
    address.district = data.get('district', address.district)
    address.detail_address = data.get('detail_address', address.detail_address)
    address.full_address = data.get('full_address', address.full_address)
    address.lng = data.get('lng', address.lng)
    address.lat = data.get('lat', address.lat)
    address.is_default = data.get('is_default', address.is_default)
    
    db.session.commit()
    return jsonify({'message': '更新成功'})

@client_bp.route('/addresses/<int:addr_id>', methods=['DELETE'])
def delete_address(addr_id):
    from models import UserAddress
    user = get_or_create_test_user()
    address = UserAddress.query.filter_by(id=addr_id, user_id=user.id).first_or_404()
    db.session.delete(address)
    db.session.commit()
    return jsonify({'message': '删除成功'})

@client_bp.route('/addresses/default', methods=['GET'])
def get_default_address():
    from models import UserAddress
    user = get_or_create_test_user()
    address = UserAddress.query.filter_by(user_id=user.id, is_default=True).first()
    if not address:
        address = UserAddress.query.filter_by(user_id=user.id).first()
    
    if address:
        return jsonify({
            'id': address.id,
            'receiver_name': address.receiver_name,
            'receiver_phone': address.receiver_phone,
            'full_address': address.full_address,
            'lng': str(address.lng),
            'lat': str(address.lat)
        })
    return jsonify({'address': None})

# ============================================
# 2. 配送范围检查API
# ============================================

@client_bp.route('/delivery-zones', methods=['GET'])
def get_delivery_zones():
    from models import DeliveryZone
    zones = DeliveryZone.query.filter_by(is_active=True).all()
    result = []
    for zone in zones:
        result.append({
            'id': zone.id,
            'zone_name': zone.zone_name,
            'center_lng': str(zone.center_lng),
            'center_lat': str(zone.center_lat),
            'radius': zone.radius,
            'delivery_fee': str(zone.delivery_fee),
            'delivery_time': zone.delivery_time
        })
    return jsonify({'zones': result})

@client_bp.route('/delivery/check', methods=['POST'])
def check_delivery():
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not lat or not lng:
        return jsonify({'message': '缺少坐标参数'}), 400
    
    result = check_delivery_available(lat, lng)
    if result['available']:
        zone = result['zone']
        return jsonify({
            'available': True,
            'zone_name': zone.zone_name,
            'delivery_fee': str(zone.delivery_fee),
            'delivery_time': zone.delivery_time,
            'distance': int(result['distance'])
        })
    return jsonify({'available': False, 'message': '该地址不在配送范围内'})

# ============================================
# 3. 商品浏览API（保持不变，移除自提点依赖）
# ============================================

@client_bp.route('/categories', methods=['GET'])
def get_categories():
    from models import Category
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    result = []
    for cat in categories:
        result.append({
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon
        })
    return jsonify({'categories': result})

@client_bp.route('/products', methods=['GET'])
def get_products():
    from models import Product
    category_id = request.args.get('category_id')
    is_recommend = request.args.get('is_recommend')
    
    query = Product.query.filter_by(is_active=True)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if is_recommend == 'true':
        query = query.filter_by(is_recommend=True)
    
    products = query.order_by(Product.sort_order.desc(), Product.sales_count.desc()).all()
    result = []
    for product in products:
        available_stock = 0
        if product.stock:
            available_stock = product.stock.total_stock - product.stock.lock_stock
        
        result.append({
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
    return jsonify({'products': result})

@client_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product_detail(product_id):
    from models import Product
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
    })

# ============================================
# 4. 购物车管理API
# ============================================

@client_bp.route('/cart', methods=['GET'])
def get_cart():
    from models import Cart
    user = get_or_create_test_user()
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    
    result = []
    total_price = Decimal('0.00')
    
    for item in cart_items:
        product = item.product
        if not product or not product.is_active:
            continue
        
        item_price = product.price * item.quantity
        total_price += item_price
        
        result.append({
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
        'cart_items': result,
        'total_price': str(total_price)
    })

@client_bp.route('/cart', methods=['POST'])
def add_to_cart():
    from models import Product, Cart
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
        cart_item = Cart(user_id=user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    
    db.session.commit()
    return jsonify({'message': '已添加到购物车'})

@client_bp.route('/cart/<int:cart_id>', methods=['PUT'])
def update_cart_item(cart_id):
    from models import Cart
    user = get_or_create_test_user()
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first_or_404()
    
    data = request.get_json()
    quantity = data.get('quantity')
    
    if quantity <= 0:
        db.session.delete(cart_item)
    else:
        cart_item.quantity = quantity
    
    db.session.commit()
    return jsonify({'message': '购物车已更新'})

@client_bp.route('/cart/<int:cart_id>', methods=['DELETE'])
def remove_from_cart(cart_id):
    from models import Cart
    user = get_or_create_test_user()
    cart_item = Cart.query.filter_by(id=cart_id, user_id=user.id).first_or_404()
    db.session.delete(cart_item)
    db.session.commit()
    return jsonify({'message': '已从购物车移除'})

# ============================================
# 5. 订单管理API（配送模式）
# ============================================

# ============================================
# 工具函数：将订单拆分为供应商备货单
# ============================================
def split_order_to_supplier_orders(order_sn):
    from models import OrderMaster, SupplierOrder, SupplierOrderItem
    
    order = OrderMaster.query.filter_by(order_sn=order_sn).first()
    if not order:
        return 0

    if SupplierOrder.query.filter_by(order_sn=order_sn).first():
        return 0
    
    # 按供应商分组统计所需原料
    supplier_ingredients = {}
    
    for order_item in order.items:
        product = order_item.product
        if not product:
            continue
        
        # 获取该成品所需的所有原料
        for pi in product.ingredients:
            ingredient = pi.ingredient
            if not ingredient or not ingredient.supplier:
                continue
            if not ingredient.is_active or not ingredient.supplier.is_active:
                continue
            
            supplier_id = ingredient.supplier.id
            ingredient_id = ingredient.id
            supplier_items = supplier_ingredients.setdefault(supplier_id, {})
            item = supplier_items.setdefault(ingredient_id, {
                'ingredient': ingredient,
                'quantity': Decimal('0')
            })
            
            # 计算所需原料总量 = 成品数量 × 每份成品所需原料量
            total_quantity = pi.quantity_needed * order_item.quantity
            item['quantity'] += total_quantity
    
    # 为每个供应商创建备货单
    supplier_order_count = 0
    for supplier_id, items in supplier_ingredients.items():
        supplier_order = SupplierOrder(
            order_sn=order_sn,
            supplier_id=supplier_id,
            status=10,  # 待备货
            notes=f'订单 {order_sn} 所需原料'
        )
        db.session.add(supplier_order)
        db.session.flush()  # 为了获取 supplier_order.id
        supplier_order_count += 1
        
        # 创建备货单项
        for item in items.values():
            soi = SupplierOrderItem(
                supplier_order_id=supplier_order.id,
                ingredient_id=item['ingredient'].id,
                ingredient_name=item['ingredient'].name,
                quantity=item['quantity'],
                unit=item['ingredient'].unit
            )
            db.session.add(soi)

    return supplier_order_count


@client_bp.route('/orders', methods=['POST'])
def create_order():
    from models import Cart, UserAddress, Product, OrderMaster, OrderItem
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    user = get_or_create_test_user()
    
    # 获取购物车
    cart_items = Cart.query.filter_by(user_id=user.id).all()
    if not cart_items:
        return jsonify({'message': '购物车为空'}), 400
    
    # 获取收货地址
    address_id = data.get('address_id')
    address = UserAddress.query.filter_by(id=address_id, user_id=user.id).first() if address_id else None
    
    # 检查配送范围
    delivery_check = check_delivery_available(address.lat, address.lng) if address else {'available': False}
    if not delivery_check['available']:
        return jsonify({'message': '该地址不在配送范围内'}), 400
    
    zone = delivery_check['zone']
    
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
    
    # 计算最终金额（含配送费）
    delivery_fee = zone.delivery_fee
    final_amount = total_amount + delivery_fee
    
    # 创建订单
    order_sn = generate_order_sn()
    order = OrderMaster(
        order_sn=order_sn,
        user_id=user.id,
        address_id=address.id if address else None,
        zone_id=zone.id,
        order_status=10,  # 待付款
        refund_status=0,
        total_amount=total_amount,
        delivery_fee=delivery_fee,
        final_amount=final_amount,
        receiver_name=address.receiver_name if address else None,
        receiver_phone=address.receiver_phone if address else None,
        receiver_address=address.full_address if address else None,
        receiver_lng=address.lng if address else None,
        receiver_lat=address.lat if address else None,
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
        'final_amount': str(final_amount)
    }), 201

@client_bp.route('/orders', methods=['GET'])
def get_orders():
    from models import OrderMaster
    user = get_or_create_test_user()
    status = request.args.get('status')
    
    query = OrderMaster.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(order_status=int(status))
    
    orders = query.order_by(OrderMaster.created_at.desc()).all()
    result = []
    
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
        
        status_text = {10: '待付款', 20: '待配货', 30: '配送中', 40: '已送达', 50: '已完成', 60: '已取消'}.get(order.order_status, '未知')
        
        result.append({
            'order_sn': order.order_sn,
            'order_status': order.order_status,
            'status_text': status_text,
            'total_amount': str(order.total_amount),
            'delivery_fee': str(order.delivery_fee),
            'final_amount': str(order.final_amount),
            'receiver_address': order.receiver_address,
            'items': items,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({'orders': result})

@client_bp.route('/orders/<order_sn>', methods=['GET'])
def get_order_detail(order_sn):
    from models import OrderMaster
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
    
    status_text = {10: '待付款', 20: '待配货', 30: '配送中', 40: '已送达', 50: '已完成', 60: '已取消'}.get(order.order_status, '未知')
    
    return jsonify({
        'order_sn': order.order_sn,
        'order_status': order.order_status,
        'status_text': status_text,
        'total_amount': str(order.total_amount),
        'delivery_fee': str(order.delivery_fee),
        'final_amount': str(order.final_amount),
        'receiver_name': order.receiver_name,
        'receiver_phone': order.receiver_phone,
        'receiver_address': order.receiver_address,
        'remark': order.remark,
        'items': items,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@client_bp.route('/orders/<order_sn>/pay', methods=['POST'])
def pay_order(order_sn):
    from models import OrderMaster, Product
    user = get_or_create_test_user()
    order = OrderMaster.query.filter_by(order_sn=order_sn, user_id=user.id).first_or_404()
    
    if order.order_status != 10:
        return jsonify({'message': '订单状态异常'}), 400
    
    order.order_status = 20  # 改为待配货
    
    # 扣减库存：锁定库存 -> 实际扣减
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product and product.stock:
            product.stock.total_stock -= item.quantity
            product.stock.lock_stock -= item.quantity
            product.sales_count += item.quantity
    
    # 自动拆分为供应商备货单
    split_order_to_supplier_orders(order_sn)
    
    db.session.commit()
    return jsonify({'message': '支付成功'})

@client_bp.route('/orders/<order_sn>/cancel', methods=['POST'])
def cancel_order(order_sn):
    from models import OrderMaster, Product, SupplierOrder
    user = get_or_create_test_user()
    order = OrderMaster.query.filter_by(order_sn=order_sn, user_id=user.id).first_or_404()
    
    if order.order_status not in [10, 20]:
        return jsonify({'message': '当前状态无法取消订单'}), 400
    
    # 释放锁定的库存
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product and product.stock:
            if order.order_status == 10:
                product.stock.lock_stock -= item.quantity
            elif order.order_status == 20:
                product.stock.total_stock += item.quantity
    
    # 取消相关的供应商备货单
    for so in order.supplier_orders:
        if so.status in [10, 20]:  # 只有待备货或备货中的可以取消
            so.status = 40  # 已取消
    
    order.order_status = 60
    db.session.commit()
    return jsonify({'message': '订单已取消'})
