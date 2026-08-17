from collections import defaultdict
from decimal import Decimal, ROUND_CEILING

from extensions import db


def get_stock_units(quantity):
    quantity = Decimal(str(quantity or 0))
    if quantity <= 0:
        return 0
    return int(quantity.to_integral_value(rounding=ROUND_CEILING))


def get_zone_station(zone):
    if not zone:
        return None
    station = getattr(zone, 'station', None)
    if station and station.is_active:
        return station
    return None


def supplier_supports_category(supplier, category_id):
    if not supplier or category_id is None:
        return True
    categories = getattr(supplier, 'supply_categories', None) or []
    if not categories:
        return True
    return any(category.id == category_id for category in categories)


def get_active_zone_rules(zone_id, category_id=None):
    from models import ZoneSupplyRule, Supplier

    query = ZoneSupplyRule.query.filter_by(zone_id=zone_id, is_active=True)
    if category_id is not None:
        query = query.filter_by(category_id=category_id)
    return (
        query.join(Supplier, ZoneSupplyRule.supplier_id == Supplier.id)
        .filter(Supplier.is_active == True)
        .order_by(ZoneSupplyRule.is_primary.desc(), ZoneSupplyRule.priority.asc(), ZoneSupplyRule.id.asc())
        .all()
    )


def resolve_ingredient_route(ingredient, zone):
    station = get_zone_station(zone)
    category_id = getattr(ingredient, 'category_id', None)

    if zone and category_id is not None:
        for rule in get_active_zone_rules(zone.id, category_id):
            supplier = rule.supplier
            if not supplier or not supplier.is_active:
                continue
            if not supplier_supports_category(supplier, category_id):
                continue
            resolved_station = rule.station if rule.station and rule.station.is_active else station
            return {
                'supplier': supplier,
                'station': resolved_station,
                'rule': rule,
                'source': 'zone_rule'
            }

    supplier = getattr(ingredient, 'supplier', None)
    if supplier and supplier.is_active and supplier_supports_category(supplier, category_id):
        return {
            'supplier': supplier,
            'station': station,
            'rule': None,
            'source': 'ingredient_supplier'
        }

    return {
        'supplier': None,
        'station': station,
        'rule': None,
        'source': 'unresolved'
    }


def serialize_delivery_station(station):
    if not station:
        return None
    return {
        'id': station.id,
        'zone_id': station.zone_id,
        'zone_name': station.zone.zone_name if station.zone else None,
        'station_name': station.station_name,
        'address': station.address,
        'contact_person': station.contact_person,
        'phone': station.phone,
        'notes': station.notes,
        'is_active': station.is_active,
        'created_at': station.created_at.strftime('%Y-%m-%d %H:%M:%S') if station.created_at else None,
        'updated_at': station.updated_at.strftime('%Y-%m-%d %H:%M:%S') if station.updated_at else None,
    }


def serialize_zone_supply_rule(rule):
    if not rule:
        return None
    return {
        'id': rule.id,
        'zone_id': rule.zone_id,
        'zone_name': rule.zone.zone_name if rule.zone else None,
        'station_id': rule.station_id,
        'station_name': rule.station.station_name if rule.station else None,
        'category_id': rule.category_id,
        'category_name': rule.category.name if rule.category else None,
        'supplier_id': rule.supplier_id,
        'supplier_name': rule.supplier.name if rule.supplier else None,
        'priority': rule.priority,
        'is_primary': rule.is_primary,
        'is_active': rule.is_active,
        'notes': rule.notes,
        'created_at': rule.created_at.strftime('%Y-%m-%d %H:%M:%S') if rule.created_at else None,
        'updated_at': rule.updated_at.strftime('%Y-%m-%d %H:%M:%S') if rule.updated_at else None,
    }


def serialize_fulfillment_issue(issue):
    if not issue:
        return None
    return {
        'id': issue.id,
        'order_sn': issue.order_sn,
        'zone_id': issue.zone_id,
        'zone_name': issue.zone.zone_name if issue.zone else None,
        'station_id': issue.station_id,
        'station_name': issue.station.station_name if issue.station else None,
        'issue_type': issue.issue_type,
        'message': issue.message,
        'status': issue.status,
        'resolved_at': issue.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if issue.resolved_at else None,
        'created_at': issue.created_at.strftime('%Y-%m-%d %H:%M:%S') if issue.created_at else None,
        'updated_at': issue.updated_at.strftime('%Y-%m-%d %H:%M:%S') if issue.updated_at else None,
    }


