from flask import Blueprint, request, jsonify
from app import db
from models import CommunityStation, Category, Product, ProductStock, OrderMaster
from decimal import Decimal

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ==================== 社区自提点管理 ====================

@admin_bp.route('/stations', methods=['POST'])
def create_station():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    station_name = data.get('station_name')
    address = data.get('address')
    merchant_username = data.get('merchant_username')
    merchant_password = data.get('merchant_password')
    commission_rate = data.get('commission_rate', 0.00)

    if not all([station_name, address, merchant_username, merchant_password]):
        return jsonify({"message": "Missing required fields"}), 400

    if CommunityStation.query.filter_by(merchant_username=merchant_username).first():
        return jsonify({"message": "Merchant username already exists"}), 409

    new_station = CommunityStation(
        station_name=station_name,
        address=address,
        merchant_username=merchant_username,
        merchant_password=merchant_password, # In a real app, hash this password
        commission_rate=commission_rate
    )
    db.session.add(new_station)
    db.session.commit()
    return jsonify({"message": "Community station created successfully", "id": new_station.id}), 201

@admin_bp.route('/stations', methods=['GET'])
def get_stations():
    stations = CommunityStation.query.all()
    output = []
    for station in stations:
        output.append({
            'id': station.id,
            'station_name': station.station_name,
            'address': station.address,
            'merchant_username': station.merchant_username,
            'commission_rate': str(station.commission_rate)
        })
    return jsonify({"stations": output}), 200

@admin_bp.route('/stations/<int:station_id>', methods=['GET'])
def get_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    return jsonify({
        'id': station.id,
        'station_name': station.station_name,
        'address': station.address,
        'merchant_username': station.merchant_username,
        'commission_rate': str(station.commission_rate)
    }), 200

@admin_bp.route('/stations/<int:station_id>', methods=['PUT'])
def update_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    data = request.get_json()

    station.station_name = data.get('station_name', station.station_name)
    station.address = data.get('address', station.address)
    station.commission_rate = data.get('commission_rate', station.commission_rate)
    # Password update would typically be a separate endpoint for security
    db.session.commit()
    return jsonify({"message": "Community station updated successfully"}), 200

@admin_bp.route('/stations/<int:station_id>', methods=['DELETE'])
def delete_station(station_id):
    station = CommunityStation.query.get_or_404(station_id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({"message": "Community station deleted successfully"}), 200

# ==================== 订单状态管理（总后台） ====================

@admin_bp.route('/orders', methods=['GET'])
def get_all_orders():
    """获取所有订单（总后台）"""
    orders = OrderMaster.query.order_by(OrderMaster.created_at.desc()).all()
    output = []
    for order in orders:
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
            'station_id': order.station_id,
            'order_status': order.order_status,
            'status_text': status_text,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"orders": output}), 200

@admin_bp.route('/orders/<order_sn>/status', methods=['PUT'])
def update_order_status(order_sn):
    """更新订单状态（总后台）"""
    order = OrderMaster.query.get_or_404(order_sn)
    data = request.get_json()
    
    new_status = data.get('status')
    if new_status not in [10, 20, 30, 40, 50, 60]:
        return jsonify({"message": "无效的订单状态"}), 400
    
    order.order_status = new_status
    db.session.commit()
    
    status_text = {
        10: '待付款',
        20: '待配货',
        30: '配送中',
        40: '待自提',
        50: '已完成',
        60: '已关闭'
    }.get(new_status, '未知')
    
    return jsonify({
        "message": "订单状态已更新",
        "order_sn": order_sn,
        "new_status": new_status,
        "status_text": status_text
    }), 200

# ==================== 商品分类管理 ====================

@admin_bp.route('/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    name = data.get('name')
    if not name:
        return jsonify({"message": "Category name is required"}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"message": "Category name already exists"}), 409

    category = Category(
        name=name,
        icon=data.get('icon'),
        sort_order=data.get('sort_order', 0),
        is_active=data.get('is_active', True)
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({"message": "Category created successfully", "id": category.id}), 201

@admin_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = Category.query.order_by(Category.sort_order).all()
    output = []
    for cat in categories:
        output.append({
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon,
            'sort_order': cat.sort_order,
            'is_active': cat.is_active
        })
    return jsonify({"categories": output}), 200

@admin_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    data = request.get_json()

    category.name = data.get('name', category.name)
    category.icon = data.get('icon', category.icon)
    category.sort_order = data.get('sort_order', category.sort_order)
    category.is_active = data.get('is_active', category.is_active)

    db.session.commit()
    return jsonify({"message": "Category updated successfully"}), 200

@admin_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted successfully"}), 200

# ==================== 商品管理 ====================

@admin_bp.route('/products', methods=['POST'])
def create_product():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    name = data.get('name')
    price = data.get('price')

    if not all([name, price]):
        return jsonify({"message": "Product name and price are required"}), 400

    product = Product(
        name=name,
        description=data.get('description'),
        category_id=data.get('category_id'),
        price=Decimal(str(price)) if price is not None else None,
        original_price=Decimal(str(data.get('original_price'))) if data.get('original_price') is not None else None,
        image_url=data.get('image_url'),
        images=data.get('images'),
        unit=data.get('unit', '份'),
        specs=data.get('specs'),
        is_active=data.get('is_active', True),
        is_recommend=data.get('is_recommend', False),
        sort_order=data.get('sort_order', 0)
    )
    db.session.add(product)
    db.session.flush()  # 获取 product.id

    # 同时创建库存记录
    stock = ProductStock(
        product_id=product.id,
        total_stock=data.get('total_stock', 0),
        warning_stock=data.get('warning_stock', 10)
    )
    db.session.add(stock)
    db.session.commit()

    return jsonify({
        "message": "Product created successfully",
        "id": product.id,
        "stock_id": stock.id
    }), 201

@admin_bp.route('/products', methods=['GET'])
def get_products():
    # 支持按分类筛选
    category_id = request.args.get('category_id')
    is_active = request.args.get('is_active')

    query = Product.query

    if category_id:
        query = query.filter_by(category_id=category_id)
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')

    products = query.order_by(Product.sort_order.desc(), Product.id.desc()).all()
    output = []
    for product in products:
        stock_info = {
            'total_stock': product.stock.total_stock if product.stock else 0,
            'lock_stock': product.stock.lock_stock if product.stock else 0,
            'available_stock': (product.stock.total_stock - product.stock.lock_stock) if product.stock else 0
        }
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
            'is_active': product.is_active,
            'is_recommend': product.is_recommend,
            'sales_count': product.sales_count,
            'stock': stock_info
        })
    return jsonify({"products": output}), 200

