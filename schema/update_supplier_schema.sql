-- 仅用于更新现有 fresh_produce 数据库，添加供应商系统相关表和数据
-- 注意：本脚本假设 fresh_produce 数据库已存在，且核心表 (user, product, category, delivery_zone, order_master 等) 已存在并包含数据。

USE fresh_produce;

-- ============================================
-- 2. 供应商表
-- ============================================
CREATE TABLE IF NOT EXISTS supplier (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '供应商ID',
    name VARCHAR(200) NOT NULL COMMENT '供应商名称',
    contact_person VARCHAR(100) DEFAULT NULL COMMENT '联系人',
    phone VARCHAR(20) DEFAULT NULL COMMENT '联系电话',
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '登录账号',
    password VARCHAR(255) NOT NULL COMMENT '登录密码',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商表';

-- ============================================
-- 7. 原料表
-- ============================================
CREATE TABLE IF NOT EXISTS ingredient (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '原料ID',
    name VARCHAR(200) NOT NULL COMMENT '原料名称',
    unit VARCHAR(20) NOT NULL DEFAULT '斤' COMMENT '单位',
    category_id INT DEFAULT NULL COMMENT '所属分类ID',
    supplier_id INT NOT NULL COMMENT '供应商ID',
    price DECIMAL(10,2) DEFAULT NULL COMMENT '原料价格',
    stock INT NOT NULL DEFAULT 0 COMMENT '库存数量',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (supplier_id) REFERENCES supplier(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE SET NULL,
    INDEX idx_supplier_id (supplier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原料表';

-- ============================================
-- 8. 成品-原料关联表
-- ============================================
CREATE TABLE IF NOT EXISTS product_ingredient (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '关联ID',
    product_id INT NOT NULL COMMENT '成品ID',
    ingredient_id INT NOT NULL COMMENT '原料ID',
    quantity_needed DECIMAL(10,2) NOT NULL COMMENT '所需原料数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredient(id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_ingredient (product_id, ingredient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成品-原料关联表';

-- ============================================
-- 13. 供应商备货单表
-- ============================================
CREATE TABLE IF NOT EXISTS supplier_order (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '备货单ID',
    order_sn VARCHAR(32) NOT NULL COMMENT '关联订单号',
    supplier_id INT NOT NULL COMMENT '供应商ID',
    status SMALLINT NOT NULL DEFAULT 10 COMMENT '状态：10-待备货，20-备货中，30-已完成，40-已取消',
    notes TEXT DEFAULT NULL COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (order_sn) REFERENCES order_master(order_sn) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES supplier(id) ON DELETE CASCADE,
    INDEX idx_order_sn (order_sn),
    INDEX idx_supplier_id (supplier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商备货单表';

-- ============================================
-- 14. 供应商备货单项表
-- ============================================
CREATE TABLE IF NOT EXISTS supplier_order_item (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '备货单项ID',
    supplier_order_id INT NOT NULL COMMENT '备货单ID',
    ingredient_id INT NOT NULL COMMENT '原料ID',
    ingredient_name VARCHAR(200) NOT NULL COMMENT '原料名称',
    quantity DECIMAL(10,2) NOT NULL COMMENT '需要数量',
    unit VARCHAR(20) NOT NULL DEFAULT '斤' COMMENT '单位',
    FOREIGN KEY (supplier_order_id) REFERENCES supplier_order(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredient(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商备货单项表';

-- ============================================
-- 插入测试数据 (使用 INSERT IGNORE 防止重复插入已存在的记录)
-- ============================================

-- 供应商测试数据
INSERT IGNORE INTO supplier (name, contact_person, phone, username, password) VALUES
('绿鲜蔬菜供应商', '王经理', '13900139000', 'veggie_supplier', '123456'),
('禽肉蛋品供应商', '李经理', '13800138111', 'meat_supplier', '123456');

-- 原料数据 (需要确保 category_id 和 supplier_id 对应的记录存在)
-- 这里假设 category id=1 (新鲜蔬菜) 和 id=3 (肉禽蛋奶) 以及 supplier id=1, id=2 已经存在
INSERT IGNORE INTO ingredient (name, unit, category_id, supplier_id, price, stock) VALUES
('西红柿', '斤', 1, 1, 4.99, 200),
('鸡蛋', '个', 3, 2, 1.20, 1000);

-- 成品-原料关联数据（西红柿炒鸡蛋套餐需要西红柿和鸡蛋）
-- 这里假设 product id=1 (西红柿炒鸡蛋套餐) 已经存在
INSERT IGNORE INTO product_ingredient (product_id, ingredient_id, quantity_needed) VALUES
(1, 1, 0.8),  -- 1份套餐需要0.8斤西红柿
(1, 2, 4);    -- 1份套餐需要4个鸡蛋