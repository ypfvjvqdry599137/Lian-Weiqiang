-- 鲜配居数据库 - 配送模式版本
-- 2026-06-29 更新：从自提点模式改为配送模式

CREATE DATABASE IF NOT EXISTS fresh_produce DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE fresh_produce;

-- ============================================
-- 1. 配送区域表（原自提点表改造）
-- ============================================
CREATE TABLE IF NOT EXISTS delivery_zone (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '配送区域ID',
    zone_name VARCHAR(100) NOT NULL COMMENT '区域名称',
    center_lng DECIMAL(10, 7) NOT NULL COMMENT '中心点经度',
    center_lat DECIMAL(10, 7) NOT NULL COMMENT '中心点纬度',
    radius INT NOT NULL DEFAULT 3000 COMMENT '配送半径(米)',
    delivery_fee DECIMAL(10, 2) DEFAULT 0.00 COMMENT '配送费',
    delivery_time VARCHAR(50) DEFAULT '30分钟' COMMENT '承诺送达时间',
    merchant_username VARCHAR(50) UNIQUE DEFAULT NULL COMMENT '后台登录账号',
    merchant_password VARCHAR(255) DEFAULT NULL COMMENT '后台登录密码',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配送区域表';

-- ============================================
-- 2. 用户地址表
-- ============================================
CREATE TABLE IF NOT EXISTS user_address (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '地址ID',
    user_id INT NOT NULL COMMENT '用户ID',
    receiver_name VARCHAR(50) NOT NULL COMMENT '收货人姓名',
    receiver_phone VARCHAR(20) NOT NULL COMMENT '收货人电话',
    province VARCHAR(50) DEFAULT NULL COMMENT '省份',
    city VARCHAR(50) DEFAULT NULL COMMENT '城市',
    district VARCHAR(50) DEFAULT NULL COMMENT '区县',
    detail_address VARCHAR(255) NOT NULL COMMENT '详细地址',
    full_address VARCHAR(500) NOT NULL COMMENT '完整地址',
    lng DECIMAL(10, 7) NOT NULL COMMENT '经度',
    lat DECIMAL(10, 7) NOT NULL COMMENT '纬度',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否默认地址',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户地址表';

-- ============================================
-- 3. 商品分类表（保持不变）
-- ============================================
CREATE TABLE IF NOT EXISTS category (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '分类名称',
    icon VARCHAR(255) DEFAULT NULL COMMENT '分类图标',
    sort_order INT DEFAULT 0 COMMENT '排序权重',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表';

-- ============================================
-- 4. 商品表（保持不变）
-- ============================================
CREATE TABLE IF NOT EXISTS product (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    name VARCHAR(200) NOT NULL COMMENT '商品名称',
    description TEXT DEFAULT NULL COMMENT '商品描述',
    category_id INT DEFAULT NULL COMMENT '所属分类ID',
    price DECIMAL(10,2) NOT NULL COMMENT '商品价格',
    original_price DECIMAL(10,2) DEFAULT NULL COMMENT '原价（用于显示折扣）',
    image_url VARCHAR(500) DEFAULT NULL COMMENT '商品主图',
    images TEXT DEFAULT NULL COMMENT '商品图片列表(JSON格式)',
    unit VARCHAR(20) NOT NULL DEFAULT '份' COMMENT '商品单位（份、斤、个等）',
    specs TEXT DEFAULT NULL COMMENT '商品规格（JSON格式，支持多规格）',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否上架',
    is_recommend BOOLEAN DEFAULT FALSE COMMENT '是否推荐',
    sort_order INT DEFAULT 0 COMMENT '排序权重',
    sales_count INT DEFAULT 0 COMMENT '销量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- ============================================
-- 5. 商品库存表（保持不变）
-- ============================================
CREATE TABLE IF NOT EXISTS product_stock (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '库存记录ID',
    product_id INT NOT NULL UNIQUE COMMENT '商品ID',
    total_stock INT NOT NULL DEFAULT 0 COMMENT '总库存',
    lock_stock INT NOT NULL DEFAULT 0 COMMENT '锁定库存',
    warning_stock INT DEFAULT 10 COMMENT '库存预警阈值',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品库存表';

-- ============================================
-- 6. 用户表（调整：移除station_id）
-- ============================================
CREATE TABLE IF NOT EXISTS user (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    openid VARCHAR(100) UNIQUE DEFAULT NULL COMMENT '微信OpenID',
    nickname VARCHAR(50) DEFAULT NULL COMMENT '微信昵称',
    avatar VARCHAR(500) DEFAULT NULL COMMENT '微信头像',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    default_address_id INT DEFAULT NULL COMMENT '默认地址ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ============================================
-- 7. 购物车表（保持不变）
-- ============================================
CREATE TABLE IF NOT EXISTS cart (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '购物车ID',
    user_id INT NOT NULL COMMENT '用户ID',
    product_id INT NOT NULL COMMENT '商品ID',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_product (user_id, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='购物车表';

-- ============================================
-- 8. 订单主表（改造为配送模式）
-- ============================================
CREATE TABLE IF NOT EXISTS order_master (
    order_sn VARCHAR(32) PRIMARY KEY COMMENT '订单号',
    user_id INT NOT NULL COMMENT '用户ID',
    address_id INT DEFAULT NULL COMMENT '收货地址ID',
    zone_id INT DEFAULT NULL COMMENT '配送区域ID',
    order_status SMALLINT NOT NULL DEFAULT 10 COMMENT '状态：10-待付款，20-待配货，30-配送中，40-已送达，50-已完成，60-已取消',
    refund_status SMALLINT NOT NULL DEFAULT 0 COMMENT '售后状态',
    total_amount DECIMAL(10,2) DEFAULT 0.00 COMMENT '商品总额',
    delivery_fee DECIMAL(10,2) DEFAULT 0.00 COMMENT '配送费',
    final_amount DECIMAL(10,2) DEFAULT 0.00 COMMENT '实付金额',
    receiver_name VARCHAR(50) DEFAULT NULL COMMENT '收货人',
    receiver_phone VARCHAR(20) DEFAULT NULL COMMENT '收货电话',
    receiver_address VARCHAR(500) DEFAULT NULL COMMENT '收货地址',
    receiver_lng DECIMAL(10,7) DEFAULT NULL COMMENT '收货地址经度',
    receiver_lat DECIMAL(10,7) DEFAULT NULL COMMENT '收货地址纬度',
    remark TEXT DEFAULT NULL COMMENT '订单备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (order_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单主表';

-- ============================================
-- 9. 订单项表（保持不变）
-- ============================================
CREATE TABLE IF NOT EXISTS order_item (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '订单项ID',
    order_sn VARCHAR(32) NOT NULL COMMENT '订单号',
    product_id INT NOT NULL COMMENT '商品ID',
    product_name VARCHAR(200) NOT NULL COMMENT '商品名称',
    product_image VARCHAR(500) DEFAULT NULL COMMENT '商品图片',
    price DECIMAL(10,2) NOT NULL COMMENT '商品价格',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    unit VARCHAR(20) NOT NULL DEFAULT '份' COMMENT '单位',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (order_sn) REFERENCES order_master(order_sn) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单项表';

-- ============================================
-- 插入测试数据
-- ============================================

-- 配送区域测试数据
INSERT INTO delivery_zone (zone_name, center_lng, center_lat, radius, delivery_fee, delivery_time, merchant_username, merchant_password) VALUES
('望京站', 116.470090, 39.989100, 3000, 5.00, '30分钟', 'wangjing', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWxJQzO.p6W'),
('国贸站', 116.460840, 39.909270, 3000, 5.00, '30分钟', 'guomao', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWxJQzO.p6W');

-- 分类数据
INSERT INTO category (name, icon, sort_order) VALUES
('新鲜蔬菜', '🥬', 1),
('时令水果', '🍎', 2),
('肉禽蛋奶', '🥩', 3),
('海鲜水产', '🐟', 4),
('粮油调味', '🌾', 5);

-- 商品数据
INSERT INTO product (name, description, category_id, price, original_price, unit, is_recommend, sort_order, sales_count) VALUES
('有机西红柿', '新鲜有机种植，自然成熟，酸甜可口', 1, 8.99, 12.99, '斤', TRUE, 10, 156),
('上海青', '鲜嫩上海青，当天采摘', 1, 3.99, 5.99, '斤', FALSE, 9, 234),
('西兰花', '优质西兰花，营养丰富', 1, 6.99, 8.99, '斤', FALSE, 8, 89),
('红富士苹果', '山东红富士，脆甜多汁', 2, 12.99, 15.99, '斤', TRUE, 10, 321),
('赣南脐橙', '正宗赣南脐橙，酸甜适中', 2, 9.99, 12.99, '斤', TRUE, 9, 456),
('草莓', '新鲜草莓，香甜可口', 2, 25.99, 32.99, '盒', FALSE, 8, 123),
('土鸡蛋', '散养土鸡蛋，营养健康', 3, 1.99, 2.50, '个', TRUE, 10, 567),
('五花肉', '新鲜五花肉，肥瘦相间', 3, 32.99, 38.99, '斤', FALSE, 9, 234),
('鲜牛奶', '巴氏杀菌鲜牛奶', 3, 8.99, 10.99, '盒', FALSE, 8, 345),
('鲜活鲈鱼', '当天捕捞鲜活鲈鱼', 4, 28.99, 35.99, '条', TRUE, 10, 189),
('基围虾', '鲜活基围虾', 4, 58.99, 68.99, '斤', FALSE, 9, 156),
('五常大米', '正宗五常稻花香大米', 5, 5.99, 7.99, '斤', TRUE, 10, 678),
('东北大豆油', '非转基因东北大豆油', 5, 45.99, 55.99, '桶', FALSE, 9, 234),
('生抽酱油', '酿造生抽，鲜味十足', 5, 12.99, 15.99, '瓶', FALSE, 8, 345);

-- 库存数据
INSERT INTO product_stock (product_id, total_stock, lock_stock, warning_stock) VALUES
(1, 200, 0, 20), (2, 300, 0, 30), (3, 150, 0, 15), (4, 250, 0, 25),
(5, 180, 0, 18), (6, 80, 0, 10), (7, 500, 0, 50), (8, 100, 0, 10),
(9, 200, 0, 20), (10, 50, 0, 5), (11, 30, 0, 5), (12, 400, 0, 40),
(13, 100, 0, 10), (14, 150, 0, 15);

-- 测试用户
INSERT INTO user (nickname, phone) VALUES ('测试用户', '13800138000');

-- 测试地址
INSERT INTO user_address (user_id, receiver_name, receiver_phone, province, city, district, detail_address, full_address, lng, lat, is_default) VALUES
(1, '张三', '13800138000', '北京市', '北京市', '朝阳区', '望京SOHO塔1', '北京市北京市朝阳区望京SOHO塔1', 116.470090, 39.989100, TRUE),
(1, '李四', '13900139000', '北京市', '北京市', '朝阳区', '国贸大厦A座', '北京市北京市朝阳区国贸大厦A座', 116.460840, 39.909270, FALSE);