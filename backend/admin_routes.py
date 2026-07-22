from flask import Blueprint, request, jsonify
from decimal import Decimal
from extensions import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ==================== 供应商管理 ====================

@admin_bp.route('/suppliers', methods=['POST'])
def create_supplier():
    from models import Supplier
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    name = data.get('name')
    username = data.get('username')
    password = data.get('password', '123456')

    if not all([name, username]):
        return jsonify({"message": "Name and username are required"}), 400

    if Supplier.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 409

    supplier = Supplier(
        name=name,
        contact_person=data.get('contact_person'),
        phone=data.get('phone'),
        username=username,
        password=password,
        is_active=data.get('is_active', True)
    )
    db.session.add(supplier)
    db.session.commit()
    return jsonify({"message": "Supplier created successfully", "id": supplier.id}), 201

@admin_bp.route('/suppliers', methods=['GET'])
def get_suppliers():
    from models import Supplier
    suppliers = Supplier.query.order_by(Supplier.created_at.desc()).all()
    output = []
    for supplier in suppliers:
        output.append({
            'id': supplier.id,
            'name': supplier.name,
            'contact_person': supplier.contact_person,
            'phone': supplier.phone,
            'username': supplier.username,
            'is_active': supplier.is_active,
            'created_at': supplier.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"suppliers": output}), 200

