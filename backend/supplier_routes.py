from flask import Blueprint, request, jsonify
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta
from extensions import db

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')
BUSINESS_TZ = timezone(timedelta(hours=8))


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

# ==================== 供应商登录和信息获取 ====================

@supplier_bp.route('/login', methods=['POST'])
def supplier_login():
    from models import Supplier # Lazy import
    data = request.get_json()
    if not data:
        return jsonify({'message': '无效请求'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'message': '请输入账号和密码'}), 400
    
    supplier = Supplier.query.filter_by(username=username).first()
    if not supplier or supplier.password != password: # 生产环境请使用加密密码验证
        return jsonify({'message': '账号或密码错误'}), 401
    
    if not supplier.is_active:
        return jsonify({'message': '供应商账号已被禁用'}), 403
    
    return jsonify({
        'message': '登录成功',
        'supplier_id': supplier.id,
        'supplier_name': supplier.name
    }), 200

@supplier_bp.route('/profile', methods=['GET'])
def get_supplier_profile():
    from models import Supplier # Lazy import
    supplier_id = request.args.get('supplier_id') # 从请求参数获取供应商ID，实际应用中应从token获取
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401
    
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        return jsonify({'message': '供应商不存在'}), 404
        
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'contact_person': supplier.contact_person,
        'phone': supplier.phone,
        'username': supplier.username,
        'is_active': supplier.is_active,
        'created_at': supplier.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

# ==================== 备货单管理 ====================

@supplier_bp.route('/orders', methods=['GET'])
def get_supplier_orders():
    from models import SupplierOrder # Lazy import
    supplier_id = request.args.get('supplier_id')
    status_filter = request.args.get('status')

    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    query = SupplierOrder.query.filter_by(supplier_id=supplier_id)
    if status_filter and status_filter.isdigit():
        query = query.filter_by(status=int(status_filter))
        
    orders = query.order_by(SupplierOrder.created_at.desc()).all()
    summary_orders = SupplierOrder.query.filter_by(supplier_id=supplier_id).all()
    today_orders = [so for so in summary_orders if so.status != 40 and is_today(so.created_at)]
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
        'today_order_count': len(today_orders)
    }
    return jsonify({"supplier_orders": output, "summary": summary}), 200

@supplier_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_supplier_order_status(order_id):
    from models import SupplierOrder # Lazy import
    supplier_id = request.args.get('supplier_id')

    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    so = SupplierOrder.query.filter_by(id=order_id, supplier_id=supplier_id).first_or_404()
    data = request.get_json()
    
    new_status = data.get('status')
    # 供应商只能更新为 备货中 或 已完成
    if new_status not in [20, 30]:
        return jsonify({'message': '无效的备货单状态，供应商只能更新为备货中或已完成'}), 400
    
    # 状态流转检查
    if so.status == 10 and new_status == 30: # 待备货可以直接到已完成
        pass
    elif so.status == 10 and new_status == 20: # 待备货到备货中
        pass
    elif so.status == 20 and new_status == 30: # 备货中到已完成
        pass
    else:
        return jsonify({'message': f'备货单当前状态 {so.status} 无法更新为 {new_status}'}), 400

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


