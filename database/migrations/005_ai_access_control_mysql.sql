-- Migration: Add AI access control to subscriptions and users
-- Run this script to add AI access control

-- Add AI access fields to subscription plans
ALTER TABLE subscription_plans
ADD COLUMN ai_enabled BOOLEAN DEFAULT FALSE COMMENT 'Whether AI features are included',
ADD COLUMN max_ai_operations_per_month INT NULL COMMENT 'Max AI operations per month (NULL = unlimited)';

-- Update existing plans with AI access
UPDATE subscription_plans SET ai_enabled = FALSE, max_ai_operations_per_month = NULL WHERE tier = 'FREE';
UPDATE subscription_plans SET ai_enabled = FALSE, max_ai_operations_per_month = NULL WHERE tier = 'BASIC';
UPDATE subscription_plans SET ai_enabled = TRUE, max_ai_operations_per_month = NULL WHERE tier = 'AI';

-- Add user-level AI access control
ALTER TABLE users
ADD COLUMN ai_access_enabled BOOLEAN DEFAULT TRUE COMMENT 'Admin can disable AI access for specific users',
ADD COLUMN ai_access_blocked_reason TEXT NULL COMMENT 'Reason why AI access was blocked';

-- Add monthly AI usage counter to user_monthly_usage
ALTER TABLE user_monthly_usage
ADD COLUMN ai_operations_count INT DEFAULT 0 COMMENT 'AI operations this month';
