-- Migration to multi-ledger (multi-regnskap) architecture
-- This allows users to have multiple regnskap and share them with others

-- Step 1: Create ledgers table
CREATE TABLE IF NOT EXISTS ledgers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Step 2: Create ledger_members table (many-to-many between users and ledgers)
CREATE TABLE IF NOT EXISTS ledger_members (
    ledger_id INT NOT NULL,
    user_id INT NOT NULL,
    role ENUM('OWNER', 'MEMBER', 'VIEWER') NOT NULL DEFAULT 'MEMBER',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ledger_id, user_id),
    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Step 3: Add last_active_ledger_id to users table
ALTER TABLE users
ADD COLUMN last_active_ledger_id INT NULL,
ADD FOREIGN KEY (last_active_ledger_id) REFERENCES ledgers(id) ON DELETE SET NULL;

-- Step 4: Migrate existing data
-- Create a default ledger for each user and migrate their data

-- Create default ledgers for all existing users
INSERT INTO ledgers (name, created_by)
SELECT CONCAT(full_name, 's regnskap'), id
FROM users;

-- Add users as owners of their default ledgers
INSERT INTO ledger_members (ledger_id, user_id, role)
SELECT l.id, u.id, 'OWNER'
FROM users u
JOIN ledgers l ON l.created_by = u.id;

-- Set last_active_ledger_id for all users
UPDATE users u
JOIN ledgers l ON l.created_by = u.id
SET u.last_active_ledger_id = l.id;

-- Step 5: Add ledger_id to existing tables and migrate data

-- bank_accounts
-- First add as nullable
ALTER TABLE bank_accounts
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE bank_accounts ba
JOIN users u ON ba.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET ba.ledger_id = l.id;

-- Now make it NOT NULL and add foreign key
ALTER TABLE bank_accounts
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- transactions
-- First add as nullable
ALTER TABLE transactions
ADD COLUMN ledger_id INT NULL AFTER id,
ADD COLUMN created_by INT NULL AFTER user_id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE transactions t
JOIN users u ON t.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET t.ledger_id = l.id, t.created_by = u.id;

-- Now make it NOT NULL and add foreign keys
ALTER TABLE transactions
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
ADD FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;

-- budgets
-- First add as nullable
ALTER TABLE budgets
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE budgets b
JOIN users u ON b.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET b.ledger_id = l.id;

-- Now make it NOT NULL and add foreign key
ALTER TABLE budgets
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- categories
-- First add as nullable
ALTER TABLE categories
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE categories c
JOIN users u ON c.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET c.ledger_id = l.id;

-- Now make it NOT NULL and add foreign key
ALTER TABLE categories
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- csv_mappings
-- First add as nullable
ALTER TABLE csv_mappings
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE csv_mappings cm
JOIN users u ON cm.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET cm.ledger_id = l.id;

-- Now make it NOT NULL and add foreign key
ALTER TABLE csv_mappings
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- import_logs (keep user_id for audit trail, add ledger_id)
-- First add as nullable
ALTER TABLE import_logs
ADD COLUMN ledger_id INT NULL AFTER id,
ADD INDEX idx_ledger (ledger_id);

-- Populate the data
UPDATE import_logs il
JOIN users u ON il.user_id = u.id
JOIN ledgers l ON l.created_by = u.id
SET il.ledger_id = l.id;

-- Now make it NOT NULL and add foreign key
ALTER TABLE import_logs
MODIFY ledger_id INT NOT NULL,
ADD FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE;

-- Step 6: Drop old user_id foreign keys (keep columns for now for backward compatibility)
-- We'll remove these columns in a future migration once everything is tested

-- For now, just make them nullable
ALTER TABLE bank_accounts MODIFY user_id INT NULL;
ALTER TABLE transactions MODIFY user_id INT NULL;
ALTER TABLE budgets MODIFY user_id INT NULL;
ALTER TABLE categories MODIFY user_id INT NULL;
ALTER TABLE csv_mappings MODIFY user_id INT NULL;
