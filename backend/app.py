from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db = SQLAlchemy(app)

# Import models and routes
import models
from admin_routes import admin_bp
from client_routes import client_bp
from merchant_routes import merchant_bp

app.register_blueprint(admin_bp)
app.register_blueprint(client_bp)
app.register_blueprint(merchant_bp)

@app.route('/')
def index():
    return "Hello, Fresh Produce Mini Program Backend!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
