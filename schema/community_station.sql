CREATE TABLE community_station (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '自提点唯一ID',
    station_name VARCHAR(100) NOT NULL COMMENT '小区/自提点名称',
    address VARCHAR(255) NOT NULL COMMENT '详细自提地址',
    merchant_username VARCHAR(50) UNIQUE NOT NULL COMMENT '合作商后台登录账号',
    merchant_password VARCHAR(255) NOT NULL COMMENT '合作商后台登录密码（加密存储）',
    commission_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '默认该小区佣金抽成比例（如10.00 代表 10%）'
);
