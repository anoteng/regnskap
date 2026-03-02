-- Migration 007: Chart of Accounts Templates (Fixed)
-- Refactor from global system accounts to flexible per-ledger templates

-- ============================================================================
-- STEP 1: Create new template tables (idempotent)
-- ============================================================================

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
-- STEP 2: Add chart_template_id to ledgers (idempotent)
-- ============================================================================

-- Check if column exists, if not add it
SET @dbname = DATABASE();
SET @tablename = "ledgers";
SET @columnname = "chart_template_id";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      TABLE_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND COLUMN_NAME = @columnname
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " INT NULL AFTER created_by")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add foreign key constraint if it doesn't exist
SET @fk_name = 'fk_ledger_template';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND CONSTRAINT_NAME = @fk_name
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD CONSTRAINT ", @fk_name,
         " FOREIGN KEY (chart_template_id) REFERENCES chart_of_accounts_templates(id) ON DELETE SET NULL")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add index if it doesn't exist
SET @index_name = 'idx_template';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND INDEX_NAME = @index_name
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD INDEX ", @index_name, " (chart_template_id)")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- ============================================================================
-- STEP 3: Make accounts ledger-specific (idempotent)
-- ============================================================================

-- Add ledger_id to accounts if not exists
SET @tablename = "accounts";
SET @columnname = "ledger_id";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND COLUMN_NAME = @columnname
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " INT NULL AFTER id")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add foreign key constraint if it doesn't exist
SET @fk_name = 'fk_account_ledger';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND CONSTRAINT_NAME = @fk_name
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD CONSTRAINT ", @fk_name,
         " FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add index on ledger_id if it doesn't exist
SET @index_name = 'idx_ledger';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = @tablename
      AND INDEX_NAME = @index_name
  ) > 0,
  "SELECT 1",
  CONCAT("ALTER TABLE ", @tablename, " ADD INDEX ", @index_name, " (ledger_id)")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Drop the global unique constraint on account_number (check actual name first)
SET @constraint_name = (
  SELECT CONSTRAINT_NAME
  FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
  WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = 'accounts'
    AND COLUMN_NAME = 'account_number'
    AND CONSTRAINT_NAME != 'PRIMARY'
  LIMIT 1
);

SET @preparedStatement = (SELECT IF(
  @constraint_name IS NOT NULL,
  CONCAT("ALTER TABLE accounts DROP INDEX ", @constraint_name),
  "SELECT 1"
));
PREPARE dropIfExists FROM @preparedStatement;
EXECUTE dropIfExists;
DEALLOCATE PREPARE dropIfExists;

-- Add new unique constraint: account_number is unique per ledger (idempotent)
SET @index_name = 'unique_account_per_ledger';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = 'accounts'
      AND INDEX_NAME = @index_name
  ) > 0,
  "SELECT 1",
  "ALTER TABLE accounts ADD UNIQUE KEY unique_account_per_ledger (ledger_id, account_number)"
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- ============================================================================
-- STEP 4: Remove is_system field (idempotent)
-- ============================================================================

SET @columnname = "is_system";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = 'accounts'
      AND COLUMN_NAME = @columnname
  ) > 0,
  CONCAT("ALTER TABLE accounts DROP COLUMN ", @columnname),
  "SELECT 1"
));
PREPARE dropIfExists FROM @preparedStatement;
EXECUTE dropIfExists;
DEALLOCATE PREPARE dropIfExists;

-- ============================================================================
-- STEP 5: Seed default template from existing accounts
-- ============================================================================

-- Insert default template if not exists
INSERT IGNORE INTO chart_of_accounts_templates (name, display_name, description, is_active, is_default)
VALUES (
    'family_accounting',
    'Familieregnskap',
    'Enkel kontoplan for husholdningsøkonomi med fokus på inntekter, utgifter, formue og gjeld.',
    TRUE,
    TRUE
);

-- Get the template ID
SET @family_template_id = (SELECT id FROM chart_of_accounts_templates WHERE name = 'family_accounting' LIMIT 1);

-- Copy existing accounts to template_accounts (only if template_accounts is empty for this template)
INSERT IGNORE INTO template_accounts (
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
WHERE ledger_id IS NULL
ORDER BY account_number;

-- ============================================================================
-- STEP 6: Migrate existing ledgers to use template
-- ============================================================================

-- Set all existing ledgers to use the family template (if not already set)
UPDATE ledgers
SET chart_template_id = @family_template_id
WHERE chart_template_id IS NULL;

-- For each existing ledger, create copies of the template accounts
DELIMITER //

DROP PROCEDURE IF EXISTS migrate_ledger_accounts//

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
        INSERT IGNORE INTO accounts (
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
            NULL,
            ta.description,
            TRUE,
            NOW()
        FROM template_accounts ta
        WHERE ta.template_id = v_template_id
          AND ta.is_default = TRUE
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
          AND ta.parent_account_number IS NOT NULL
          AND a.parent_account_id IS NULL;

    END LOOP;

    CLOSE ledger_cursor;
END//

DELIMITER ;

-- Run the migration procedure
CALL migrate_ledger_accounts();

-- Clean up the procedure
DROP PROCEDURE IF EXISTS migrate_ledger_accounts;

-- ============================================================================
-- STEP 7: Clean up orphaned global accounts
-- ============================================================================

-- Any accounts without a ledger_id at this point are orphaned
DELETE FROM accounts WHERE ledger_id IS NULL;

-- ============================================================================
-- STEP 8: Make ledger_id required (now that all accounts have one)
-- ============================================================================

-- Only modify if column is still nullable
SET @preparedStatement = (SELECT IF(
  (
    SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
      AND TABLE_NAME = 'accounts'
      AND COLUMN_NAME = 'ledger_id'
  ) = 'YES',
  "ALTER TABLE accounts MODIFY COLUMN ledger_id INT NOT NULL",
  "SELECT 1"
));
PREPARE alterIfNeeded FROM @preparedStatement;
EXECUTE alterIfNeeded;
DEALLOCATE PREPARE alterIfNeeded;

-- ============================================================================
-- STEP 9: Drop LedgerAccountSettings table (if exists)
-- ============================================================================

DROP TABLE IF EXISTS ledger_account_settings;

-- ============================================================================
-- Verification queries
-- ============================================================================

SELECT 'Migration completed successfully!' as status;
SELECT COUNT(*) as template_count FROM chart_of_accounts_templates;
SELECT COUNT(*) as template_account_count FROM template_accounts;
SELECT COUNT(*) as ledger_with_template FROM ledgers WHERE chart_template_id IS NOT NULL;
SELECT
    l.id,
    l.name,
    t.display_name as template,
    COUNT(a.id) as account_count
FROM ledgers l
LEFT JOIN chart_of_accounts_templates t ON l.chart_template_id = t.id
LEFT JOIN accounts a ON a.ledger_id = l.id
GROUP BY l.id, l.name, t.display_name;
