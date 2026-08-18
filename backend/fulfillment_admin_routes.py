from datetime import datetime

from flask import Blueprint, request, jsonify

from extensions import db
from fulfillment import (
    serialize_delivery_station,
    serialize_zone_supply_rule,
    serialize_fulfillment_issue,
)
from supplier_helpers import (
    serialize_supplier_supply_categories,
    set_supplier_supply_categories,
)

fulfillment_admin_bp = Blueprint('fulfillment_admin', __name__, url_prefix='/admin')


@fulfillment_admin_bp.route('/stations', methods=['GET'])
def get_stations():
    from models import DeliveryStation

    stations = DeliveryStation.query.order_by(DeliveryStation.id.desc()).all()
    return jsonify({'stations': [serialize_delivery_station(station) for station in stations]}), 200


@fulfillment_admin_bp.route('/stations', methods=['POST'])
def create_station():
    from models import DeliveryStation, DeliveryZone

    data = request.get_json() or {}
    zone_id = data.get('zone_id')
    station_name = (data.get('station_name') or '').strip()
    if not zone_id or not str(zone_id).isdigit():
        return jsonify({'message': '请选择配送区域'}), 400
    if not station_name:
        return jsonify({'message': '请输入站点名称'}), 400

    zone = DeliveryZone.query.get(int(zone_id))
    if not zone:
        return jsonify({'message': '配送区域不存在'}), 404
    if zone.station:
        return jsonify({'message': '该区域已经配置站点，请先编辑现有站点'}), 409

    station = DeliveryStation(
        zone_id=zone.id,
        station_name=station_name,
        address=data.get('address'),
        contact_person=data.get('contact_person'),
        phone=data.get('phone'),
        notes=data.get('notes'),
        is_active=data.get('is_active', True)
    )
    db.session.add(station)
    db.session.commit()
    return jsonify({'message': '站点创建成功', 'id': station.id}), 201


@fulfillment_admin_bp.route('/stations/<int:station_id>', methods=['GET'])
def get_station(station_id):
    from models import DeliveryStation

    station = DeliveryStation.query.get_or_404(station_id)
    return jsonify(serialize_delivery_station(station)), 200


@fulfillment_admin_bp.route('/stations/<int:station_id>', methods=['PUT'])
def update_station(station_id):
    from models import DeliveryStation, DeliveryZone, ZoneSupplyRule

    station = DeliveryStation.query.get_or_404(station_id)
    data = request.get_json() or {}

    if 'zone_id' in data:
        zone_id = data.get('zone_id')
        if not zone_id or not str(zone_id).isdigit():
            return jsonify({'message': '请选择配送区域'}), 400
        zone = DeliveryZone.query.get(int(zone_id))
        if not zone:
            return jsonify({'message': '配送区域不存在'}), 404
        other_station = DeliveryStation.query.filter(DeliveryStation.zone_id == zone.id, DeliveryStation.id != station.id).first()
        if other_station:
            return jsonify({'message': '该配送区域已被其他站点占用'}), 409
        station.zone_id = zone.id

    if 'station_name' in data:
        station.station_name = (data.get('station_name') or station.station_name).strip()
    if 'address' in data:
        station.address = data.get('address')
    if 'contact_person' in data:
        station.contact_person = data.get('contact_person')
    if 'phone' in data:
        station.phone = data.get('phone')
    if 'notes' in data:
        station.notes = data.get('notes')
    if 'is_active' in data:
        station.is_active = bool(data.get('is_active'))

    if not station.station_name:
        return jsonify({'message': '站点名称不能为空'}), 400

    if not station.is_active:
        ZoneSupplyRule.query.filter_by(station_id=station.id, is_active=True).update({'is_active': False})

    db.session.commit()
    return jsonify({'message': '站点更新成功'}), 200


@fulfillment_admin_bp.route('/stations/<int:station_id>', methods=['DELETE'])
def delete_station(station_id):
    from models import DeliveryStation, ZoneSupplyRule

    station = DeliveryStation.query.get_or_404(station_id)
    linked_rules = ZoneSupplyRule.query.filter_by(station_id=station.id).count()
    if linked_rules:
        return jsonify({'message': '该站点仍有关联站点供货规则，请先删除或迁移规则'}), 400

    db.session.delete(station)
    db.session.commit()
    return jsonify({'message': '站点已删除'}), 200


