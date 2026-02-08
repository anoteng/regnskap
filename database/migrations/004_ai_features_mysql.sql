-- Migration: Add AI features and usage tracking
-- Run this script to add AI configuration and usage tracking

-- AI Configuration table (system-wide settings)
CREATE TABLE IF NOT EXISTS ai_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider VARCHAR(50) NOT NULL COMMENT 'openai, anthropic, etc.',
    api_key TEXT NOT NULL,
    model VARCHAR(100) NOT NULL COMMENT 'gpt-4o, claude-3-5-sonnet, etc.',
    is_active BOOLEAN DEFAULT TRUE,
    max_tokens INT DEFAULT 4000,
    temperature DECIMAL(3, 2) DEFAULT 0.3,
    config_notes TEXT COMMENT 'Admin notes about this configuration',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- AI Usage tracking per user
CREATE TABLE IF NOT EXISTS ai_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ledger_id INT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    operation_type VARCHAR(50) NOT NULL COMMENT 'receipt_analysis, posting_suggestion, etc.',
    tokens_used INT NOT NULL,
    cost_usd DECIMAL(10, 6) NULL COMMENT 'Estimated cost in USD',
    request_data TEXT COMMENT 'JSON data about the request',
    response_data TEXT COMMENT 'JSON data about the response',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE SET NULL
);

CREATE INDEX idx_ai_usage_user_id ON ai_usage(user_id);
CREATE INDEX idx_ai_usage_created_at ON ai_usage(created_at);
CREATE INDEX idx_ai_usage_operation ON ai_usage(operation_type);

-- Add AI-extracted fields to receipts table
ALTER TABLE receipts
ADD COLUMN ai_extracted_date DATE NULL COMMENT 'Date extracted by AI',
ADD COLUMN ai_extracted_amount DECIMAL(10, 2) NULL COMMENT 'Amount extracted by AI',
ADD COLUMN ai_extracted_vendor VARCHAR(255) NULL COMMENT 'Vendor/merchant name',
ADD COLUMN ai_extracted_description TEXT NULL COMMENT 'Description extracted by AI',
ADD COLUMN ai_suggested_account VARCHAR(10) NULL COMMENT 'Suggested account number',
ADD COLUMN ai_confidence DECIMAL(3, 2) NULL COMMENT 'AI confidence score 0-1',
ADD COLUMN ai_processed_at DATETIME NULL COMMENT 'When AI processing was done',
ADD COLUMN ai_processing_error TEXT NULL COMMENT 'Error if AI processing failed';

-- Add AI suggestion fields to transactions (for posting suggestions)
ALTER TABLE transactions
ADD COLUMN ai_suggested BOOLEAN DEFAULT FALSE COMMENT 'Whether this was AI-suggested',
ADD COLUMN ai_suggestion_data TEXT NULL COMMENT 'JSON with AI suggestion details';
