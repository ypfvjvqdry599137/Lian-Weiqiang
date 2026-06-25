import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://fresh_user:794423@localhost:3306/fresh_produce'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
