
def normalize_zone_ids(raw_ids):
    if raw_ids is None:
        return []
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]

    zone_ids = []
    for raw_id in raw_ids:
        if raw_id in [None, '', 'global', 'all']:
            continue
        try:
            zone_id = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError('服务配送区域格式不正确')
        if zone_id not in zone_ids:
            zone_ids.append(zone_id)
    return zone_ids


def normalize_id_list(raw_ids):
    if raw_ids is None:
        return []
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]

    result = []
    for raw_id in raw_ids:
        if raw_id in [None, '', 'global', 'all']:
            continue
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError('ID 格式不正确')
        if value not in result:
            result.append(value)
    return result


def serialize_supplier_service_zones(supplier):
    zones = sorted(supplier.service_zones, key=lambda item: item.id)
    return {
        'service_zone_ids': [zone.id for zone in zones],
        'service_zone_names': [zone.zone_name for zone in zones]
    }


def serialize_supplier_supply_categories(supplier):
    categories = sorted(getattr(supplier, 'supply_categories', []) or [], key=lambda item: item.id)
    return {
        'supply_category_ids': [category.id for category in categories],
        'supply_category_names': [category.name for category in categories]
    }


def set_supplier_service_zones(supplier, raw_zone_ids):
    from models import DeliveryZone, Ingredient

    zone_ids = normalize_zone_ids(raw_zone_ids)
    next_zone_set = set(zone_ids)
    current_zone_set = {zone.id for zone in supplier.service_zones}
    removed_zone_ids = current_zone_set - next_zone_set
    if removed_zone_ids:
        active_ingredients = Ingredient.query.filter(
            Ingredient.supplier_id == supplier.id,
            Ingredient.is_active == True,
            Ingredient.zone_id.in_(list(removed_zone_ids))
        ).limit(5).all()
        if active_ingredients:
            names = '、'.join(sorted({item.zone.zone_name if item.zone else str(item.zone_id) for item in active_ingredients}))
            raise ValueError(f'该供应商在 {names} 还有启用原料，请先转移或停用这些原料后再取消服务区域')

    if not zone_ids:
        supplier.service_zones = []
        return

    zones = DeliveryZone.query.filter(DeliveryZone.id.in_(zone_ids)).all()
    if len(zones) != len(zone_ids):
        raise ValueError('部分配送区域不存在')
    supplier.service_zones = sorted(zones, key=lambda item: item.id)


def set_supplier_supply_categories(supplier, raw_category_ids):
    from models import Category

    category_ids = normalize_id_list(raw_category_ids)
    if not category_ids:
        supplier.supply_categories = []
        return

    categories = Category.query.filter(Category.id.in_(category_ids)).all()
    if len(categories) != len(category_ids):
        raise ValueError('部分供货品类不存在')
    supplier.supply_categories = sorted(categories, key=lambda item: item.id)


def supplier_serves_zone(supplier, zone_id):
    if not zone_id:
        return True
    return any(zone.id == int(zone_id) for zone in supplier.service_zones)


def validate_supplier_zone(supplier, zone_id):
    if not supplier:
        return '供应商不存在'
    if not supplier.is_active:
        return '供应商已禁用'
    if zone_id and not supplier_serves_zone(supplier, zone_id):
        return f'{supplier.name} 未配置服务该配送区域，请先在供应商管理中勾选服务区域'
    return None
