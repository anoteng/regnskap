-- Migration to add CSV mappings functionality
-- Run this to update existing database

-- Create csv_mappings table
CREATE TABLE IF NOT EXISTS csv_mappings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    date_column VARCHAR(100) NOT NULL,
    description_column VARCHAR(100) NOT NULL,
    amount_column VARCHAR(100) NOT NULL,
    reference_column VARCHAR(100),
    date_format VARCHAR(50) DEFAULT 'YYYY-MM-DD',
    decimal_separator VARCHAR(1) DEFAULT '.',
    delimiter VARCHAR(1) DEFAULT ',',
    skip_rows INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_mapping_name (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add csv_mapping_id to import_logs
ALTER TABLE import_logs
ADD COLUMN csv_mapping_id INT AFTER bank_account_id,
ADD FOREIGN KEY (csv_mapping_id) REFERENCES csv_mappings(id) ON DELETE SET NULL;