@fulfillment_admin_bp.route('/suppliers/<int:supplier_id>/supply-categories', methods=['GET'])
def get_supplier_supply_categories(supplier_id):
    from models import Supplier

    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify(serialize_supplier_supply_categories(supplier)), 200


@fulfillment_admin_bp.route('/suppliers/<int:supplier_id>/supply-categories', methods=['PUT'])
def update_supplier_supply_categories(supplier_id):
    from models import Supplier

    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json() or {}
    try:
        set_supplier_supply_categories(supplier, data.get('supply_category_ids'))
    except ValueError as exc:
        return jsonify({'message': str(exc)}), 400
    db.session.commit()
    return jsonify({'message': '供应商品类已更新', **serialize_supplier_supply_categories(supplier)}), 200


@fulfillment_admin_bp.route('/zone-supply-rules', methods=['GET'])
def get_zone_supply_rules():
    from models import ZoneSupplyRule

    zone_id = request.args.get('zone_id')
    station_id = request.args.get('station_id')
    supplier_id = request.args.get('supplier_id')
    category_id = request.args.get('category_id')
    is_active = request.args.get('is_active')

    query = ZoneSupplyRule.query
    if zone_id and str(zone_id).isdigit():
        query = query.filter_by(zone_id=int(zone_id))
    if station_id and str(station_id).isdigit():
        query = query.filter_by(station_id=int(station_id))
    if supplier_id and str(supplier_id).isdigit():
        query = query.filter_by(supplier_id=int(supplier_id))
    if category_id and str(category_id).isdigit():
        query = query.filter_by(category_id=int(category_id))
    if is_active in ['true', 'false']:
        query = query.filter_by(is_active=(is_active == 'true'))

    rules = query.order_by(ZoneSupplyRule.is_primary.desc(), ZoneSupplyRule.priority.asc(), ZoneSupplyRule.id.desc()).all()
    return jsonify({'rules': [serialize_zone_supply_rule(rule) for rule in rules]}), 200


@fulfillment_admin_bp.route('/zone-supply-rules', methods=['POST'])
def create_zone_supply_rule():
    from models import Category, DeliveryStation, DeliveryZone, Supplier, ZoneSupplyRule

    data = request.get_json() or {}
    zone_id = data.get('zone_id')
    station_id = data.get('station_id')
    category_id = data.get('category_id')
    supplier_id = data.get('supplier_id')

    if not all([zone_id, station_id, category_id, supplier_id]):
        return jsonify({'message': '请完整填写区域、站点、品类和供应商'}), 400
    if not str(zone_id).isdigit() or not str(station_id).isdigit() or not str(category_id).isdigit() or not str(supplier_id).isdigit():
        return jsonify({'message': '参数格式不正确'}), 400

    zone = DeliveryZone.query.get(int(zone_id))
    station = DeliveryStation.query.get(int(station_id))
    category = Category.query.get(int(category_id))
    supplier = Supplier.query.get(int(supplier_id))
    if not zone or not station or not category or not supplier:
        return jsonify({'message': '区域、站点、品类或供应商不存在'}), 404
    if station.zone_id != zone.id:
        return jsonify({'message': '站点必须归属该配送区域'}), 400

    rule = ZoneSupplyRule(
        zone_id=zone.id,
        station_id=station.id,
        category_id=category.id,
        supplier_id=supplier.id,
        priority=int(data.get('priority') or 0),
        is_primary=bool(data.get('is_primary', False)),
        is_active=data.get('is_active', True),
        notes=data.get('notes')
    )
    if rule.is_primary:
        ZoneSupplyRule.query.filter_by(zone_id=zone.id, category_id=category.id, is_primary=True).update({'is_primary': False})
    db.session.add(rule)
    db.session.commit()
    return jsonify({'message': '站点供货规则创建成功', 'id': rule.id}), 201


@fulfillment_admin_bp.route('/zone-supply-rules/<int:rule_id>', methods=['GET'])
def get_zone_supply_rule(rule_id):
    from models import ZoneSupplyRule

    rule = ZoneSupplyRule.query.get_or_404(rule_id)
    return jsonify(serialize_zone_supply_rule(rule)), 200


