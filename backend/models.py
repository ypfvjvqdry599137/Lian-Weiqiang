from app import db

class CommunityStation(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自提点唯一ID')
    station_name = db.Column(db.String(100), nullable=False, comment='小区/自提点名称')
    address = db.Column(db.String(255), nullable=False, comment='详细自提地址')
    merchant_username = db.Column(db.String(50), unique=True, nullable=False, comment='合作商后台登录账号')
    merchant_password = db.Column(db.String(255), nullable=False, comment='合作商后台登录密码（加密存储）')
    commission_rate = db.Column(db.Numeric(5, 2), default=0.00, comment='默认该小区佣金抽成比例（如10.00 代表 10%）')

    def __repr__(self):
        return f'<CommunityStation {self.station_name}>'

class ProductStock(db.Model):
    product_id = db.Column(db.Integer, primary_key=True, comment='商品ID')
    total_stock = db.Column(db.Integer, nullable=False, default=0, comment='全城大仓总库存（所有用户下单扣减此字段）')
    lock_stock = db.Column(db.Integer, nullable=False, default=0, comment='锁定库存（用户下单未付款时的冻结库存）')

    def __repr__(self):
        return f'<ProductStock {self.product_id}>'

class OrderMaster(db.Model):
    order_sn = db.Column(db.String(32), primary_key=True, comment='订单号（唯一业务流水号）')
    station_id = db.Column(db.Integer, nullable=False, comment='归属小区自提点ID')
    shipping_type = db.Column(db.SmallInteger, default=1, comment='配送模式：1-社区自提，2-同城快送（预留）')
    order_status = db.Column(db.SmallInteger, nullable=False, default=10, comment='订单状态机')
    refund_status = db.Column(db.SmallInteger, nullable=False, default=0, comment='售后状态机')

    def __repr__(self):
        return f'<OrderMaster {self.order_sn}>'
