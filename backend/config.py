import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://fresh_user:794423@localhost:3306/fresh_produce'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or \
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', '8')) * 1024 * 1024
