import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Blueprint, request, jsonify, current_app
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from extensions import db
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_PRODUCT_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
PRODUCT_IMAGE_MAX_SIDE = 1200
PRODUCT_IMAGE_QUALITY = 82
BUSINESS_TZ = timezone(timedelta(hours=8))


def get_public_upload_url(relative_path):
    base_url = (current_app.config.get('PUBLIC_BASE_URL') or request.host_url.rstrip('/')).rstrip('/')
    return f"{base_url}/{relative_path.lstrip('/')}"


def get_tencent_map_js_key():
    return (current_app.config.get('TENCENT_MAP_JS_KEY') or '').strip()


def get_tencent_map_server_key():
    return (current_app.config.get('TENCENT_MAP_SERVER_KEY') or '').strip()


def request_tencent_map_api(path, params, accept_statuses=(0,)):
    key = get_tencent_map_server_key()
    if not key:
        return None, ({'message': '请先在服务器环境变量 TENCENT_MAP_SERVER_KEY 配置腾讯地图 WebService Key'}, 400)

    query = dict(params)
    query['key'] = key
    url = f"https://apis.map.qq.com{path}?{urlencode(query)}"
    try:
        with urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (URLError, TimeoutError, ValueError, OSError):
        return None, ({'message': '腾讯地图服务暂时不可用，请稍后再试'}, 502)

    if accept_statuses is not None and payload.get('status') not in accept_statuses:
        return None, ({'message': payload.get('message') or '腾讯地图解析失败'}, 400)
    return payload, None


def get_tencent_payload_message(payload):
    if not payload:
        return None
    return payload.get('message') or payload.get('msg')


def format_tencent_place_result(item, keyword):
    location = item.get('location') or {}
    if location.get('lng') is None or location.get('lat') is None:
        return None
    return {
        'title': item.get('title') or keyword,
        'address': item.get('address') or item.get('title') or keyword,
        'lng': location.get('lng'),
        'lat': location.get('lat'),
        'province': item.get('province'),
        'city': item.get('city'),
        'district': item.get('district'),
        'source': 'place_suggestion'
    }


def search_tencent_place(keyword, region=None):
    attempts = []
    if region:
        attempts.append({'keyword': keyword, 'region': region})
    attempts.append({'keyword': keyword})

    last_message = None
    for params in attempts:
        payload, error = request_tencent_map_api('/ws/place/v1/suggestion', params, accept_statuses=None)
        if error:
            body, _ = error
            last_message = body.get('message')
            continue
        if payload.get('status') != 0:
            last_message = get_tencent_payload_message(payload)
            continue
        for item in payload.get('data') or []:
            result = format_tencent_place_result(item, keyword)
            if result:
                return result, None
    return None, last_message

@admin_bp.route('/map/config', methods=['GET'])
def get_map_config():
    key = get_tencent_map_js_key()
    return jsonify({
        'enabled': bool(key),
        'key': key,
        'server_geocoder_enabled': bool(get_tencent_map_server_key())
    }), 200


@admin_bp.route('/map/geocode', methods=['GET'])
def geocode_map_address():
    address = (request.args.get('address') or '').strip()
    region = (request.args.get('region') or '').strip()
    if not address:
        return jsonify({'message': '请输入要搜索的地址'}), 400

    place_result, place_message = search_tencent_place(address, region or None)
    if place_result:
        return jsonify(place_result), 200

    params = {'address': address}
    if region:
        params['region'] = region
    payload, error = request_tencent_map_api('/ws/geocoder/v1/', params, accept_statuses=None)
    if error:
        body, status = error
        return jsonify(body), status

    if payload.get('status') != 0:
        message = get_tencent_payload_message(payload)
        if place_message and '达到上限' in place_message:
            message = place_message
        elif not message:
            message = place_message
        if message and '达到上限' in message:
            message = '腾讯地图服务端 Key 的相关接口额度不足，请在额度管理里给“关键词输入提示/地址解析”分配额度'
        else:
            message = '没有找到有效坐标，请输入“城市 + 小区/门店名”，或直接点击地图选点'
        return jsonify({'message': message}), 400

    result = payload.get('result') or {}
    location = result.get('location') or {}
    if location.get('lng') is None or location.get('lat') is None:
        return jsonify({'message': '没有解析到有效坐标，请换一个更完整的地址'}), 400

    return jsonify({
        'title': result.get('title') or address,
        'address': result.get('address') or address,
        'lng': location.get('lng'),
        'lat': location.get('lat'),
        'province': (result.get('address_components') or {}).get('province'),
        'city': (result.get('address_components') or {}).get('city'),
        'district': (result.get('address_components') or {}).get('district'),
        'reliability': result.get('reliability'),
        'similarity': result.get('similarity'),
        'source': 'geocoder'
    }), 200

