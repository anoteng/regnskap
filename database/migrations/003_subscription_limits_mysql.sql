-- Migration: Add subscription limits and usage tracking
-- Run this script to add max limits to subscription plans and track usage

-- Add limit columns to subscription_plans
ALTER TABLE subscription_plans
ADD COLUMN max_documents INT NULL COMMENT 'Max total documents/receipts (NULL = unlimited)',
ADD COLUMN max_monthly_uploads INT NULL COMMENT 'Max uploads per month (NULL = unlimited)';

-- Set limits for FREE tier
UPDATE subscription_plans
SET max_documents = 50, max_monthly_uploads = 20
WHERE tier = 'FREE';

-- BASIC and AI tiers have unlimited (NULL values)
UPDATE subscription_plans
SET max_documents = NULL, max_monthly_uploads = NULL
WHERE tier IN ('BASIC', 'AI');

-- Create monthly usage tracking table
CREATE TABLE IF NOT EXISTS user_monthly_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    upload_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_month (user_id, year, month)
);

CREATE INDEX idx_user_monthly_usage_user_id ON user_monthly_usage(user_id);
CREATE INDEX idx_user_monthly_usage_period ON user_monthly_usage(year, month);
