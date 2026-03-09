-- Migration 010: Update subscription plans
-- Rename AI → PREMIUM, update pricing and features, remove AI columns

-- 1. Rename AI tier to PREMIUM
UPDATE subscription_plans SET tier = 'PREMIUM' WHERE tier = 'AI';
UPDATE subscription_plans
SET name = 'Premium',
    description = 'Full funksjonalitet med bankintegrasjon og vedlegg',
    price_monthly = 49.00,
    features = '["Alt i Basic", "Automatisk banksynkronisering", "Vedleggshåndtering", "Duplikatdeteksjon ved import"]',
    max_documents = NULL,
    max_monthly_uploads = NULL
WHERE tier = 'PREMIUM';

-- 2. Update Basic plan: 10 kr/mnd, receipts included
UPDATE subscription_plans
SET description = 'Vedleggshåndtering og CSV-import for 10 kr/mnd',
    price_monthly = 10.00,
    features = '["Alt i Gratis", "Vedleggshåndtering", "CSV-import", "Ubegrenset opplasting"]',
    max_documents = NULL,
    max_monthly_uploads = NULL
WHERE tier = 'BASIC';

-- 3. Update Free plan: no receipt limits (no receipt feature at all), no restrictions
UPDATE subscription_plans
SET description = 'Grunnleggende regnskapsfunksjonalitet uten vedlegg',
    features = '["Ubegrenset regnskap", "Ubegrenset transaksjoner", "Manuell postering", "Grunnleggende rapporter"]',
    max_documents = NULL,
    max_monthly_uploads = NULL
WHERE tier = 'FREE';

-- 4. Drop AI-specific columns
ALTER TABLE subscription_plans DROP COLUMN IF EXISTS ai_enabled;
ALTER TABLE subscription_plans DROP COLUMN IF EXISTS max_ai_operations_per_month;

-- 5. Add price_yearly column for annual pricing
ALTER TABLE subscription_plans ADD COLUMN price_yearly DECIMAL(10,2) DEFAULT NULL AFTER price_monthly;

UPDATE subscription_plans SET price_yearly = 100.00 WHERE tier = 'BASIC';
UPDATE subscription_plans SET price_yearly = 490.00 WHERE tier = 'PREMIUM';