@admin_bp.route('/map/reverse-geocode', methods=['GET'])
def reverse_geocode_map_location():
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    if not lat or not lng:
        return jsonify({'message': '缺少坐标参数'}), 400

    payload, error = request_tencent_map_api('/ws/geocoder/v1/', {'location': f'{lat},{lng}'})
    if error:
        body, status = error
        return jsonify(body), status

    result = payload.get('result') or {}
    component = result.get('address_component') or {}
    return jsonify({
        'address': result.get('address'),
        'formatted_address': (result.get('formatted_addresses') or {}).get('recommend') or result.get('address'),
        'province': component.get('province'),
        'city': component.get('city'),
        'district': component.get('district')
    }), 200


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


def is_today(value):
    if not value:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TZ).date() == datetime.now(BUSINESS_TZ).date()


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


def get_order_supplier_cost(order):
    return sum((get_supplier_order_total(supplier_order) for supplier_order in order.supplier_orders), Decimal('0'))

def get_price_request_status_text(status):
    return {
        10: '待审核',
        20: '已通过',
        30: '已驳回'
    }.get(status, '未知')


def serialize_ingredient_price_request(request_item):
    if not request_item:
        return None
    return {
        'id': request_item.id,
        'ingredient_id': request_item.ingredient_id,
        'ingredient_name': request_item.ingredient.name if request_item.ingredient else None,
        'supplier_id': request_item.supplier_id,
        'supplier_name': request_item.supplier.name if request_item.supplier else None,
        'old_price': str(request_item.old_price) if request_item.old_price is not None else None,
        'requested_price': str(request_item.requested_price) if request_item.requested_price is not None else None,
        'status': request_item.status,
        'status_text': get_price_request_status_text(request_item.status),
        'remark': request_item.remark,
        'created_at': request_item.created_at.strftime('%Y-%m-%d %H:%M:%S') if request_item.created_at else None,
        'reviewed_at': request_item.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if request_item.reviewed_at else None,
        'updated_at': request_item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if request_item.updated_at else None
    }


def get_pending_ingredient_price_request(ingredient_id):
    from models import IngredientPriceChangeRequest
    return IngredientPriceChangeRequest.query.filter_by(
        ingredient_id=ingredient_id,
        status=10
    ).order_by(IngredientPriceChangeRequest.created_at.desc()).first()


def serialize_admin_ingredient(ing):
    pending_request = get_pending_ingredient_price_request(ing.id)
    return {
        'id': ing.id,
        'name': ing.name,
        'unit': ing.unit,
        'category_id': ing.category_id,
        'category_name': ing.category.name if ing.category else None,
        'supplier_id': ing.supplier_id,
        'supplier_name': ing.supplier.name if ing.supplier else None,
        'zone_id': ing.zone_id,
        'zone_name': ing.zone.zone_name if ing.zone else None,
        'price': str(ing.price) if ing.price is not None else None,
        'stock': ing.stock,
        'is_active': ing.is_active,
        'pending_price_request': serialize_ingredient_price_request(pending_request),
        'created_at': ing.created_at.strftime('%Y-%m-%d %H:%M:%S') if ing.created_at else None
    }

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
    zone_id = data.get('zone_id') or None
    if not all([name, supplier_id]):
        return jsonify({"message": "Name and supplier are required"}), 400

    ingredient = Ingredient(
        name=name,
        unit=data.get('unit', '斤'),
        category_id=data.get('category_id'),
        supplier_id=supplier_id,
        zone_id=zone_id,
        price=Decimal(str(data.get('price'))) if data.get('price') is not None else None,
        stock=data.get('stock', 0),
        is_active=data.get('is_active', True)
    )
    db.session.add(ingredient)
    db.session.commit()
    return jsonify({"message": "Ingredient created successfully", "id": ingredient.id}), 201

