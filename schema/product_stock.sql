CREATE TABLE product_stock (
    product_id INT PRIMARY KEY COMMENT '商品ID',
    total_stock INT NOT NULL DEFAULT 0 COMMENT '全城大仓总库存（所有用户下单扣减此字段）',
    lock_stock INT NOT NULL DEFAULT 0 COMMENT '锁定库存（用户下单未付款时的冻结库存）'
);
