from pathlib import Path

from app import create_app
from extensions import db


DEV_DB = Path(__file__).with_name("fresh_produce_dev.sqlite")


class DevConfig:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DEV_DB.as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


def create_dev_app():
    return create_app(DevConfig)


def seed_dev_data():
    from models import Supplier

    db.create_all()

    suppliers = [
        {
            "name": "绿鲜蔬菜供应商",
            "contact_person": "王经理",
            "phone": "13900139000",
            "username": "veggie_supplier",
            "password": "123456",
        },
        {
            "name": "禽肉蛋品供应商",
            "contact_person": "李经理",
            "phone": "13800138111",
            "username": "meat_supplier",
            "password": "123456",
        },
    ]

    for supplier_data in suppliers:
        exists = Supplier.query.filter_by(username=supplier_data["username"]).first()
        if not exists:
            db.session.add(Supplier(**supplier_data, is_active=True))

    db.session.commit()


if __name__ == "__main__":
    app = create_dev_app()
    with app.app_context():
        seed_dev_data()
        print(f"Dev database ready: {DEV_DB}")

    app.run(host="0.0.0.0", port=5000, debug=True)
