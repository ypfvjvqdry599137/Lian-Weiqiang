CREATE TABLE order_master (
    order_sn VARCHAR(32) PRIMARY KEY COMMENT '订单号（唯一业务流水号）',
    station_id INT NOT NULL COMMENT '归属小区自提点ID',
    shipping_type TINYINT DEFAULT 1 COMMENT '配送模式：1-社区自提，2-同城快送（预留）',
    order_status TINYINT NOT NULL DEFAULT 10 COMMENT '订单状态机（见6.1）',
    refund_status TINYINT NOT NULL DEFAULT 0 COMMENT '售后状态机（见6.2）'
);
