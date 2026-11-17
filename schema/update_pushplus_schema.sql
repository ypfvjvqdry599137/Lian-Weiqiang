-- Idempotent PushPlus recipient mapping. The outbox table is created by db.create_all on backend restart.
SET @add_pushplus_topic = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'supplier' AND COLUMN_NAME = 'pushplus_topic') = 0,
    'ALTER TABLE supplier ADD COLUMN pushplus_topic VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt FROM @add_pushplus_topic; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @add_pushplus_index = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'supplier' AND INDEX_NAME = 'uq_supplier_pushplus_topic') = 0,
    'ALTER TABLE supplier ADD UNIQUE INDEX uq_supplier_pushplus_topic (pushplus_topic)', 'SELECT 1');
PREPARE stmt FROM @add_pushplus_index; EXECUTE stmt; DEALLOCATE PREPARE stmt;