@supplier_bp.route('/settlement', methods=['GET'])
def get_supplier_settlement():
    from models import Supplier, SupplierOrder # Lazy import

    supplier_id = request.args.get('supplier_id')
    month_value = request.args.get('month')

    if not supplier_id or not supplier_id.isdigit():
        return jsonify({'message': '未授权'}), 401

    supplier_id = int(supplier_id)
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        return jsonify({'message': '供应商不存在'}), 404

    month_range = get_month_range(month_value)
    if month_range is None:
        return jsonify({'message': '月份格式错误，请使用 YYYY-MM'}), 400

    start_local, end_local, normalized_month = month_range
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)

    orders = SupplierOrder.query.filter(
        SupplierOrder.supplier_id == supplier_id,
        SupplierOrder.created_at >= start_utc,
        SupplierOrder.created_at < end_utc
    ).order_by(SupplierOrder.created_at.desc()).all()

    summary = {
        'month': normalized_month,
        'supplier_name': supplier.name,
        'order_count': len(orders),
        'completed_count': 0,
        'pending_count': 0,
        'canceled_count': 0,
        'total_cost': Decimal('0'),
        'payable_total': Decimal('0'),
        'pending_total': Decimal('0'),
        'canceled_total': Decimal('0')
    }
    daily_totals = {}
    orders_output = []

    for order in orders:
        order_total = get_supplier_order_total(order)
        created_at = to_business_datetime(order.created_at)
        day_key = created_at.strftime('%Y-%m-%d')
        daily = daily_totals.setdefault(day_key, {
            'date': day_key,
            'order_count': 0,
            'completed_count': 0,
            'pending_count': 0,
            'total_cost': Decimal('0'),
            'payable_total': Decimal('0'),
            'pending_total': Decimal('0')
        })

        daily['order_count'] += 1
        if order.status == 30:
            summary['completed_count'] += 1
            summary['payable_total'] += order_total
            summary['total_cost'] += order_total
            daily['completed_count'] += 1
            daily['payable_total'] += order_total
            daily['total_cost'] += order_total
        elif order.status in [10, 20]:
            summary['pending_count'] += 1
            summary['pending_total'] += order_total
            summary['total_cost'] += order_total
            daily['pending_count'] += 1
            daily['pending_total'] += order_total
            daily['total_cost'] += order_total
        elif order.status == 40:
            summary['canceled_count'] += 1

        items_output = []
        for item in order.items:
            unit_price = item.unit_price if item.unit_price is not None else (item.ingredient.price if item.ingredient else None)
            item_total = get_supplier_order_item_total(item)
            items_output.append({
                'ingredient_name': item.ingredient_name,
                'quantity': str(item.quantity),
                'unit': item.unit,
                'unit_price': str(unit_price) if unit_price is not None else None,
                'total_price': str(item_total)
            })

        status_text = {
            10: '待备货',
            20: '备货中',
            30: '已完成',
            40: '已取消'
        }.get(order.status, '未知')

        orders_output.append({
            'id': order.id,
            'order_sn': order.order_sn,
            'status': order.status,
            'status_text': status_text,
            'total_cost': str(order_total),
            'items': items_output,
            'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    summary_output = {
        key: (str(value) if isinstance(value, Decimal) else value)
        for key, value in summary.items()
    }

    daily_output = []
    for day_key in sorted(daily_totals.keys(), reverse=True):
        item = daily_totals[day_key]
        daily_output.append({
            key: (str(value) if isinstance(value, Decimal) else value)
            for key, value in item.items()
        })

    return jsonify({
        'month': normalized_month,
        'summary': summary_output,
        'daily_totals': daily_output,
        'supplier_orders': orders_output
    }), 200

# ==================== 原料管理 (供应商视角) ====================
# 供应商只能管理自己提供的原料

@supplier_bp.route('/ingredients', methods=['GET'])
def get_supplier_ingredients():
    from models import Ingredient # Lazy import
    supplier_id = request.args.get('supplier_id')
    is_active = request.args.get('is_active')
    
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    query = Ingredient.query.filter_by(supplier_id=supplier_id)
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

@supplier_bp.route('/ingredients/<int:ingredient_id>', methods=['GET'])
def get_supplier_ingredient(ingredient_id):
    from models import Ingredient # Lazy import
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    ing = Ingredient.query.filter_by(id=ingredient_id, supplier_id=supplier_id).first_or_404()
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

@supplier_bp.route('/ingredients/<int:ingredient_id>', methods=['PUT'])
def update_supplier_ingredient(ingredient_id):
    from models import Ingredient # Lazy import
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    ing = Ingredient.query.filter_by(id=ingredient_id, supplier_id=supplier_id).first_or_404()
    data = request.get_json() or {}

    if 'price' in data:
        try:
            price = data['price']
            ing.price = None if price is None or price == '' else Decimal(str(price))
            if ing.price is not None and ing.price < 0:
                return jsonify({'message': '价格不能小于0'}), 400
        except (InvalidOperation, ValueError, TypeError):
            return jsonify({'message': '价格格式不正确'}), 400
    if 'stock' in data:
        try:
            stock = int(data.get('stock') or 0)
        except (ValueError, TypeError):
            return jsonify({'message': '库存格式不正确'}), 400
        if stock < 0:
            return jsonify({'message': '库存不能小于0'}), 400
        ing.stock = stock
    
    db.session.commit()
    return jsonify({"message": "价格和库存已更新"}), 200

@supplier_bp.route('/ingredients', methods=['POST'])
def create_supplier_ingredient():
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    return jsonify({"message": "供应商不能新增原料，请联系主后台添加"}), 403

@supplier_bp.route('/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_supplier_ingredient(ingredient_id):
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    return jsonify({"message": "供应商不能删除原料，请联系主后台处理"}), 403
