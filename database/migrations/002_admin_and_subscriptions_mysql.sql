-- Migration: Add admin and subscription features (MySQL version)
-- Run this script to add user administration and subscription support

-- Add is_admin column to users table
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;

-- Create subscription_plans table
CREATE TABLE IF NOT EXISTS subscription_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    tier VARCHAR(10) NOT NULL UNIQUE,
    description TEXT,
    price_monthly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    features TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Create user_subscriptions table
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plan_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    cancelled_at DATETIME,
    discount_percentage DECIMAL(5, 2) DEFAULT 0,
    custom_price DECIMAL(10, 2),
    is_free_forever BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id) ON DELETE RESTRICT
);

-- Create indexes
CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX idx_users_is_admin ON users(is_admin);

-- Insert default subscription plans
INSERT INTO subscription_plans (name, tier, description, price_monthly, features, is_active)
VALUES
    ('Gratis', 'FREE', 'Grunnleggende regnskapsfunksjonalitet', 0, '["Ubegrenset regnskap", "Manuell postering", "Grunnleggende rapporter"]', TRUE),
    ('Basic', 'BASIC', 'Full regnskapsfunksjonalitet uten AI', 49, '["Alt i Gratis", "CSV-import", "Vedleggshåndtering", "Avanserte rapporter", "Multi-bruker"]', TRUE),
    ('AI', 'AI', 'Full funksjonalitet med AI-assistanse', 99, '["Alt i Basic", "AI-forslag til postering", "Automatisk kvitteringstolking", "Smart kategorisering", "Prediktiv analyse"]', TRUE);

-- Make andreas@noteng.no an admin
UPDATE users SET is_admin = TRUE WHERE email = 'andreas@noteng.no';
