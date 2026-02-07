-- Migration continuation - add ledger_id to all data tables
-- This continues from where the previous migration left off

-- Step 1: Verify ledgers exist and populate if needed
-- Create default ledgers for users that don't have one
INSERT INTO ledgers (name, created_by)
SELECT CONCAT(full_name, 's regnskap'), u.id
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM ledgers l WHERE l.created_by = u.id
);

-- Add users as owners of their default ledgers if not already members
INSERT IGNORE INTO ledger_members (ledger_id, user_id, role)
SELECT l.id, u.id, 'OWNER'
FROM users u
JOIN ledgers l ON l.created_by = u.id;

-- Set last_active_ledger_id for users who don't have it set
UPDATE users u
JOIN ledgers l ON l.created_by = u.id
SET u.last_active_ledger_id = l.id
WHERE u.last_active_ledger_id IS NULL;

-- Step 2: Add ledger_id to bank_accounts
ALTER TABLE bank_accounts
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

UPDATE bank_accounts ba
JOIN users u ON ba.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET ba.ledger_id = l.id;

ALTER TABLE bank_accounts
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 3: Add ledger_id to transactions
ALTER TABLE transactions
ADD COLUMN ledger_id INT NULL AFTER id,
ADD COLUMN created_by INT NULL AFTER user_id,
ADD INDEX idx_ledger (ledger_id);

UPDATE transactions t
JOIN users u ON t.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET t.ledger_id = l.id, t.created_by = u.id;

ALTER TABLE transactions
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
ADD FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

-- Step 4: Add ledger_id to budgets
ALTER TABLE budgets
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

UPDATE budgets b
JOIN users u ON b.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET b.ledger_id = l.id;

ALTER TABLE budgets
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 5: Add ledger_id to categories
ALTER TABLE categories
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

UPDATE categories c
JOIN users u ON c.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET c.ledger_id = l.id;

ALTER TABLE categories
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 6: Add ledger_id to csv_mappings
ALTER TABLE csv_mappings
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

UPDATE csv_mappings cm
JOIN users u ON cm.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET cm.ledger_id = l.id;

ALTER TABLE csv_mappings
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 7: Add ledger_id to import_logs
ALTER TABLE import_logs
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

UPDATE import_logs il
JOIN users u ON il.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET il.ledger_id = l.id;

ALTER TABLE import_logs
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 8: Make old user_id columns nullable (keep for backward compatibility)
ALTER TABLE bank_accounts MODIFY user_id INT NULL;
ALTER TABLE transactions MODIFY user_id INT NULL;
ALTER TABLE budgets MODIFY user_id INT NULL;
ALTER TABLE categories MODIFY user_id INT NULL;
ALTER TABLE csv_mappings MODIFY user_id INT NULL;