@fulfillment_admin_bp.route('/zone-supply-rules/<int:rule_id>', methods=['PUT'])
def update_zone_supply_rule(rule_id):
    from models import Category, DeliveryStation, DeliveryZone, Supplier, ZoneSupplyRule

    rule = ZoneSupplyRule.query.get_or_404(rule_id)
    data = request.get_json() or {}

    if 'zone_id' in data:
        zone_id = data.get('zone_id')
        if not str(zone_id).isdigit():
            return jsonify({'message': '区域参数不正确'}), 400
        zone = DeliveryZone.query.get(int(zone_id))
        if not zone:
            return jsonify({'message': '配送区域不存在'}), 404
        rule.zone_id = zone.id

    if 'station_id' in data:
        station_id = data.get('station_id')
        if not str(station_id).isdigit():
            return jsonify({'message': '站点参数不正确'}), 400
        station = DeliveryStation.query.get(int(station_id))
        if not station:
            return jsonify({'message': '站点不存在'}), 404
        if rule.zone_id and station.zone_id != rule.zone_id:
            return jsonify({'message': '站点必须归属当前区域'}), 400
        rule.station_id = station.id

    if 'category_id' in data:
        category_id = data.get('category_id')
        if not str(category_id).isdigit():
            return jsonify({'message': '品类参数不正确'}), 400
        category = Category.query.get(int(category_id))
        if not category:
            return jsonify({'message': '品类不存在'}), 404
        rule.category_id = category.id

    if 'supplier_id' in data:
        supplier_id = data.get('supplier_id')
        if not str(supplier_id).isdigit():
            return jsonify({'message': '供应商参数不正确'}), 400
        supplier = Supplier.query.get(int(supplier_id))
        if not supplier:
            return jsonify({'message': '供应商不存在'}), 404
        rule.supplier_id = supplier.id

    if 'priority' in data:
        rule.priority = int(data.get('priority') or 0)
    if 'is_primary' in data:
        rule.is_primary = bool(data.get('is_primary'))
    if 'is_active' in data:
        rule.is_active = bool(data.get('is_active'))
    if 'notes' in data:
        rule.notes = data.get('notes')

    if rule.is_primary:
        ZoneSupplyRule.query.filter(
            ZoneSupplyRule.zone_id == rule.zone_id,
            ZoneSupplyRule.category_id == rule.category_id,
            ZoneSupplyRule.id != rule.id,
            ZoneSupplyRule.is_primary == True
        ).update({'is_primary': False})

    db.session.commit()
    return jsonify({'message': '站点供货规则更新成功'}), 200


@fulfillment_admin_bp.route('/zone-supply-rules/<int:rule_id>', methods=['DELETE'])
def delete_zone_supply_rule(rule_id):
    from models import ZoneSupplyRule

    rule = ZoneSupplyRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify({'message': '站点供货规则已删除'}), 200


@fulfillment_admin_bp.route('/fulfillment-issues', methods=['GET'])
def get_fulfillment_issues():
    from models import FulfillmentIssue

    status = request.args.get('status')
    zone_id = request.args.get('zone_id')
    station_id = request.args.get('station_id')
    order_sn = (request.args.get('order_sn') or '').strip()
    issue_type = (request.args.get('issue_type') or '').strip()

    query = FulfillmentIssue.query
    if status and str(status).isdigit():
        query = query.filter_by(status=int(status))
    if zone_id and str(zone_id).isdigit():
        query = query.filter_by(zone_id=int(zone_id))
    if station_id and str(station_id).isdigit():
        query = query.filter_by(station_id=int(station_id))
    if order_sn:
        query = query.filter_by(order_sn=order_sn)
    if issue_type:
        query = query.filter_by(issue_type=issue_type)

    issues = query.order_by(FulfillmentIssue.created_at.desc()).all()
    return jsonify({'issues': [serialize_fulfillment_issue(issue) for issue in issues]}), 200


@fulfillment_admin_bp.route('/fulfillment-issues/<int:issue_id>', methods=['PUT'])
def update_fulfillment_issue(issue_id):
    from models import FulfillmentIssue

    issue = FulfillmentIssue.query.get_or_404(issue_id)
    data = request.get_json() or {}

    if 'status' in data:
        try:
            issue.status = int(data.get('status'))
        except (TypeError, ValueError):
            return jsonify({'message': '状态参数不正确'}), 400
        if issue.status == 20:
            issue.resolved_at = datetime.utcnow()
        elif issue.status == 10:
            issue.resolved_at = None
    if 'message' in data:
        issue.message = data.get('message') or issue.message

    db.session.commit()
    return jsonify({'message': '异常已更新', 'issue': serialize_fulfillment_issue(issue)}), 200
