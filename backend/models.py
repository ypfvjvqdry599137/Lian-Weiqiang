from app import db
from datetime import datetime

class CommunityStation(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自提点唯一ID')
    station_name = db.Column(db.String(100), nullable=False, comment='小区/自提点名称')
    address = db.Column(db.String(255), nullable=False, comment='详细自提地址')
    merchant_username = db.Column(db.String(50), unique=True, nullable=False, comment='合作商后台登录账号')
    merchant_password = db.Column(db.String(255), nullable=False, comment='合作商后台登录密码（加密存储）')
    commission_rate = db.Column(db.Numeric(5, 2), default=0.00, comment='默认该小区佣金抽成比例（如10.00 代表 10%）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def __repr__(self):
        return f'<CommunityStation {self.station_name}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='分类ID')
    name = db.Column(db.String(100), nullable=False, unique=True, comment='分类名称')
    icon = db.Column(db.String(255), nullable=True, comment='分类图标')
    sort_order = db.Column(db.Integer, default=0, comment='排序权重')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='商品ID')
    name = db.Column(db.String(200), nullable=False, comment='商品名称')
    description = db.Column(db.Text, nullable=True, comment='商品描述')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True, comment='所属分类ID')
    price = db.Column(db.Numeric(10, 2), nullable=False, comment='商品价格')
    original_price = db.Column(db.Numeric(10, 2), nullable=True, comment='原价（用于显示折扣）')
    image_url = db.Column(db.String(500), nullable=True, comment='商品主图')
    images = db.Column(db.Text, nullable=True, comment='商品图片列表(JSON格式)')
    unit = db.Column(db.String(20), nullable=False, default='份', comment='商品单位（份、斤、个等）')
    specs = db.Column(db.Text, nullable=True, comment='商品规格（JSON格式，支持多规格）')
    is_active = db.Column(db.Boolean, default=True, comment='是否上架')
    is_recommend = db.Column(db.Boolean, default=False, comment='是否推荐')
    sort_order = db.Column(db.Integer, default=0, comment='排序权重')
    sales_count = db.Column(db.Integer, default=0, comment='销量')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    category = db.relationship('Category', backref=db.backref('products', lazy=True))

    def __repr__(self):
        return f'<Product {self.name}>'

class ProductStock(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='库存记录ID')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, unique=True, comment='商品ID')
    total_stock = db.Column(db.Integer, nullable=False, default=0, comment='全城大仓总库存（所有用户下单扣减此字段）')
    lock_stock = db.Column(db.Integer, nullable=False, default=0, comment='锁定库存（用户下单未付款时的冻结库存）')
    warning_stock = db.Column(db.Integer, default=10, comment='库存预警阈值')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    product = db.relationship('Product', backref=db.backref('stock', uselist=False, lazy=True))

    def __repr__(self):
        return f'<ProductStock {self.product_id}>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID')
    openid = db.Column(db.String(100), unique=True, nullable=True, comment='微信OpenID')
    nickname = db.Column(db.String(50), nullable=True, comment='微信昵称')
    avatar = db.Column(db.String(500), nullable=True, comment='微信头像')
    phone = db.Column(db.String(20), nullable=True, comment='手机号')
    station_id = db.Column(db.Integer, db.ForeignKey('community_station.id'), nullable=True, comment='当前选择的自提点')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    station = db.relationship('CommunityStation', backref=db.backref('users', lazy=True))

    def __repr__(self):
        return f'<User {self.nickname}>'

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='购物车ID')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, comment='用户ID')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, comment='商品ID')
    quantity = db.Column(db.Integer, nullable=False, default=1, comment='数量')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    user = db.relationship('User', backref=db.backref('cart_items', lazy=True))
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))

    def __repr__(self):
        return f'<Cart {self.user_id} - {self.product_id}>'

class OrderMaster(db.Model):
    order_sn = db.Column(db.String(32), primary_key=True, comment='订单号（唯一业务流水号）')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, comment='用户ID')
    station_id = db.Column(db.Integer, nullable=False, comment='归属小区自提点ID')
    shipping_type = db.Column(db.SmallInteger, default=1, comment='配送模式：1-社区自提，2-同城快送（预留）')
    order_status = db.Column(db.SmallInteger, nullable=False, default=10, comment='订单状态机：10-待付款，20-待配货，30-配送中，40-待自提，50-已完成，60-已关闭')
    refund_status = db.Column(db.SmallInteger, nullable=False, default=0, comment='售后状态机：0-无售后，10-待合作商初审，20-待总后台终审，30-退款成功，40-售后驳回')
    total_amount = db.Column(db.Numeric(10, 2), default=0.00, comment='订单总金额')
    pickup_time = db.Column(db.String(50), nullable=True, comment='自提时间段')
    receiver_name = db.Column(db.String(50), nullable=True, comment='收货人姓名')
    receiver_phone = db.Column(db.String(20), nullable=True, comment='收货人电话')
    remark = db.Column(db.Text, nullable=True, comment='订单备注')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    user = db.relationship('User', backref=db.backref('orders', lazy=True))

    def __repr__(self):
        return f'<OrderMaster {self.order_sn}>'

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='订单项ID')
    order_sn = db.Column(db.String(32), db.ForeignKey('order_master.order_sn'), nullable=False, comment='订单号')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, comment='商品ID')
    product_name = db.Column(db.String(200), nullable=False, comment='商品名称快照')
    product_image = db.Column(db.String(500), nullable=True, comment='商品图片快照')
    price = db.Column(db.Numeric(10, 2), nullable=False, comment='商品价格快照')
    quantity = db.Column(db.Integer, nullable=False, default=1, comment='数量')
    unit = db.Column(db.String(20), nullable=False, default='份', comment='商品单位快照')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')

    # 关联
    order = db.relationship('OrderMaster', backref=db.backref('items', lazy=True))
    product = db.relationship('Product', backref=db.backref('order_items', lazy=True))

    def __repr__(self):
        return f'<OrderItem {self.order_sn} - {self.product_id}>'
