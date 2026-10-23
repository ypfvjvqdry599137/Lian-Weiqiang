-- Idempotent migration for existing delivery_station tables.
SET @add_station_username = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_station' AND COLUMN_NAME = 'username') = 0,
    'ALTER TABLE delivery_station ADD COLUMN username VARCHAR(50) NULL',
    'SELECT 1'
);
PREPARE stmt FROM @add_station_username;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_station_password_hash = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_station' AND COLUMN_NAME = 'password_hash') = 0,
    'ALTER TABLE delivery_station ADD COLUMN password_hash VARCHAR(255) NULL',
    'SELECT 1'
);
PREPARE stmt FROM @add_station_password_hash;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_station_username_unique = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'delivery_station'
       AND COLUMN_NAME = 'username' AND NON_UNIQUE = 0) = 0,
    'ALTER TABLE delivery_station ADD UNIQUE INDEX uq_delivery_station_username (username)',
    'SELECT 1'
);
PREPARE stmt FROM @add_station_username_unique;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