@admin_bp.route('/ingredients', methods=['GET'])
def get_ingredients():
    from models import Ingredient, Supplier, Category, DeliveryZone
    supplier_id = request.args.get('supplier_id')
    zone_id_filter = request.args.get('zone_id')
    is_active = request.args.get('is_active')
    keyword = (request.args.get('q') or '').strip()
    
    query = Ingredient.query
    if supplier_id:
        query = query.filter_by(supplier_id=int(supplier_id))
    if zone_id_filter:
        if zone_id_filter == 'global':
            query = query.filter(Ingredient.zone_id.is_(None))
        elif zone_id_filter.isdigit():
            query = query.filter_by(zone_id=int(zone_id_filter))
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    if keyword:
        like = f"%{keyword}%"
        query = query.outerjoin(Supplier, Ingredient.supplier_id == Supplier.id) \
            .outerjoin(Category, Ingredient.category_id == Category.id) \
            .outerjoin(DeliveryZone, Ingredient.zone_id == DeliveryZone.id) \
            .filter(or_(
                Ingredient.name.ilike(like),
                Supplier.name.ilike(like),
                Category.name.ilike(like),
                DeliveryZone.zone_name.ilike(like)
            ))
    
    ingredients = query.order_by(Ingredient.created_at.desc()).all()
    return jsonify({"ingredients": [serialize_admin_ingredient(ing) for ing in ingredients]}), 200
@admin_bp.route('/ingredients/batch', methods=['DELETE'])
def batch_delete_ingredients():
    from models import Ingredient
    data = request.get_json()
    ids = data.get('ids') if data else None
    if not ids:
        return jsonify({"message": "请选择要删除的原料"}), 400

    try:
        ids = [int(item) for item in ids]
    except (TypeError, ValueError):
        return jsonify({"message": "原料ID格式不正确"}), 400

    ingredients = Ingredient.query.filter(Ingredient.id.in_(ids)).all()
    for ing in ingredients:
        ing.is_active = False

    db.session.commit()
    return jsonify({
        "message": "Ingredients disabled successfully",
        "count": len(ingredients)
    }), 200

@admin_bp.route('/ingredients/<int:ingredient_id>', methods=['GET'])
def get_ingredient(ingredient_id):
    from models import Ingredient
    ing = Ingredient.query.get_or_404(ingredient_id)
    return jsonify(serialize_admin_ingredient(ing)), 200
@admin_bp.route('/ingredients/<int:ingredient_id>', methods=['PUT'])
def update_ingredient(ingredient_id):
    from models import Ingredient
    ing = Ingredient.query.get_or_404(ingredient_id)
    data = request.get_json()

    ing.name = data.get('name', ing.name)
    ing.unit = data.get('unit', ing.unit)
    ing.category_id = data.get('category_id', ing.category_id)
    ing.supplier_id = data.get('supplier_id', ing.supplier_id)
    if 'zone_id' in data:
        ing.zone_id = data.get('zone_id') or None
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
    ing.is_active = False
    db.session.commit()
    return jsonify({"message": "Ingredient disabled successfully"}), 200

# ==================== 原料价格审核 ====================

@admin_bp.route('/ingredient-price-requests', methods=['GET'])
def get_ingredient_price_requests():
    from models import IngredientPriceChangeRequest, Ingredient, Supplier
    status_filter = (request.args.get('status') or 'pending').strip().lower()
    keyword = (request.args.get('q') or '').strip()

    query = IngredientPriceChangeRequest.query
    if status_filter != 'all':
        status_map = {
            'pending': 10,
            'approved': 20,
            'rejected': 30,
            '10': 10,
            '20': 20,
            '30': 30
        }
        status_value = status_map.get(status_filter)
        if status_value is None:
            return jsonify({"message": "审核状态不正确"}), 400
        query = query.filter_by(status=status_value)

    if keyword:
        like = f"%{keyword}%"
        query = query.join(Ingredient, IngredientPriceChangeRequest.ingredient_id == Ingredient.id) \
            .join(Supplier, IngredientPriceChangeRequest.supplier_id == Supplier.id) \
            .filter(or_(
                Ingredient.name.ilike(like),
                Supplier.name.ilike(like)
            ))

    requests = query.order_by(IngredientPriceChangeRequest.created_at.desc()).all()
    summary = {
        'pending_count': IngredientPriceChangeRequest.query.filter_by(status=10).count(),
        'approved_count': IngredientPriceChangeRequest.query.filter_by(status=20).count(),
        'rejected_count': IngredientPriceChangeRequest.query.filter_by(status=30).count()
    }
    return jsonify({
        "requests": [serialize_ingredient_price_request(item) for item in requests],
        "summary": summary
    }), 200


