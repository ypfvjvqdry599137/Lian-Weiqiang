-- Idempotent columns for scheduled product promotions. Times are stored in UTC.
SET @add_flash_price = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'product' AND COLUMN_NAME = 'flash_price') = 0,
    'ALTER TABLE product ADD COLUMN flash_price DECIMAL(10,2) NULL', 'SELECT 1');
PREPARE stmt FROM @add_flash_price; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @add_flash_start = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'product' AND COLUMN_NAME = 'flash_start_at') = 0,
    'ALTER TABLE product ADD COLUMN flash_start_at DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @add_flash_start; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @add_flash_end = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = 'product' AND COLUMN_NAME = 'flash_end_at') = 0,
    'ALTER TABLE product ADD COLUMN flash_end_at DATETIME NULL', 'SELECT 1');
PREPARE stmt FROM @add_flash_end; EXECUTE stmt; DEALLOCATE PREPARE stmt;
