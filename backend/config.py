import os


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_env_file(os.path.join(os.path.dirname(BASE_DIR), '.env'))
load_env_file(os.path.join(BASE_DIR, '.env'))


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://fresh_user:794423@localhost:3306/fresh_produce'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL')
    TENCENT_MAP_KEY = os.environ.get('TENCENT_MAP_KEY')
    TENCENT_MAP_JS_KEY = os.environ.get('TENCENT_MAP_JS_KEY') or os.environ.get('TENCENT_MAP_WEB_KEY') or TENCENT_MAP_KEY
    TENCENT_MAP_SERVER_KEY = os.environ.get('TENCENT_MAP_SERVER_KEY') or TENCENT_MAP_KEY
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', '8')) * 1024 * 1024