@admin_bp.route('/ingredient-price-requests/<int:request_id>/review', methods=['PUT'])
def review_ingredient_price_request(request_id):
    from models import IngredientPriceChangeRequest
    request_item = IngredientPriceChangeRequest.query.get_or_404(request_id)
    data = request.get_json() or {}
    action = (data.get('action') or '').strip().lower()

    if request_item.status != 10:
        return jsonify({"message": "该价格申请已经审核过，不能重复处理"}), 400

    if action in ['approve', 'approved']:
        request_item.status = 20
        if request_item.ingredient:
            request_item.ingredient.price = request_item.requested_price
        message = '价格申请已通过，新价格已生效'
    elif action in ['reject', 'rejected']:
        request_item.status = 30
        message = '价格申请已驳回，原价格保持不变'
    else:
        return jsonify({"message": "请传入 approve 或 reject"}), 400

    request_item.remark = data.get('remark') or None
    request_item.reviewed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": message,
        "request": serialize_ingredient_price_request(request_item)
    }), 200
# ==================== 成品-原料关联管理 ====================

@admin_bp.route('/products/<int:product_id>/ingredients', methods=['POST'])
def add_product_ingredient(product_id):
    from models import ProductIngredient, Product, Ingredient, Supplier
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400
    
    product = Product.query.get_or_404(product_id)
    ingredient_id = data.get('ingredient_id')
    ingredient_name = (data.get('ingredient_name') or '').strip()
    supplier_id = data.get('supplier_id')
    zone_id = data.get('zone_id')
    supplier_name = (data.get('supplier_name') or '').strip()
    quantity_needed = data.get('quantity_needed')
    
    if not quantity_needed:
        return jsonify({"message": "请填写所需数量"}), 400
    
    if ingredient_id:
        ingredient = Ingredient.query.get_or_404(ingredient_id)
        if not ingredient.is_active:
            return jsonify({"message": "原料已停用"}), 400
        if ingredient.supplier and not ingredient.supplier.is_active:
            return jsonify({"message": "供应商已禁用"}), 400
        if zone_id == 'global' and ingredient.zone_id is not None:
            return jsonify({"message": "请选择通用区域原料"}), 400
        if zone_id and str(zone_id).isdigit() and ingredient.zone_id != int(zone_id):
            return jsonify({"message": "请选择当前配送区域下的原料"}), 400
        ingredient_id = ingredient.id
    else:
        if not ingredient_name:
            return jsonify({"message": "请输入原料名称"}), 400

        if supplier_id:
            supplier = Supplier.query.get_or_404(int(supplier_id))
            if not supplier.is_active:
                return jsonify({"message": "供应商已禁用"}), 400
        elif not supplier_name:
            return jsonify({"message": "请选择供应商"}), 400

        query = Ingredient.query.filter(
            Ingredient.name == ingredient_name,
            Ingredient.is_active == True
        )
        if supplier_id:
            query = query.filter(Ingredient.supplier_id == int(supplier_id))
        if zone_id == 'global':
            query = query.filter(Ingredient.zone_id.is_(None))
        elif zone_id and str(zone_id).isdigit():
            query = query.filter(Ingredient.zone_id == int(zone_id))
        if supplier_name:
            query = query.join(Supplier).filter(Supplier.name == supplier_name)

        matches = query.order_by(Ingredient.id.asc()).limit(2).all()
        if not matches:
            return jsonify({"message": "未找到该供应商下的原料，请先在原料管理中添加并设置价格"}), 404
        if len(matches) > 1:
            return jsonify({"message": "该供应商下存在多个同名原料，请先整理原料数据"}), 409

        ingredient = matches[0]
        ingredient_id = ingredient.id
    
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
            'supplier_id': rel.ingredient.supplier_id if rel.ingredient else None,
            'supplier_name': rel.ingredient.supplier.name if (rel.ingredient and rel.ingredient.supplier) else None,
            'ingredient_zone_id': rel.ingredient.zone_id if rel.ingredient else None,
            'ingredient_zone_name': rel.ingredient.zone.zone_name if (rel.ingredient and rel.ingredient.zone) else None,
            'ingredient_price': str(rel.ingredient.price) if (rel.ingredient and rel.ingredient.price is not None) else None,
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
    from models import SupplierOrder, OrderMaster
    supplier_id = request.args.get('supplier_id')
    status_filter = request.args.get('status')
    zone_id_filter = request.args.get('zone_id')

    def apply_filters(query, include_status=True):
        if supplier_id:
            query = query.filter(SupplierOrder.supplier_id == int(supplier_id))
        if zone_id_filter:
            query = query.join(OrderMaster, SupplierOrder.order_sn == OrderMaster.order_sn)
            if zone_id_filter == 'unassigned':
                query = query.filter(OrderMaster.zone_id.is_(None))
            elif zone_id_filter.isdigit():
                query = query.filter(OrderMaster.zone_id == int(zone_id_filter))
        if include_status and status_filter and status_filter.isdigit():
            query = query.filter(SupplierOrder.status == int(status_filter))
        return query

    query = apply_filters(SupplierOrder.query)
    orders = query.order_by(SupplierOrder.created_at.desc()).all()
    summary_query = apply_filters(SupplierOrder.query, include_status=False)
    summary_orders = summary_query.all()
    today_orders = [so for so in summary_orders if so.status != 40 and is_today(so.created_at)]
    supplier_totals = {}
    for so in today_orders:
        sid = so.supplier_id
        if sid not in supplier_totals:
            supplier_totals[sid] = {
                'supplier_id': sid,
                'supplier_name': so.supplier.name if so.supplier else '未知供应商',
                'today_total_cost': Decimal('0')
            }
        supplier_totals[sid]['today_total_cost'] += get_supplier_order_total(so)

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
                unit_price = item.unit_price if item.unit_price is not None else (item.ingredient.price if item.ingredient else None)
                total_price = get_supplier_order_item_total(item)
                items_output.append({
                    'id': item.id,
                    'ingredient_id': item.ingredient_id,
                    'ingredient_name': item.ingredient_name,
                    'quantity': str(item.quantity),
                    'unit': item.unit,
                    'unit_price': str(unit_price) if unit_price is not None else None,
                    'total_price': str(total_price)
                })
        
        output.append({
            'id': so.id,
            'order_sn': so.order_sn,
            'supplier_id': so.supplier_id,
            'supplier_name': so.supplier.name if so.supplier else None,
            'zone_id': so.order.zone_id if so.order else None,
            'zone_name': so.order.zone.zone_name if (so.order and so.order.zone) else None,
            'status': so.status,
            'status_text': status_text,
            'notes': so.notes,
            'items': items_output,
            'total_cost': str(get_supplier_order_total(so)),
            'created_at': so.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': so.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    summary = {
        'today_total_cost': str(sum((get_supplier_order_total(so) for so in today_orders), Decimal('0'))),
        'filtered_total_cost': str(sum((get_supplier_order_total(so) for so in orders), Decimal('0'))),
        'today_order_count': len(today_orders),
        'supplier_totals': [
            {
                'supplier_id': item['supplier_id'],
                'supplier_name': item['supplier_name'],
                'today_total_cost': str(item['today_total_cost'])
            }
            for item in supplier_totals.values()
        ]
    }
    return jsonify({"supplier_orders": output, "summary": summary}), 200

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

# ==================== 配送区域统计 ====================

@admin_bp.route('/zone-statistics', methods=['GET'])
def get_zone_statistics():
    from models import DeliveryZone, OrderMaster

    month_range = get_month_range(request.args.get('month'))
    if month_range is None:
        return jsonify({'message': '月份格式错误，请使用 YYYY-MM'}), 400

    zone_id_filter = request.args.get('zone_id')
    start_local, end_local, normalized_month = month_range
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)

    zones_query = DeliveryZone.query.order_by(DeliveryZone.id.asc())
    orders_query = OrderMaster.query.filter(
        OrderMaster.created_at >= start_utc,
        OrderMaster.created_at < end_utc
    )
    if zone_id_filter and zone_id_filter.isdigit():
        zone_id = int(zone_id_filter)
        zones_query = zones_query.filter_by(id=zone_id)
        orders_query = orders_query.filter_by(zone_id=zone_id)

    zone_rows = {}
    for zone in zones_query.all():
        zone_rows[zone.id] = {
            'zone_id': zone.id,
            'zone_name': zone.zone_name,
            'merchant_username': zone.merchant_username,
            'order_count': 0,
            'active_order_count': 0,
            'completed_count': 0,
            'pending_count': 0,
            'canceled_count': 0,
            'total_sales': Decimal('0'),
            'settled_sales': Decimal('0'),
            'delivery_fee_total': Decimal('0'),
            'supplier_cost_total': Decimal('0'),
            'settled_supplier_cost': Decimal('0'),
            'estimated_gross_profit': Decimal('0')
        }

    totals = {
        'month': normalized_month,
        'order_count': 0,
        'active_order_count': 0,
        'completed_count': 0,
        'pending_count': 0,
        'canceled_count': 0,
        'total_sales': Decimal('0'),
        'settled_sales': Decimal('0'),
        'delivery_fee_total': Decimal('0'),
        'supplier_cost_total': Decimal('0'),
        'settled_supplier_cost': Decimal('0'),
        'estimated_gross_profit': Decimal('0')
    }

    completed_statuses = [40, 50]
    pending_statuses = [10, 20, 30]
    for order in orders_query.all():
        zone_id = order.zone_id or 0
        if zone_id not in zone_rows:
            zone_rows[zone_id] = {
                'zone_id': zone_id,
                'zone_name': order.zone.zone_name if order.zone else '未分配区域',
                'merchant_username': order.zone.merchant_username if order.zone else None,
                'order_count': 0,
                'active_order_count': 0,
                'completed_count': 0,
                'pending_count': 0,
                'canceled_count': 0,
                'total_sales': Decimal('0'),
                'settled_sales': Decimal('0'),
                'delivery_fee_total': Decimal('0'),
                'supplier_cost_total': Decimal('0'),
                'settled_supplier_cost': Decimal('0'),
                'estimated_gross_profit': Decimal('0')
            }

        row = zone_rows[zone_id]
        order_total = money(order.total_amount)
        delivery_fee = money(order.delivery_fee)
        supplier_cost = get_order_supplier_cost(order)

        row['order_count'] += 1
        totals['order_count'] += 1
        if order.order_status == 60:
            row['canceled_count'] += 1
            totals['canceled_count'] += 1
            continue

        row['active_order_count'] += 1
        row['total_sales'] += order_total
        row['supplier_cost_total'] += supplier_cost
        totals['active_order_count'] += 1
        totals['total_sales'] += order_total
        totals['supplier_cost_total'] += supplier_cost

        if order.order_status in completed_statuses:
            row['completed_count'] += 1
            row['settled_sales'] += order_total
            row['delivery_fee_total'] += delivery_fee
            row['settled_supplier_cost'] += supplier_cost
            totals['completed_count'] += 1
            totals['settled_sales'] += order_total
            totals['delivery_fee_total'] += delivery_fee
            totals['settled_supplier_cost'] += supplier_cost
        elif order.order_status in pending_statuses:
            row['pending_count'] += 1
            totals['pending_count'] += 1

    for row in zone_rows.values():
        row['estimated_gross_profit'] = row['settled_sales'] - row['settled_supplier_cost']
    totals['estimated_gross_profit'] = totals['settled_sales'] - totals['settled_supplier_cost']

    zones_output = [
        {key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()}
        for row in sorted(zone_rows.values(), key=lambda item: item['zone_id'] or 0)
    ]
    totals_output = {key: (str(value) if isinstance(value, Decimal) else value) for key, value in totals.items()}

    return jsonify({
        'month': normalized_month,
        'summary': totals_output,
        'zones': zones_output
    }), 200
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
            'zone_name': order.zone.zone_name if order.zone else None,
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

@admin_bp.route('/uploads/product-image', methods=['POST'])
def upload_product_image():
    upload = request.files.get('image')
    if not upload or not upload.filename:
        return jsonify({"message": "请选择要上传的图片"}), 400

    original_filename = secure_filename(upload.filename)
    extension = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    if extension not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        return jsonify({"message": "仅支持 JPG、PNG、WebP 图片"}), 400

    upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'products'
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.jpg"
    target_path = upload_dir / filename

    try:
        image = Image.open(upload.stream)
        image = ImageOps.exif_transpose(image)
        image.thumbnail((PRODUCT_IMAGE_MAX_SIDE, PRODUCT_IMAGE_MAX_SIDE), Image.Resampling.LANCZOS)

        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image.convert('RGBA'), mask=image.convert('RGBA').split()[-1])
            image = background
        else:
            image = image.convert('RGB')

        image.save(target_path, 'JPEG', quality=PRODUCT_IMAGE_QUALITY, optimize=True, progressive=True)
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({"message": "图片文件无法识别，请重新选择"}), 400

    relative_url = f"uploads/products/{filename}"
    return jsonify({
        "message": "Image uploaded successfully",
        "image_url": get_public_upload_url(relative_url),
        "path": f"/{relative_url}"
    }), 201

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
