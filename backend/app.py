from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from extensions import db
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)
    db.init_app(app)

    # 导入模型
    import models


    # 导入并注册蓝图
    from admin_routes import admin_bp
    from client_routes import client_bp
    from merchant_routes import merchant_bp
    from supplier_routes import supplier_bp
    
    app.register_blueprint(admin_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(merchant_bp)
    app.register_blueprint(supplier_bp)

    @app.route('/')
    def index():
        return "Hello, Fresh Produce Mini Program Backend!"

    # Serve static files from the 'admin-panel' directory
    # This assumes admin-panel is a sibling directory to backend
    # We need to get the absolute path to the admin-panel directory
    ADMIN_PANEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'admin-panel')

    @app.route('/admin-panel/<path:filename>')
    def serve_admin_panel_static(filename):
        return send_from_directory(ADMIN_PANEL_DIR, filename)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
