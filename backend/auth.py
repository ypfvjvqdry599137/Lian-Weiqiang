import hashlib

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


CLIENT_TOKEN_AGE = 7 * 24 * 60 * 60
STAFF_TOKEN_AGE = 12 * 60 * 60


def token_binding(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


def _serializer(role):
    secret = current_app.config.get('AUTH_SIGNING_KEY')
    if not secret or len(secret) < 32:
        raise RuntimeError('AUTH_SIGNING_KEY must contain at least 32 characters')
    return URLSafeTimedSerializer(secret, salt=f'fresh-produce-{role}-v1')


def issue_token(role, subject, binding):
    return _serializer(role).dumps({
        'sub': int(subject),
        'bind': token_binding(binding)
    })


def bearer_token():
    scheme, separator, token = request.headers.get('Authorization', '').partition(' ')
    if separator and scheme.lower() == 'bearer' and token and not any(char.isspace() for char in token):
        return token
    return None


def read_token(role, max_age):
    token = bearer_token()
    if not token:
        return None
    try:
        payload = _serializer(role).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get('sub'), int) or payload['sub'] <= 0:
        return None
    if not isinstance(payload.get('bind'), str):
        return None
    return payload


def require_admin():
    if request.method == 'OPTIONS':
        return None
    password_hash = current_app.config.get('ADMIN_PASSWORD_HASH')
    payload = read_token('admin', STAFF_TOKEN_AGE)
    if not password_hash or not payload or payload['bind'] != token_binding(password_hash):
        return jsonify({'message': '管理员登录已失效，请重新登录'}), 401
    return None
