from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def flash_is_active(product, now=None):
    now = now or datetime.utcnow()
    return bool(product.is_active and product.flash_price is not None
                and product.flash_start_at and product.flash_end_at
                and product.flash_start_at <= now < product.flash_end_at)


def effective_product_price(product, now=None):
    return product.flash_price if flash_is_active(product, now) else product.price


def flash_payload(product, now=None):
    active = flash_is_active(product, now)
    return {
        'flash_active': active,
        'flash_price': str(product.flash_price) if product.flash_price is not None else None,
        'flash_start_at': product.flash_start_at.isoformat() + 'Z' if product.flash_start_at else None,
        'flash_end_at': product.flash_end_at.isoformat() + 'Z' if product.flash_end_at else None,
    }


def _parse_utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('活动时间必须包含时区')
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def apply_flash_payload(product, data):
    if not any(key in data for key in ('flash_price', 'flash_start_at', 'flash_end_at')):
        return
    values = [data.get('flash_price'), data.get('flash_start_at'), data.get('flash_end_at')]
    if all(value in (None, '') for value in values):
        product.flash_price = product.flash_start_at = product.flash_end_at = None
        return
    if any(value in (None, '') for value in values):
        raise ValueError('限时特惠需同时填写特惠价、开始和结束时间')
    try:
        price = Decimal(str(values[0]))
        start = _parse_utc(values[1])
        end = _parse_utc(values[2])
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise ValueError('特惠价格或活动时间格式不正确') from None
    if not price.is_finite() or price <= 0 or price.as_tuple().exponent < -2 or price >= product.price:
        raise ValueError('特惠价须大于0、低于商品原售价，最多两位小数')
    if start >= end:
        raise ValueError('活动结束时间必须晚于开始时间')
    product.flash_price, product.flash_start_at, product.flash_end_at = price, start, end
