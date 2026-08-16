import base64
import json
import os
import secrets
import time
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cryptography import x509
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from flask import current_app


class WeChatPayError(RuntimeError):
    pass


class WeChatPayConfigError(WeChatPayError):
    pass


def _config_value(*names, default=None):
    for name in names:
        value = current_app.config.get(name)
        if value not in (None, ''):
            return value
        env_value = os.environ.get(name)
        if env_value not in (None, ''):
            return env_value
    return default


def get_mini_program_app_id():
    app_id = _config_value('WECHAT_MINI_PROGRAM_APPID')
    if not app_id:
        raise WeChatPayConfigError('未配置微信小程序 AppID')
    return app_id


def get_mini_program_secret():
    secret = _config_value('WECHAT_MINI_PROGRAM_SECRET')
    if not secret:
        raise WeChatPayConfigError('未配置微信小程序 AppSecret')
    return secret


def get_pay_mchid():
    mchid = _config_value('WECHAT_PAY_MCHID')
    if not mchid:
        raise WeChatPayConfigError('未配置微信支付商户号')
    return mchid


def get_pay_api_v3_key():
    api_v3_key = _config_value('WECHAT_PAY_API_V3_KEY')
    if not api_v3_key:
        raise WeChatPayConfigError('未配置微信支付 APIv3 密钥')
    if len(api_v3_key) != 32:
        raise WeChatPayConfigError('微信支付 APIv3 密钥必须是 32 位字符串')
    return api_v3_key.encode('utf-8')


def get_pay_serial_no():
    serial_no = _config_value('WECHAT_PAY_SERIAL_NO')
    if not serial_no:
        raise WeChatPayConfigError('未配置微信支付商户证书序列号')
    return serial_no


def get_pay_notify_url():
    notify_url = _config_value('WECHAT_PAY_NOTIFY_URL')
    if notify_url:
        return notify_url

    base_url = _config_value('PUBLIC_BASE_URL')
    if not base_url:
        raise WeChatPayConfigError('未配置微信支付通知地址，也未配置 PUBLIC_BASE_URL')

    return base_url.rstrip('/') + '/client/wechat/pay/notify'


def _normalize_private_key_pem(raw_pem):
    if not raw_pem:
        return raw_pem
    if isinstance(raw_pem, bytes):
        raw_pem = raw_pem.decode('utf-8')
    if '\\n' in raw_pem and 'BEGIN PRIVATE KEY' in raw_pem:
        raw_pem = raw_pem.replace('\\n', '\n')
    return raw_pem.encode('utf-8')


@lru_cache(maxsize=1)
def load_pay_private_key():
    pem_text = _config_value('WECHAT_PAY_PRIVATE_KEY')
    key_path = _config_value('WECHAT_PAY_PRIVATE_KEY_PATH')

    if pem_text:
        pem_bytes = _normalize_private_key_pem(pem_text)
    elif key_path:
        with open(key_path, 'rb') as key_file:
            pem_bytes = key_file.read()
    else:
        raise WeChatPayConfigError('未配置微信支付私钥')

    return load_pem_private_key(pem_bytes, password=None)


def _sign_sha256_with_rsa(message):
    private_key = load_pay_private_key()
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


def _build_auth_header(method, request_path, body_text, nonce_str, timestamp):
    canonical_message = f'{method}\n{request_path}\n{timestamp}\n{nonce_str}\n{body_text}\n'
    signature = _sign_sha256_with_rsa(canonical_message)
    return (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{get_pay_mchid()}",'
        f'nonce_str="{nonce_str}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{get_pay_serial_no()}",'
        f'signature="{signature}"'
    )


def _wechat_api_request(method, path, body=None):
    url = 'https://api.mch.weixin.qq.com' + path
    body_text = '' if body is None else json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    body_bytes = body_text.encode('utf-8') if body_text else None
    timestamp = str(int(time.time()))
    nonce_str = secrets.token_hex(16)
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': _build_auth_header(method, path, body_text, nonce_str, timestamp)
    }

    request = Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            response_text = response.read().decode('utf-8')
    except HTTPError as exc:
        error_text = exc.read().decode('utf-8') if exc.fp else ''
        try:
            error_payload = json.loads(error_text) if error_text else {}
        except json.JSONDecodeError:
            error_payload = {}
        message = error_payload.get('message') or error_payload.get('msg') or error_text or str(exc)
        raise WeChatPayError(message) from exc
    except URLError as exc:
        raise WeChatPayError('微信支付请求失败，请检查网络或支付配置') from exc

    if not response_text:
        return {}

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise WeChatPayError('微信支付响应内容不是有效的 JSON') from exc

    return payload