def split_order_to_supplier_orders(order_sn):
    from models import FulfillmentIssue, OrderMaster, SupplierOrder, SupplierOrderItem

    order = OrderMaster.query.filter_by(order_sn=order_sn).first()
    if not order:
        return {'supplier_order_count': 0, 'issues': []}

    if SupplierOrder.query.filter_by(order_sn=order_sn).first():
        return {'supplier_order_count': 0, 'issues': []}

    zone = order.zone
    station = get_zone_station(zone)
    supplier_buckets = {}
    issue_keys = set()
    issue_payloads = []

    def add_issue(issue_type, message):
        key = (issue_type, message)
        if key in issue_keys:
            return
        issue_keys.add(key)
        issue_payloads.append({'issue_type': issue_type, 'message': message})

    for order_item in order.items:
        product = order_item.product
        if not product:
            add_issue('missing_product', f'订单 {order_sn} 存在缺失商品信息的条目')
            continue

        for rel in product.ingredients:
            ingredient = rel.ingredient
            if not ingredient:
                add_issue('missing_ingredient', f'{product.name} 的原料配置缺失')
                continue
            if not ingredient.is_active:
                add_issue('inactive_ingredient', f'{product.name} 的原料 {ingredient.name} 已停用')
                continue

            route = resolve_ingredient_route(ingredient, zone)
            supplier = route['supplier']
            route_station = route['station'] or station
            if not supplier:
                add_issue(
                    'missing_supply_rule',
                    f'区域 {zone.zone_name if zone else "未分配区域"} 的原料 {ingredient.name} 缺少可用供应商规则'
                )
                continue

            if not route_station:
                add_issue(
                    'missing_station',
                    f'区域 {zone.zone_name if zone else "未分配区域"} 尚未配置站点，原料 {ingredient.name} 暂时只能进入人工处理'
                )

            group_key = (supplier.id, route_station.id if route_station else None)
            bucket = supplier_buckets.setdefault(group_key, {
                'supplier': supplier,
                'station': route_station,
                'items': {},
                'messages': []
            })

            required_quantity = Decimal(str(rel.quantity_needed or 0)) * Decimal(str(order_item.quantity or 0))
            item = bucket['items'].setdefault(ingredient.id, {
                'ingredient': ingredient,
                'quantity': Decimal('0')
            })
            item['quantity'] += required_quantity

    supplier_order_count = 0
    for bucket in supplier_buckets.values():
        supplier = bucket['supplier']
        station = bucket['station']
        notes = []
        if zone:
            notes.append(f'区域：{zone.zone_name}')
        if station:
            notes.append(f'站点：{station.station_name}')
        notes.append(f'订单：{order_sn}')

        supplier_order = SupplierOrder(
            order_sn=order_sn,
            supplier_id=supplier.id,
            supplier_name_snapshot=supplier.name,
            status=10,
            notes=' / '.join(notes)
        )
        db.session.add(supplier_order)
        db.session.flush()
        supplier_order_count += 1

        for item in bucket['items'].values():
            ingredient = item['ingredient']
            required_quantity = item['quantity']
            required_units = get_stock_units(required_quantity)
            available_units = ingredient.stock or 0
            if required_units > available_units:
                shortage = required_units - available_units
                add_issue(
                    'stock_shortage',
                    f'原料 {ingredient.name} 库存不足，当前 {available_units}{ingredient.unit}，需要 {required_units}{ingredient.unit}，缺口 {shortage}{ingredient.unit}'
                )
            ingredient.stock = (ingredient.stock or 0) - required_units
            unit_price = ingredient.price
            total_price = required_quantity * unit_price if unit_price is not None else Decimal('0')
            db.session.add(SupplierOrderItem(
                supplier_order_id=supplier_order.id,
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                quantity=required_quantity,
                unit=ingredient.unit,
                unit_price=unit_price,
                total_price=total_price
            ))

    issue_records = []
    if issue_payloads:
        for payload in issue_payloads:
            issue = FulfillmentIssue(
                order_sn=order_sn,
                zone_id=zone.id if zone else None,
                station_id=station.id if station else None,
                issue_type=payload['issue_type'],
                message=payload['message'],
                status=10
            )
            db.session.add(issue)
            issue_records.append(issue)

    return {
        'supplier_order_count': supplier_order_count,
        'issues': [serialize_fulfillment_issue(issue) for issue in issue_records]
    }