@admin_bp.route('/suppliers/<int:supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'contact_person': supplier.contact_person,
        'phone': supplier.phone,
        'username': supplier.username,
        'is_active': supplier.is_active,
        'created_at': supplier.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@admin_bp.route('/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()

    supplier.name = data.get('name', supplier.name)
    supplier.contact_person = data.get('contact_person', supplier.contact_person)
    supplier.phone = data.get('phone', supplier.phone)
    supplier.is_active = data.get('is_active', supplier.is_active)
    
    if 'password' in data and data['password']:
        supplier.password = data['password']
    
    if 'username' in data:
        existing = Supplier.query.filter(
            Supplier.username == data['username'],
            Supplier.id != supplier_id
        ).first()
        if existing:
            return jsonify({"message": "Username already exists"}), 409
        supplier.username = data['username']
        
    db.session.commit()
    return jsonify({"message": "Supplier updated successfully"}), 200

@admin_bp.route('/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"message": "Supplier deleted successfully"}), 200

# ==================== 原料管理 ====================

@admin_bp.route('/ingredients', methods=['POST'])
def create_ingredient():
    from models import Ingredient
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    name = data.get('name')
    supplier_id = data.get('supplier_id')
    if not all([name, supplier_id]):
        return jsonify({"message": "Name and supplier are required"}), 400

    ingredient = Ingredient(
        name=name,
        unit=data.get('unit', '斤'),
        category_id=data.get('category_id'),
        supplier_id=supplier_id,
        price=Decimal(str(data.get('price'))) if data.get('price') is not None else None,
        stock=data.get('stock', 0),
        is_active=data.get('is_active', True)
    )
    db.session.add(ingredient)
    db.session.commit()
    return jsonify({"message": "Ingredient created successfully", "id": ingredient.id}), 201

@admin_bp.route('/ingredients', methods=['GET'])
def get_ingredients():
    from models import Ingredient
    supplier_id = request.args.get('supplier_id')
    is_active = request.args.get('is_active')
    
    query = Ingredient.query
    if supplier_id:
        query = query.filter_by(supplier_id=int(supplier_id))
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    
    ingredients = query.order_by(Ingredient.created_at.desc()).all()
    output = []
    for ing in ingredients:
        output.append({
            'id': ing.id,
            'name': ing.name,
            'unit': ing.unit,
            'category_id': ing.category_id,
            'category_name': ing.category.name if ing.category else None,
            'supplier_id': ing.supplier_id,
            'supplier_name': ing.supplier.name if ing.supplier else None,
            'price': str(ing.price) if ing.price else None,
            'stock': ing.stock,
            'is_active': ing.is_active,
            'created_at': ing.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"ingredients": output}), 200

@admin_bp.route('/ingredients/<int:ingredient_id>', methods=['GET'])
def get_ingredient(ingredient_id):
    from models import Ingredient
    ing = Ingredient.query.get_or_404(ingredient_id)
    return jsonify({
        'id': ing.id,
        'name': ing.name,
        'unit': ing.unit,
        'category_id': ing.category_id,
        'category_name': ing.category.name if ing.category else None,
        'supplier_id': ing.supplier_id,
        'supplier_name': ing.supplier.name if ing.supplier else None,
        'price': str(ing.price) if ing.price else None,
        'stock': ing.stock,
        'is_active': ing.is_active
    }), 200

@admin_bp.route('/ingredients/<int:ingredient_id>', methods=['PUT'])
def update_ingredient(ingredient_id):
    from models import Ingredient
    ing = Ingredient.query.get_or_404(ingredient_id)
    data = request.get_json()

    ing.name = data.get('name', ing.name)
    ing.unit = data.get('unit', ing.unit)
    ing.category_id = data.get('category_id', ing.category_id)
    ing.supplier_id = data.get('supplier_id', ing.supplier_id)
    if 'price' in data:
        ing.price = Decimal(str(data['price'])) if data['price'] is not None else None
    ing.stock = data.get('stock', ing.stock)
    ing.is_active = data.get('is_active', ing.is_active)
    
    db.session.commit()
    return jsonify({"message": "Ingredient updated successfully"}), 200

@admin_bp.route('/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    from models import Ingredient
    ing = Ingredient.query.get_or_404(ingredient_id)
    db.session.delete(ing)
    db.session.commit()
    return jsonify({"message": "Ingredient deleted successfully"}), 200

# ==================== 成品-原料关联管理 ====================

@admin_bp.route('/products/<int:product_id>/ingredients', methods=['POST'])
def add_product_ingredient(product_id):
    from models import ProductIngredient, Product, Ingredient
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400
    
    product = Product.query.get_or_404(product_id)
    ingredient_id = data.get('ingredient_id')
    quantity_needed = data.get('quantity_needed')
    
    if not all([ingredient_id, quantity_needed]):
        return jsonify({"message": "Ingredient and quantity are required"}), 400
    
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    
    existing = ProductIngredient.query.filter_by(
        product_id=product_id,
        ingredient_id=ingredient_id
    ).first()
    if existing:
        existing.quantity_needed = Decimal(str(quantity_needed))
    else:
        new_relation = ProductIngredient(
            product_id=product_id,
            ingredient_id=ingredient_id,
            quantity_needed=Decimal(str(quantity_needed))
        )
        db.session.add(new_relation)
    
    db.session.commit()
    return jsonify({"message": "Ingredient added to product successfully"}), 201

@admin_bp.route('/products/<int:product_id>/ingredients', methods=['GET'])
def get_product_ingredients(product_id):
    from models import ProductIngredient, Product
    product = Product.query.get_or_404(product_id)
    output = []
    for rel in product.ingredients:
        output.append({
            'id': rel.id,
            'product_id': rel.product_id,
            'ingredient_id': rel.ingredient_id,
            'ingredient_name': rel.ingredient.name if rel.ingredient else None,
            'ingredient_unit': rel.ingredient.unit if rel.ingredient else '斤',
            'supplier_name': rel.ingredient.supplier.name if (rel.ingredient and rel.ingredient.supplier) else None,
            'quantity_needed': str(rel.quantity_needed)
        })
    return jsonify({"ingredients": output}), 200

@admin_bp.route('/products/<int:product_id>/ingredients/<int:relation_id>', methods=['DELETE'])
def delete_product_ingredient(product_id, relation_id):
    from models import ProductIngredient
    rel = ProductIngredient.query.filter_by(id=relation_id, product_id=product_id).first_or_404()
    db.session.delete(rel)
    db.session.commit()
    return jsonify({"message": "Ingredient removed from product successfully"}), 200

# ==================== 供应商备货单管理 ====================

@admin_bp.route('/supplier-orders', methods=['GET'])
def get_all_supplier_orders():
    from models import SupplierOrder
    supplier_id = request.args.get('supplier_id')
    status_filter = request.args.get('status')
    
    query = SupplierOrder.query
    if supplier_id:
        query = query.filter_by(supplier_id=int(supplier_id))
    if status_filter and status_filter.isdigit():
        query = query.filter_by(status=int(status_filter))
        
    orders = query.order_by(SupplierOrder.created_at.desc()).all()
    output = []
    for so in orders:
        status_text = {
            10: '待备货',
            20: '备货中',
            30: '已完成',
            40: '已取消'
        }.get(so.status, '未知')
        
        items_output = []
        if so.items:
            for item in so.items:
                items_output.append({
                    'id': item.id,
                    'ingredient_id': item.ingredient_id,
                    'ingredient_name': item.ingredient_name,
                    'quantity': str(item.quantity),
                    'unit': item.unit
                })
        
        output.append({
            'id': so.id,
            'order_sn': so.order_sn,
            'supplier_id': so.supplier_id,
            'supplier_name': so.supplier.name if so.supplier else None,
            'status': so.status,
            'status_text': status_text,
            'notes': so.notes,
            'items': items_output,
            'created_at': so.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': so.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"supplier_orders": output}), 200

@admin_bp.route('/supplier-orders/<int:order_id>/status', methods=['PUT'])
def update_supplier_order_status(order_id):
    from models import SupplierOrder
    so = SupplierOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    new_status = data.get('status')
    if new_status not in [10, 20, 30, 40]:
        return jsonify({"message": "无效的备货单状态"}), 400
    
    so.status = new_status
    db.session.commit()
    
    status_text = {
        10: '待备货',
        20: '备货中',
        30: '已完成',
        40: '已取消'
    }.get(new_status, '未知')
    
    return jsonify({
        "message": "备货单状态已更新",
        "id": order_id,
        "new_status": new_status,
        "status_text": status_text
    }), 200

# ==================== 配送区域管理 ====================

@admin_bp.route('/delivery-zones', methods=['POST'])
def create_delivery_zone():
    from models import DeliveryZone
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    zone_name = data.get('zone_name')
    center_lng = data.get('center_lng')
    center_lat = data.get('center_lat')
    radius = data.get('radius', 3000)
    delivery_fee = data.get('delivery_fee', 0.00)
    delivery_time = data.get('delivery_time', '30分钟')
    merchant_username = data.get('merchant_username')
    merchant_password = data.get('merchant_password')

    if not all([zone_name, center_lng, center_lat]):
        return jsonify({"message": "Missing required fields"}), 400

    if merchant_username and DeliveryZone.query.filter_by(merchant_username=merchant_username).first():
        return jsonify({"message": "Merchant username already exists"}), 409

    new_zone = DeliveryZone(
        zone_name=zone_name,
        center_lng=center_lng,
        center_lat=center_lat,
        radius=radius,
        delivery_fee=Decimal(str(delivery_fee)) if delivery_fee is not None else Decimal('0.00'),
        delivery_time=delivery_time,
        merchant_username=merchant_username,
        merchant_password=merchant_password
    )
    db.session.add(new_zone)
    db.session.commit()
    return jsonify({"message": "Delivery zone created successfully", "id": new_zone.id}), 201

@admin_bp.route('/delivery-zones', methods=['GET'])
def get_delivery_zones():
    from models import DeliveryZone
    zones = DeliveryZone.query.all()
    output = []
    for zone in zones:
        output.append({
            'id': zone.id,
            'zone_name': zone.zone_name,
            'center_lng': str(zone.center_lng),
            'center_lat': str(zone.center_lat),
            'radius': zone.radius,
            'delivery_fee': str(zone.delivery_fee),
            'delivery_time': zone.delivery_time,
            'merchant_username': zone.merchant_username,
            'is_active': zone.is_active
        })
    return jsonify({"zones": output}), 200

@admin_bp.route('/delivery-zones/<int:zone_id>', methods=['GET'])
def get_delivery_zone(zone_id):
    from models import DeliveryZone
    zone = DeliveryZone.query.get_or_404(zone_id)
    return jsonify({
        'id': zone.id,
        'zone_name': zone.zone_name,
        'center_lng': str(zone.center_lng),
        'center_lat': str(zone.center_lat),
        'radius': zone.radius,
        'delivery_fee': str(zone.delivery_fee),
        'delivery_time': zone.delivery_time,
        'merchant_username': zone.merchant_username,
        'is_active': zone.is_active
    }), 200

@admin_bp.route('/delivery-zones/<int:zone_id>', methods=['PUT'])
def update_delivery_zone(zone_id):
    from models import DeliveryZone
    zone = DeliveryZone.query.get_or_404(zone_id)
    data = request.get_json()

    zone.zone_name = data.get('zone_name', zone.zone_name)
    if 'center_lng' in data:
        zone.center_lng = data['center_lng']
    if 'center_lat' in data:
        zone.center_lat = data['center_lat']
    if 'radius' in data:
        zone.radius = data['radius']
    if 'delivery_fee' in data:
        zone.delivery_fee = Decimal(str(data['delivery_fee']))
    if 'delivery_time' in data:
        zone.delivery_time = data['delivery_time']
    if 'is_active' in data:
        zone.is_active = data['is_active']
    
    # 如果传了新密码，更新密码
    if 'merchant_password' in data and data['merchant_password']:
        zone.merchant_password = data['merchant_password']
    
    # 如果传了新的用户名，检查是否已被使用
    if 'merchant_username' in data:
        existing = DeliveryZone.query.filter(
            DeliveryZone.merchant_username == data['merchant_username'],
            DeliveryZone.id != zone_id
        ).first()
        if existing:
            return jsonify({"message": "Merchant username already exists"}), 409
        zone.merchant_username = data['merchant_username']
        
    db.session.commit()
    return jsonify({"message": "Delivery zone updated successfully"}), 200

@admin_bp.route('/delivery-zones/<int:zone_id>', methods=['DELETE'])
def delete_delivery_zone(zone_id):
    from models import DeliveryZone
    zone = DeliveryZone.query.get_or_404(zone_id)
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"message": "Delivery zone deleted successfully"}), 200

# ==================== 订单状态管理（总后台） ====================

@admin_bp.route('/orders', methods=['GET'])
def get_all_orders():
    from models import OrderMaster
    """获取所有订单（总后台）"""
    status_filter = request.args.get('status')
    query = OrderMaster.query
    
    if status_filter and status_filter.isdigit():
        query = query.filter_by(order_status=int(status_filter))
        
    orders = query.order_by(OrderMaster.created_at.desc()).all()
    output = []
    for order in orders:
        status_text = {
            10: '待付款',
            20: '待配货',
            30: '配送中',
            40: '已送达',
            50: '已完成',
            60: '已取消'
        }.get(order.order_status, '未知')
        
        items_output = []
        if order.items:
            for item in order.items:
                items_output.append({
                    'product_name': item.product_name,
                    'product_image': item.product_image,
                    'price': str(item.price),
                    'quantity': item.quantity,
                    'unit': item.unit
                })
        
        output.append({
            'order_sn': order.order_sn,
            'zone_id': order.zone_id,
            'order_status': order.order_status,
            'status_text': status_text,
            'total_amount': str(order.total_amount),
            'delivery_fee': str(order.delivery_fee),
            'final_amount': str(order.final_amount),
            'receiver_name': order.receiver_name,
            'receiver_phone': order.receiver_phone,
            'receiver_address': order.receiver_address,
            'items': items_output,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"orders": output}), 200

@admin_bp.route('/orders/<order_sn>/status', methods=['PUT'])
def update_order_status(order_sn):
    from models import OrderMaster
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
        40: '已送达',
        50: '已完成',
        60: '已取消'
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
    from models import Category
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
    from models import Category
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
    from models import Category
    category = Category.query.get_or_404(category_id)
    data = request.get_json()

    category.name = data.get('name', category.name)
    category.icon = data.get('icon', category.icon)
    category.sort_order = data.get('sort_order', category.sort_order)
    category.is_active = data.get('is_active', category.is_active)

    db.session.commit()
    return jsonify({"message": "Category updated successfully"}), 200

@admin_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    from models import Category
    category = Category.query.get_or_404(category_id)
    return jsonify({
        'id': category.id,
        'name': category.name,
        'icon': category.icon,
        'sort_order': category.sort_order,
        'is_active': category.is_active
    }), 200

@admin_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    from models import Category
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({"message": "Category deleted successfully"}), 200

# ==================== 商品管理 ====================

@admin_bp.route('/products', methods=['POST'])
def create_product():
    from models import Product, ProductStock
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
    db.session.flush()

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
    from models import Product
    category_id = request.args.get('category_id')
    is_active = request.args.get('is_active')

    query = Product.query

    if category_id:
        query = query.filter_by(category_id=int(category_id))
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')

    products = query.order_by(Product.sort_order.desc(), Product.id.desc()).all()
    output = []
    for product in products:
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
            'sort_order': product.sort_order,
            'sales_count': product.sales_count,
            'total_stock': product.stock.total_stock if product.stock else 0,
            'warning_stock': product.stock.warning_stock if product.stock else 10,
            'available_stock': (product.stock.total_stock - product.stock.lock_stock) if product.stock else 0
        })
    return jsonify({"products": output}), 200

@admin_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    from models import Product
    product = Product.query.get_or_404(product_id)
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
        'total_stock': product.stock.total_stock if product.stock else 0,
        'warning_stock': product.stock.warning_stock if product.stock else 10,
        'lock_stock': product.stock.lock_stock if product.stock else 0,
        'available_stock': (product.stock.total_stock - product.stock.lock_stock) if product.stock else 0
    }), 200

@admin_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    from models import Product, ProductStock
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
    
    if 'total_stock' in data or 'warning_stock' in data:
        stock = product.stock
        if not stock:
            stock = ProductStock(product_id=product.id)
            db.session.add(stock)
        if 'total_stock' in data:
            stock.total_stock = data['total_stock']
        if 'warning_stock' in data:
            stock.warning_stock = data['warning_stock']

    db.session.commit()
    return jsonify({"message": "Product updated successfully"}), 200

@admin_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    from models import Product
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    return jsonify({"message": "Product disabled successfully"}), 200

# ==================== 库存管理 ====================

@admin_bp.route('/products/<int:product_id>/stock', methods=['PUT'])
def update_stock(product_id):
    from models import Product, ProductStock
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    stock = product.stock
    if not stock:
        stock = ProductStock(product_id=product.id)
        db.session.add(stock)

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
    from models import Product, ProductStock
    product = Product.query.get_or_404(product_id)
    data = request.get_json()

    quantity = data.get('quantity', 0)
    if quantity <= 0:
        return jsonify({"message": "Quantity must be greater than 0"}), 400

    stock = product.stock
    if not stock:
        stock = ProductStock(product_id=product.id, total_stock=0)
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
    from models import ProductStock
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