def exchange_code_for_openid(code):
    if not code:
        raise WeChatPayError('微信登录 code 不能为空')

    params = urlencode({
        'appid': get_mini_program_app_id(),
        'secret': get_mini_program_secret(),
        'js_code': code,
        'grant_type': 'authorization_code'
    })
    url = f'https://api.weixin.qq.com/sns/jscode2session?{params}'
    try:
        with urlopen(Request(url, method='GET'), timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise WeChatPayError('微信登录接口请求失败') from exc
    except URLError as exc:
        raise WeChatPayError('微信登录接口请求失败，请检查网络') from exc
    except json.JSONDecodeError as exc:
        raise WeChatPayError('微信登录接口返回了无效数据') from exc

    if payload.get('openid'):
        return payload

    raise WeChatPayError(payload.get('errmsg') or payload.get('message') or '微信登录失败')


def _decimal_to_fen(amount):
    decimal_amount = Decimal(str(amount or '0'))
    return int((decimal_amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def build_request_payment_params(prepay_id):
    time_stamp = str(int(time.time()))
    nonce_str = secrets.token_hex(16)
    package = f'prepay_id={prepay_id}'
    sign_string = f'{get_mini_program_app_id()}\n{time_stamp}\n{nonce_str}\n{package}\n'
    pay_sign = _sign_sha256_with_rsa(sign_string)

    return {
        'timeStamp': time_stamp,
        'nonceStr': nonce_str,
        'package': package,
        'signType': 'RSA',
        'paySign': pay_sign
    }


def create_jsapi_prepay(order_sn, description, amount, openid):
    if not openid:
        raise WeChatPayError('用户尚未绑定微信 OpenID')

    description = (description or '微信支付订单').strip()[:127]

    payload = {
        'appid': get_mini_program_app_id(),
        'mchid': get_pay_mchid(),
        'description': description,
        'out_trade_no': order_sn,
        'notify_url': get_pay_notify_url(),
        'attach': order_sn,
        'amount': {
            'total': _decimal_to_fen(amount),
            'currency': 'CNY'
        },
        'payer': {
            'openid': openid
        }
    }

    response = _wechat_api_request('POST', '/v3/pay/transactions/jsapi', payload)
    prepay_id = response.get('prepay_id')
    if not prepay_id:
        raise WeChatPayError('微信支付统一下单失败，未返回 prepay_id')

    return {
        'prepay_id': prepay_id,
        'payment': build_request_payment_params(prepay_id)
    }


def query_jsapi_order_by_out_trade_no(order_sn):
    request_path = f'/v3/pay/transactions/out-trade-no/{quote(order_sn, safe="")}?mchid={get_pay_mchid()}'
    return _wechat_api_request('GET', request_path)


def _decrypt_aes_gcm(ciphertext, nonce, associated_data=None):
    aesgcm = AESGCM(get_pay_api_v3_key())
    ciphertext_bytes = base64.b64decode(ciphertext)
    associated_bytes = associated_data.encode('utf-8') if associated_data not in (None, '') else None
    plain_bytes = aesgcm.decrypt(nonce.encode('utf-8'), ciphertext_bytes, associated_bytes)
    return plain_bytes.decode('utf-8')


def _extract_encrypted_block(item):
    encrypted = item.get('encrypt_certificate') or {}
    return {
        'algorithm': encrypted.get('algorithm') or item.get('algorithm'),
        'nonce': encrypted.get('nonce') or item.get('nonce'),
        'associated_data': encrypted.get('associated_data') or item.get('associated_data'),
        'ciphertext': encrypted.get('ciphertext') or item.get('ciphertext')
    }


@lru_cache(maxsize=1)
def _load_platform_certificate_map():
    payload = _wechat_api_request('GET', '/v3/certificates')
    data = payload.get('data') or []
    if not data:
        raise WeChatPayError('未获取到微信支付平台证书')

    certificates = {}
    for item in data:
        serial_no = item.get('serial_no')
        if not serial_no:
            continue

        encrypted = _extract_encrypted_block(item)
        if encrypted['algorithm'] and encrypted['algorithm'] != 'AEAD_AES_256_GCM':
            raise WeChatPayError('微信支付平台证书加密算法不受支持')
        if not encrypted['nonce'] or not encrypted['ciphertext']:
            raise WeChatPayError('微信支付平台证书信息不完整')

        pem_text = _decrypt_aes_gcm(
            encrypted['ciphertext'],
            encrypted['nonce'],
            encrypted['associated_data']
        )
        certificates[serial_no] = x509.load_pem_x509_certificate(pem_text.encode('utf-8'))

    if not certificates:
        raise WeChatPayError('未解析到任何微信支付平台证书')

    return certificates


def clear_platform_certificate_cache():
    _load_platform_certificate_map.cache_clear()


def _get_platform_certificate(serial_no):
    if not serial_no:
        raise WeChatPayError('回调缺少 Wechatpay-Serial')

    certs = _load_platform_certificate_map()
    certificate = certs.get(serial_no)
    if certificate is not None:
        return certificate

    clear_platform_certificate_cache()
    certs = _load_platform_certificate_map()
    certificate = certs.get(serial_no)
    if certificate is not None:
        return certificate

    raise WeChatPayError(f'未找到序列号为 {serial_no} 的微信支付平台证书')


def verify_wechatpay_callback(headers, body_text):
    timestamp = headers.get('Wechatpay-Timestamp')
    nonce = headers.get('Wechatpay-Nonce')
    signature = headers.get('Wechatpay-Signature')
    serial_no = headers.get('Wechatpay-Serial')

    missing = []
    if not timestamp:
        missing.append('Wechatpay-Timestamp')
    if not nonce:
        missing.append('Wechatpay-Nonce')
    if not signature:
        missing.append('Wechatpay-Signature')
    if not serial_no:
        missing.append('Wechatpay-Serial')
    if missing:
        raise WeChatPayError('回调缺少签名头：' + '、'.join(missing))

    try:
        signature_bytes = base64.b64decode(signature)
    except Exception as exc:
        raise WeChatPayError('微信支付回调签名不是有效的 Base64') from exc

    message = f'{timestamp}\n{nonce}\n{body_text or ""}\n'.encode('utf-8')
    certificate = _get_platform_certificate(serial_no)

    try:
        certificate.public_key().verify(
            signature_bytes,
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except InvalidSignature as exc:
        raise WeChatPayError('微信支付回调签名校验失败') from exc


def decrypt_wechatpay_resource(resource):
    if not isinstance(resource, dict):
        raise WeChatPayError('微信支付回调缺少 resource 字段')

    algorithm = resource.get('algorithm')
    if algorithm and algorithm != 'AEAD_AES_256_GCM':
        raise WeChatPayError('微信支付回调加密算法不受支持')

    nonce = resource.get('nonce')
    ciphertext = resource.get('ciphertext')
    if not nonce or not ciphertext:
        raise WeChatPayError('微信支付回调加密字段不完整')

    try:
        plain_text = _decrypt_aes_gcm(
            ciphertext,
            nonce,
            resource.get('associated_data')
        )
    except InvalidTag as exc:
        raise WeChatPayError('微信支付回调解密失败') from exc

    try:
        return json.loads(plain_text)
    except json.JSONDecodeError as exc:
        raise WeChatPayError('微信支付回调解密后内容不是有效的 JSON') from exc


def parse_wechatpay_notification(headers, body_text):
    try:
        payload = json.loads(body_text or '{}')
    except json.JSONDecodeError as exc:
        raise WeChatPayError('微信支付回调内容不是有效的 JSON') from exc

    verify_wechatpay_callback(headers, body_text or '')
    return payload, decrypt_wechatpay_resource(payload.get('resource'))
