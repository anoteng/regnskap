-- Migration 007: Chart of Accounts Templates
-- Refactor from global system accounts to flexible per-ledger templates

-- ============================================================================
-- STEP 1: Create new template tables
-- ============================================================================

-- Chart of accounts templates (e.g., Family, Personal, Sole Proprietorship)
CREATE TABLE IF NOT EXISTS chart_of_accounts_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active),
    INDEX idx_default (is_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Template accounts (blueprint for accounts in each template)
CREATE TABLE IF NOT EXISTS template_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id INT NOT NULL,
    account_number VARCHAR(10) NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    account_type ENUM('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE') NOT NULL,
    parent_account_number VARCHAR(10),
    description TEXT,
    is_default BOOLEAN DEFAULT TRUE COMMENT 'If true, included by default when creating ledger',
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES chart_of_accounts_templates(id) ON DELETE CASCADE,
    UNIQUE KEY unique_account_per_template (template_id, account_number),
    INDEX idx_template_type (template_id, account_type),
    INDEX idx_parent (template_id, parent_account_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 2: Add chart_template_id to ledgers
-- ============================================================================

ALTER TABLE ledgers
ADD COLUMN chart_template_id INT NULL AFTER created_by,
ADD CONSTRAINT fk_ledger_template
    FOREIGN KEY (chart_template_id)
    REFERENCES chart_of_accounts_templates(id)
    ON DELETE SET NULL;

ALTER TABLE ledgers
ADD INDEX idx_template (chart_template_id);

-- ============================================================================
-- STEP 3: Make accounts ledger-specific
-- ============================================================================

-- Add ledger_id to accounts (making them per-ledger instead of global)
ALTER TABLE accounts
ADD COLUMN ledger_id INT NULL AFTER id,
ADD CONSTRAINT fk_account_ledger
    FOREIGN KEY (ledger_id)
    REFERENCES ledgers(id)
    ON DELETE CASCADE;

ALTER TABLE accounts
ADD INDEX idx_ledger (ledger_id);

-- Remove the global unique constraint on account_number
ALTER TABLE accounts
DROP INDEX account_number;

-- Add new unique constraint: account_number is unique per ledger
ALTER TABLE accounts
ADD UNIQUE KEY unique_account_per_ledger (ledger_id, account_number);

-- ============================================================================
-- STEP 4: Remove is_system field
-- ============================================================================

ALTER TABLE accounts
DROP COLUMN is_system;

-- ============================================================================
-- STEP 5: Seed default template from existing accounts
-- ============================================================================

-- Insert default template (Familieregnskap)
INSERT INTO chart_of_accounts_templates (name, display_name, description, is_active, is_default)
VALUES (
    'family_accounting',
    'Familieregnskap',
    'Enkel kontoplan for husholdningsøkonomi med fokus på inntekter, utgifter, formue og gjeld.',
    TRUE,
    TRUE
);

-- Get the template ID (we'll use it below)
SET @family_template_id = LAST_INSERT_ID();

-- Copy existing accounts to template_accounts
-- This preserves the current account structure as the default template
INSERT INTO template_accounts (
    template_id,
    account_number,
    account_name,
    account_type,
    parent_account_number,
    description,
    is_default,
    sort_order
)
SELECT
    @family_template_id,
    account_number,
    account_name,
    account_type,
    (SELECT a2.account_number FROM accounts a2 WHERE a2.id = accounts.parent_account_id),
    description,
    TRUE,
    CAST(account_number AS UNSIGNED)
FROM accounts
WHERE ledger_id IS NULL  -- Only migrate accounts that haven't been assigned to a ledger yet
ORDER BY account_number;

-- ============================================================================
-- STEP 6: Migrate existing ledgers to use template
-- ============================================================================

-- Set all existing ledgers to use the family template
UPDATE ledgers
SET chart_template_id = @family_template_id
WHERE chart_template_id IS NULL;

-- For each existing ledger, create copies of the template accounts
-- First, let's create a temporary procedure to do this migration

DELIMITER //

CREATE PROCEDURE migrate_ledger_accounts()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_ledger_id INT;
    DECLARE v_template_id INT;

    -- Cursor for all ledgers
    DECLARE ledger_cursor CURSOR FOR
        SELECT id, chart_template_id FROM ledgers WHERE chart_template_id IS NOT NULL;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN ledger_cursor;

    read_loop: LOOP
        FETCH ledger_cursor INTO v_ledger_id, v_template_id;
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- Insert accounts for this ledger from template
        -- First pass: accounts without parents
        INSERT INTO accounts (
            ledger_id,
            account_number,
            account_name,
            account_type,
            parent_account_id,
            description,
            is_active,
            created_at
        )
        SELECT
            v_ledger_id,
            ta.account_number,
            ta.account_name,
            ta.account_type,
            NULL,  -- Will be set in second pass
            ta.description,
            TRUE,
            NOW()
        FROM template_accounts ta
        WHERE ta.template_id = v_template_id
          AND ta.is_default = TRUE
          -- Only if not already exists (for idempotency)
          AND NOT EXISTS (
              SELECT 1 FROM accounts a2
              WHERE a2.ledger_id = v_ledger_id
                AND a2.account_number = ta.account_number
          )
        ORDER BY ta.sort_order;

        -- Second pass: update parent relationships
        UPDATE accounts a
        INNER JOIN template_accounts ta ON (
            a.ledger_id = v_ledger_id
            AND a.account_number = ta.account_number
            AND ta.template_id = v_template_id
        )
        LEFT JOIN accounts parent_acc ON (
            parent_acc.ledger_id = v_ledger_id
            AND parent_acc.account_number = ta.parent_account_number
        )
        SET a.parent_account_id = parent_acc.id
        WHERE a.ledger_id = v_ledger_id
          AND ta.parent_account_number IS NOT NULL;

    END LOOP;

    CLOSE ledger_cursor;
END//

DELIMITER ;

-- Run the migration procedure
CALL migrate_ledger_accounts();

-- Clean up the procedure
DROP PROCEDURE migrate_ledger_accounts;

-- ============================================================================
-- STEP 7: Clean up orphaned global accounts
-- ============================================================================

-- Any accounts without a ledger_id at this point are orphaned
-- (they were the old global system accounts, now copied to template and per-ledger)
-- We'll delete them to clean up

DELETE FROM accounts WHERE ledger_id IS NULL;

-- ============================================================================
-- STEP 8: Make ledger_id required (now that all accounts have one)
-- ============================================================================

ALTER TABLE accounts
MODIFY COLUMN ledger_id INT NOT NULL;

-- ============================================================================
-- STEP 9: Drop LedgerAccountSettings table (no longer needed)
-- ============================================================================

-- With per-ledger accounts, we don't need a separate settings table
-- Accounts can just be marked inactive instead of hidden
DROP TABLE IF EXISTS ledger_account_settings;

-- ============================================================================
-- Verification queries (commented out)
-- ============================================================================

-- SELECT * FROM chart_of_accounts_templates;
-- SELECT * FROM template_accounts ORDER BY template_id, account_number;
-- SELECT COUNT(*) as template_count FROM chart_of_accounts_templates;
-- SELECT COUNT(*) as template_account_count FROM template_accounts;
-- SELECT COUNT(*) as ledger_with_template FROM ledgers WHERE chart_template_id IS NOT NULL;
-- SELECT l.id, l.name, t.display_name as template, COUNT(a.id) as account_count
-- FROM ledgers l
-- LEFT JOIN chart_of_accounts_templates t ON l.chart_template_id = t.id
-- LEFT JOIN accounts a ON a.ledger_id = l.id
-- GROUP BY l.id, l.name, t.display_name;
