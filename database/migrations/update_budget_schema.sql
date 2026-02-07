-- Drop old budget tables if they exist
DROP TABLE IF EXISTS budget_items;
DROP TABLE IF EXISTS budgets;

-- Create new budgets table for yearly budgets
CREATE TABLE IF NOT EXISTS budgets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ledger_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    year INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NOT NULL,

    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_ledger_year (ledger_id, year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create budget_lines table for monthly amounts per account
CREATE TABLE IF NOT EXISTS budget_lines (
    id INT PRIMARY KEY AUTO_INCREMENT,
    budget_id INT NOT NULL,
    account_number VARCHAR(10) NOT NULL,
    period INT NOT NULL,  -- 1-12 for months
    amount DECIMAL(15,2) NOT NULL DEFAULT 0,

    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
    FOREIGN KEY (account_number) REFERENCES accounts(account_number),
    UNIQUE KEY unique_budget_line (budget_id, account_number, period),
    INDEX idx_budget_account (budget_id, account_number),
    INDEX idx_budget_period (budget_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
