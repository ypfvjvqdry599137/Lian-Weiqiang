CREATE TABLE IF NOT EXISTS manual_refund (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_sn VARCHAR(32) NOT NULL,
    out_refund_no VARCHAR(64) DEFAULT NULL,
    refund_id VARCHAR(32) DEFAULT NULL,
    transaction_id VARCHAR(100) NOT NULL,
    order_total_fen INT NOT NULL,
    refund_fen INT NOT NULL,
    status VARCHAR(16) NOT NULL,
    refund_channel VARCHAR(24) DEFAULT NULL,
    operator_note VARCHAR(255) DEFAULT NULL,
    success_time VARCHAR(64) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checked_at DATETIME DEFAULT NULL,
    UNIQUE KEY uq_manual_refund_out_refund_no (out_refund_no),
    UNIQUE KEY uq_manual_refund_refund_id (refund_id),
    KEY ix_manual_refund_order_sn (order_sn),
    CONSTRAINT fk_manual_refund_order FOREIGN KEY (order_sn) REFERENCES order_master(order_sn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET @refund_channel_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'manual_refund' AND COLUMN_NAME = 'refund_channel'
);
SET @refund_channel_sql = IF(@refund_channel_exists = 0,
    'ALTER TABLE manual_refund ADD COLUMN refund_channel VARCHAR(24) DEFAULT NULL', 'SELECT 1');
PREPARE refund_channel_migration FROM @refund_channel_sql;
EXECUTE refund_channel_migration;
DEALLOCATE PREPARE refund_channel_migration;
