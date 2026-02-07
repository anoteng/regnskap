-- Create receipts table for attachment queue
CREATE TABLE IF NOT EXISTS receipts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ledger_id INT NOT NULL,
    uploaded_by INT NOT NULL,

    -- File storage
    image_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255),
    file_size INT,
    mime_type VARCHAR(100),

    -- Metadata
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    receipt_date DATE,  -- Optional, can be set manually
    amount DECIMAL(10,2),  -- Optional, can be set manually
    description TEXT,  -- Optional note from uploader

    -- Matching status
    status ENUM('PENDING', 'MATCHED', 'ARCHIVED') DEFAULT 'PENDING',
    matched_transaction_id INT NULL,
    matched_at DATETIME NULL,
    matched_by INT NULL,

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id),
    FOREIGN KEY (matched_transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,
    FOREIGN KEY (matched_by) REFERENCES users(id),

    -- Indexes
    INDEX idx_ledger_status (ledger_id, status),
    INDEX idx_upload_date (upload_date),
    INDEX idx_receipt_date (receipt_date),
    INDEX idx_matched_transaction (matched_transaction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
