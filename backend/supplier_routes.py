from flask import Blueprint, request, jsonify
from app import db
from datetime import datetime
from models import Supplier, SupplierOrder, SupplierOrderItem, Ingredient

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')

# ==================== 供应商登录和信息获取 ====================

@supplier_bp.route('/login', methods=['POST'])
def supplier_login():
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
    supplier_id = request.args.get('supplier_id')
    status_filter = request.args.get('status')

    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    query = SupplierOrder.query.filter_by(supplier_id=supplier_id)
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

@supplier_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_supplier_order_status(order_id):
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

# ==================== 原料管理 (供应商视角) ====================
# 供应商只能管理自己提供的原料

@supplier_bp.route('/ingredients', methods=['GET'])
def get_supplier_ingredients():
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
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    ing = Ingredient.query.filter_by(id=ingredient_id, supplier_id=supplier_id).first_or_404()
    data = request.get_json()

    ing.name = data.get('name', ing.name)
    ing.unit = data.get('unit', ing.unit)
    ing.category_id = data.get('category_id', ing.category_id)
    # 供应商不能修改supplier_id
    if 'price' in data:
        from decimal import Decimal
        ing.price = Decimal(str(data['price'])) if data['price'] is not None else None
    ing.stock = data.get('stock', ing.stock)
    ing.is_active = data.get('is_active', ing.is_active)
    
    db.session.commit()
    return jsonify({"message": "原料更新成功"}), 200

@supplier_bp.route('/ingredients', methods=['POST'])
def create_supplier_ingredient():
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    name = data.get('name')
    if not name:
        return jsonify({"message": "Name is required"}), 400

    ingredient = Ingredient(
        name=name,
        unit=data.get('unit', '斤'),
        category_id=data.get('category_id'),
        supplier_id=supplier_id, # 自动设置为当前登录供应商
        price=data.get('price'),
        stock=data.get('stock', 0),
        is_active=data.get('is_active', True)
    )
    db.session.add(ingredient)
    db.session.commit()
    return jsonify({"message": "原料创建成功", "id": ingredient.id}), 201

@supplier_bp.route('/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_supplier_ingredient(ingredient_id):
    supplier_id = request.args.get('supplier_id')
    if not supplier_id:
        return jsonify({'message': '未授权'}), 401

    ing = Ingredient.query.filter_by(id=ingredient_id, supplier_id=supplier_id).first_or_404()
    db.session.delete(ing)
    db.session.commit()
    return jsonify({"message": "原料删除成功"}), 200