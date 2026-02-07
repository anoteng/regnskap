-- Migration: Add admin and subscription features
-- Run this script to add user administration and subscription support

-- Add is_admin column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- Create subscription_plans table
CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    tier VARCHAR(10) NOT NULL UNIQUE,
    description TEXT,
    price_monthly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    features TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_subscriptions table
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES subscription_plans(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    discount_percentage DECIMAL(5, 2) DEFAULT 0,
    custom_price DECIMAL(10, 2),
    is_free_forever BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);

-- Insert default subscription plans
INSERT INTO subscription_plans (name, tier, description, price_monthly, features, is_active)
VALUES
    ('Gratis', 'FREE', 'Grunnleggende regnskapsfunksjonalitet', 0, '["Ubegrenset regnskap", "Manuell postering", "Grunnleggende rapporter"]', TRUE),
    ('Basic', 'BASIC', 'Full regnskapsfunksjonalitet uten AI', 49, '["Alt i Gratis", "CSV-import", "Vedleggshåndtering", "Avanserte rapporter", "Multi-bruker"]', TRUE),
    ('AI', 'AI', 'Full funksjonalitet med AI-assistanse', 99, '["Alt i Basic", "AI-forslag til postering", "Automatisk kvitteringstolking", "Smart kategorisering", "Prediktiv analyse"]', TRUE)
ON CONFLICT (tier) DO NOTHING;

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_subscription_plans_updated_at
    BEFORE UPDATE ON subscription_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Optional: Make your user an admin (replace with your email)
-- UPDATE users SET is_admin = TRUE WHERE email = 'your-email@example.com';