@admin_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    stock_info = {
        'total_stock': product.stock.total_stock if product.stock else 0,
        'lock_stock': product.stock.lock_stock if product.stock else 0,
        'warning_stock': product.stock.warning_stock if product.stock else 10,
        'available_stock': (product.stock.total_stock - product.stock.lock_stock) if product.stock else 0
    }
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'category_id': product.category_id,
        'price': str(product.price),
        'original_price': str(product.original_price) if product.original_price else None,
        'image_url': product.image_url,
        'images': product.images,
        'unit': product.unit,
        'specs': product.specs,
        'is_active': product.is_active,
        'is_recommend': product.is_recommend,
        'sort_order': product.sort_order,
        'sales_count': product.sales_count,
        'stock': stock_info
    }), 200

@admin_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.category_id = data.get('category_id', product.category_id)
    if 'price' in data:
        product.price = Decimal(str(data['price'])) if data['price'] is not None else None
    if 'original_price' in data:
        product.original_price = Decimal(str(data['original_price'])) if data['original_price'] is not None else None
    product.image_url = data.get('image_url', product.image_url)
    product.images = data.get('images', product.images)
    product.unit = data.get('unit', product.unit)
    product.specs = data.get('specs', product.specs)
    product.is_active = data.get('is_active', product.is_active)
    product.is_recommend = data.get('is_recommend', product.is_recommend)
    product.sort_order = data.get('sort_order', product.sort_order)

    db.session.commit()
    return jsonify({"message": "Product updated successfully"}), 200

@admin_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted successfully"}), 200

# ==================== 库存管理 ====================

@admin_bp.route('/products/<int:product_id>/stock', methods=['PUT'])
def update_stock(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    stock = product.stock
    if not stock:
        # 如果没有库存记录，创建一个
        stock = ProductStock(product_id=product_id)
        db.session.add(stock)

    # 更新库存
    stock.total_stock = data.get('total_stock', stock.total_stock)
    stock.warning_stock = data.get('warning_stock', stock.warning_stock)

    db.session.commit()
    return jsonify({
        "message": "Stock updated successfully",
        "product_id": product_id,
        "total_stock": stock.total_stock
    }), 200

@admin_bp.route('/products/<int:product_id>/stock/increase', methods=['POST'])
def increase_stock(product_id):
    """入库操作 - 增加库存"""
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    quantity = data.get('quantity', 0)
    if quantity <= 0:
        return jsonify({"message": "Quantity must be greater than 0"}), 400

    stock = product.stock
    if not stock:
        stock = ProductStock(product_id=product_id, total_stock=0)
        db.session.add(stock)

    stock.total_stock += quantity
    db.session.commit()

    return jsonify({
        "message": "Stock increased successfully",
        "product_id": product_id,
        "added_quantity": quantity,
        "new_total_stock": stock.total_stock
    }), 200

@admin_bp.route('/stock/overview', methods=['GET'])
def get_stock_overview():
    """获取库存概览，包括库存预警"""
    stocks = ProductStock.query.all()
    warning_products = []
    normal_products = []

    for stock in stocks:
        available_stock = stock.total_stock - stock.lock_stock
        product_info = {
            'product_id': stock.product_id,
            'product_name': stock.product.name if stock.product else None,
            'total_stock': stock.total_stock,
            'lock_stock': stock.lock_stock,
            'available_stock': available_stock,
            'warning_stock': stock.warning_stock
        }
        if available_stock <= stock.warning_stock:
            warning_products.append(product_info)
        else:
            normal_products.append(product_info)

    return jsonify({
        "total_products": len(stocks),
        "warning_products_count": len(warning_products),
        "warning_products": warning_products,
        "normal_products": normal_products
    }), 200
