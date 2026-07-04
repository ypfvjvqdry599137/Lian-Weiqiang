from app import db
from datetime import datetime

# ============================================
# 配送区域模型
# ============================================
class DeliveryZone(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='配送区域ID')
    zone_name = db.Column(db.String(100), nullable=False, comment='区域名称')
    center_lng = db.Column(db.Numeric(10, 7), nullable=False, comment='中心点经度')
    center_lat = db.Column(db.Numeric(10, 7), nullable=False, comment='中心点纬度')
    radius = db.Column(db.Integer, default=3000, comment='配送半径(米)')
    delivery_fee = db.Column(db.Numeric(10, 2), default=0.00, comment='配送费')
    delivery_time = db.Column(db.String(50), default='30分钟', comment='承诺送达时间')
    merchant_username = db.Column(db.String(50), unique=True, nullable=True, comment='后台登录账号')
    merchant_password = db.Column(db.String(255), nullable=True, comment='后台登录密码')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def __repr__(self):
        return f'<DeliveryZone {self.zone_name}>'

# ============================================
# 用户地址模型
# ============================================
class UserAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='地址ID')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, comment='用户ID')
    receiver_name = db.Column(db.String(50), nullable=False, comment='收货人姓名')
    receiver_phone = db.Column(db.String(20), nullable=False, comment='收货人电话')
    province = db.Column(db.String(50), nullable=True, comment='省份')
    city = db.Column(db.String(50), nullable=True, comment='城市')
    district = db.Column(db.String(50), nullable=True, comment='区县')
    detail_address = db.Column(db.String(255), nullable=False, comment='详细地址')
    full_address = db.Column(db.String(500), nullable=False, comment='完整地址')
    lng = db.Column(db.Numeric(10, 7), nullable=False, comment='经度')
    lat = db.Column(db.Numeric(10, 7), nullable=False, comment='纬度')
    is_default = db.Column(db.Boolean, default=False, comment='是否默认地址')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    user = db.relationship('User', backref=db.backref('addresses', lazy=True))

    def __repr__(self):
        return f'<UserAddress {self.full_address}>'

# ============================================
# 商品分类模型
# ============================================
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

# ============================================
# 商品模型
# ============================================
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

# ============================================
# 商品库存模型
# ============================================
class ProductStock(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='库存记录ID')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, unique=True, comment='商品ID')
    total_stock = db.Column(db.Integer, nullable=False, default=0, comment='总库存')
    lock_stock = db.Column(db.Integer, nullable=False, default=0, comment='锁定库存')
    warning_stock = db.Column(db.Integer, default=10, comment='库存预警阈值')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    product = db.relationship('Product', backref=db.backref('stock', uselist=False, lazy=True))

    def __repr__(self):
        return f'<ProductStock {self.product_id}>'

# ============================================
# 用户模型
# ============================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID')
    openid = db.Column(db.String(100), unique=True, nullable=True, comment='微信OpenID')
    nickname = db.Column(db.String(50), nullable=True, comment='微信昵称')
    avatar = db.Column(db.String(500), nullable=True, comment='微信头像')
    phone = db.Column(db.String(20), nullable=True, comment='手机号')
    default_address_id = db.Column(db.Integer, nullable=True, comment='默认地址ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def __repr__(self):
        return f'<User {self.nickname}>'

# ============================================
# 购物车模型
# ============================================
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

# ============================================
# 订单主模型（配送模式）
# ============================================
class OrderMaster(db.Model):
    order_sn = db.Column(db.String(32), primary_key=True, comment='订单号')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, comment='用户ID')
    address_id = db.Column(db.Integer, nullable=True, comment='收货地址ID')
    zone_id = db.Column(db.Integer, nullable=True, comment='配送区域ID')
    order_status = db.Column(db.SmallInteger, nullable=False, default=10, comment='状态：10-待付款，20-待配货，30-配送中，40-已送达，50-已完成，60-已取消')
    refund_status = db.Column(db.SmallInteger, nullable=False, default=0, comment='售后状态')
    total_amount = db.Column(db.Numeric(10, 2), default=0.00, comment='商品总额')
    delivery_fee = db.Column(db.Numeric(10, 2), default=0.00, comment='配送费')
    final_amount = db.Column(db.Numeric(10, 2), default=0.00, comment='实付金额')
    receiver_name = db.Column(db.String(50), nullable=True, comment='收货人')
    receiver_phone = db.Column(db.String(20), nullable=True, comment='收货电话')
    receiver_address = db.Column(db.String(500), nullable=True, comment='收货地址')
    receiver_lng = db.Column(db.Numeric(10, 7), nullable=True, comment='收货地址经度')
    receiver_lat = db.Column(db.Numeric(10, 7), nullable=True, comment='收货地址纬度')
    remark = db.Column(db.Text, nullable=True, comment='订单备注')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 关联
    user = db.relationship('User', backref=db.backref('orders', lazy=True))

    def __repr__(self):
        return f'<OrderMaster {self.order_sn}>'

# ============================================
# 订单项模型
# ============================================
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='订单项ID')
    order_sn = db.Column(db.String(32), db.ForeignKey('order_master.order_sn'), nullable=False, comment='订单号')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, comment='商品ID')
    product_name = db.Column(db.String(200), nullable=False, comment='商品名称')
    product_image = db.Column(db.String(500), nullable=True, comment='商品图片')
    price = db.Column(db.Numeric(10, 2), nullable=False, comment='商品价格')
    quantity = db.Column(db.Integer, nullable=False, default=1, comment='数量')
    unit = db.Column(db.String(20), nullable=False, default='份', comment='单位')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')

    # 关联
    order = db.relationship('OrderMaster', backref=db.backref('items', lazy=True))
    product = db.relationship('Product', backref=db.backref('order_items', lazy=True))

    def __repr__(self):
        return f'<OrderItem {self.order_sn} - {self.product_id}>'