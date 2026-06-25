from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)

    # Import models here to avoid circular imports
    import models

    from admin_routes import admin_bp
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return "Hello, Fresh Produce Mini Program Backend!"

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
