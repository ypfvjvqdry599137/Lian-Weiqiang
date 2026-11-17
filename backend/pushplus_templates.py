"""Editable supplier notification bodies with safe, named placeholders."""

from string import Formatter

from models import SupplierPushTemplate


NOTICE_KINDS = {
    'new': {
        'label': '新备货单',
        'title': '鲜配居：新备货单',
        'default': '订单 {order_sn} 已付款，请安排备货。备货单 #{supplier_order_id}。{items}。登录核对：{supplier_url}',
    },
    'hold': {
        'label': '暂停备货',
        'title': '鲜配居：暂停备货',
        'default': '订单 {order_sn}：{reason}。请立即登录后台核对：{supplier_url}',
    },
    'resume': {
        'label': '恢复备货',
        'title': '鲜配居：恢复备货',
        'default': '订单 {order_sn} 的退款暂停已解除，请登录后台核对后继续备货：{supplier_url}',
    },
    'stop': {
        'label': '停止备货',
        'title': '鲜配居：停止备货',
        'default': '订单 {order_sn}：{reason}。请立即登录后台核对：{supplier_url}',
    },
}

PLACEHOLDERS = {'order_sn', 'supplier_order_id', 'items', 'reason', 'supplier_url'}


def validate_template(kind, content):
    if kind not in NOTICE_KINDS:
        raise ValueError('未知的通知类型')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('通知内容不能为空')
    content = content.strip()
    if len(content) > 1000:
        raise ValueError('通知内容不能超过 1000 字')
    try:
        fields = set()
        for _, field, format_spec, conversion in Formatter().parse(content):
            if field is None:
                continue
            if field not in PLACEHOLDERS or format_spec or conversion:
                raise ValueError('只能使用页面列出的变量，不能访问变量属性或添加格式指令')
            fields.add(field)
    except ValueError as exc:
        if '只能使用' in str(exc):
            raise
        raise ValueError('变量的大括号格式不正确') from exc
    if 'order_sn' not in fields:
        raise ValueError('通知内容必须包含 {order_sn}，方便供应商核对订单')
    return content


def template_rows():
    saved = {row.kind: row.content for row in SupplierPushTemplate.query.all()}
    return [
        {
            'kind': kind,
            'label': details['label'],
            'title': details['title'],
            'content': saved.get(kind, details['default']),
            'is_custom': kind in saved,
        }
        for kind, details in NOTICE_KINDS.items()
    ]


def render_notice(kind, values):
    details = NOTICE_KINDS[kind]
    saved = SupplierPushTemplate.query.filter_by(kind=kind).first()
    content = saved.content if saved else details['default']
    return details['title'], content.format_map(values)
