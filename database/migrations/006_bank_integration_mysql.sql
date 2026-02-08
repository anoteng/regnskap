-- Bank Integration Migration
-- Enable Banking, Tink, Neonomics support with OAuth and transaction sync

-- Provider configuration (system-wide, admin-managed)
CREATE TABLE bank_providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT 'Provider identifier: enable_banking, tink, neonomics',
    display_name VARCHAR(100) NOT NULL COMMENT 'Human-readable name',
    is_active BOOLEAN DEFAULT TRUE,
    environment VARCHAR(20) NOT NULL COMMENT 'SANDBOX or PRODUCTION',

    -- Provider-specific configuration (stored as JSON)
    config_data TEXT COMMENT 'JSON: API keys, certificate paths, app IDs, etc.',

    -- OAuth endpoints
    authorization_url VARCHAR(500) COMMENT 'OAuth authorization endpoint',
    token_url VARCHAR(500) COMMENT 'OAuth token exchange endpoint',
    api_base_url VARCHAR(500) COMMENT 'Base URL for API calls',

    -- Admin notes
    config_notes TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_active_providers (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User's bank connections (OAuth tokens and connection status)
CREATE TABLE bank_connections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ledger_id INT NOT NULL,
    bank_account_id INT NOT NULL COMMENT 'Links to existing bank_accounts table',
    provider_id INT NOT NULL,

    -- External bank identifiers
    external_bank_id VARCHAR(255) COMMENT 'Bank institution ID from provider (ASPSP for Enable Banking)',
    external_account_id VARCHAR(255) NOT NULL COMMENT 'Account ID from provider API',
    external_account_name VARCHAR(255) COMMENT 'Account name from bank',
    external_account_iban VARCHAR(50) COMMENT 'IBAN if available',
    external_account_bic VARCHAR(20) COMMENT 'BIC/SWIFT if available',

    -- OAuth tokens (encrypted)
    access_token TEXT COMMENT 'Encrypted OAuth access token',
    refresh_token TEXT COMMENT 'Encrypted OAuth refresh token',
    token_expires_at DATETIME COMMENT 'When access token expires',

    -- Connection status
    status VARCHAR(20) DEFAULT 'ACTIVE' COMMENT 'ACTIVE, EXPIRED, DISCONNECTED, ERROR',
    connection_error TEXT COMMENT 'Last error message if status=ERROR',

    -- Sync settings
    last_sync_at DATETIME COMMENT 'Last sync attempt (success or failure)',
    last_successful_sync_at DATETIME COMMENT 'Last successful sync',
    auto_sync_enabled BOOLEAN DEFAULT TRUE COMMENT 'Enable automatic syncing',
    sync_frequency_hours INT DEFAULT 24 COMMENT 'Hours between auto-syncs',

    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NOT NULL COMMENT 'User who created the connection',

    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES bank_providers(id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,

    UNIQUE KEY unique_external_account (provider_id, external_account_id),
    INDEX idx_ledger_connections (ledger_id),
    INDEX idx_bank_account (bank_account_id),
    INDEX idx_sync_status (status, last_sync_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fetched bank transactions (staging table before import)
CREATE TABLE bank_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bank_connection_id INT NOT NULL,

    -- External transaction identifiers
    external_transaction_id VARCHAR(255) NOT NULL COMMENT 'Unique transaction ID from provider',

    -- Transaction data
    transaction_date DATE NOT NULL COMMENT 'Transaction date (value date or booking date)',
    booking_date DATE COMMENT 'When transaction was posted/booked',
    value_date DATE COMMENT 'Value date for interest calculation',
    amount DECIMAL(15, 2) NOT NULL COMMENT 'Transaction amount',
    currency VARCHAR(3) DEFAULT 'NOK',
    description TEXT COMMENT 'Transaction description/memo',
    reference VARCHAR(255) COMMENT 'Reference number (end-to-end ID, etc.)',

    -- Merchant/payee information (if available from provider)
    merchant_name VARCHAR(255) COMMENT 'Creditor or debtor name',
    merchant_category VARCHAR(100) COMMENT 'Merchant category code if available',

    -- Deduplication hash
    dedup_hash VARCHAR(32) NOT NULL COMMENT 'MD5 hash of date|amount|description|reference',

    -- Import status tracking
    import_status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'PENDING, IMPORTED, DUPLICATE, IGNORED',
    imported_transaction_id INT COMMENT 'Links to transactions table if imported',

    -- Raw API response for debugging
    raw_data TEXT COMMENT 'Full JSON response from provider API',

    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bank_connection_id) REFERENCES bank_connections(id) ON DELETE CASCADE,
    FOREIGN KEY (imported_transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,

    UNIQUE KEY unique_external_transaction (bank_connection_id, external_transaction_id),
    INDEX idx_dedup_hash (dedup_hash),
    INDEX idx_import_status (import_status),
    INDEX idx_connection_date (bank_connection_id, transaction_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sync operation audit log
CREATE TABLE bank_sync_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bank_connection_id INT NOT NULL,

    -- Sync operation metadata
    sync_type VARCHAR(20) NOT NULL COMMENT 'MANUAL, AUTO, OAUTH_CONNECT',
    sync_status VARCHAR(20) NOT NULL COMMENT 'SUCCESS, PARTIAL, FAILED',

    -- Results
    transactions_fetched INT DEFAULT 0 COMMENT 'Number of transactions fetched from bank',
    transactions_imported INT DEFAULT 0 COMMENT 'Number of new transactions imported',
    transactions_duplicate INT DEFAULT 0 COMMENT 'Number of duplicates skipped',

    -- Date range synced
    sync_from_date DATE COMMENT 'Start of sync date range',
    sync_to_date DATE COMMENT 'End of sync date range',

    -- Error handling
    error_message TEXT COMMENT 'Error message if sync failed',
    error_code VARCHAR(50) COMMENT 'Error code from provider if available',

    -- Timing
    started_at DATETIME NOT NULL,
    completed_at DATETIME COMMENT 'When sync finished (NULL if still running)',
    duration_seconds INT COMMENT 'Duration in seconds',

    -- Who triggered the sync
    triggered_by INT COMMENT 'User ID for manual sync, NULL for auto-sync',

    FOREIGN KEY (bank_connection_id) REFERENCES bank_connections(id) ON DELETE CASCADE,
    FOREIGN KEY (triggered_by) REFERENCES users(id) ON DELETE SET NULL,

    INDEX idx_connection_logs (bank_connection_id, started_at DESC),
    INDEX idx_status (sync_status),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Temporary OAuth state tracking (for CSRF protection)
CREATE TABLE oauth_states (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state_token VARCHAR(64) NOT NULL UNIQUE COMMENT 'Random token for CSRF protection',
    user_id INT NOT NULL,
    ledger_id INT NOT NULL,
    bank_account_id INT NOT NULL COMMENT 'Which bank account user is connecting',
    provider_id INT NOT NULL,

    -- State metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL COMMENT '10 minute expiry for security',
    used_at DATETIME COMMENT 'When state was consumed (callback received)',

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES bank_providers(id) ON DELETE CASCADE,

    INDEX idx_state_token (state_token),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add source tracking to existing transactions table
ALTER TABLE transactions
ADD COLUMN source VARCHAR(20) DEFAULT 'MANUAL' COMMENT 'MANUAL, CSV_IMPORT, BANK_SYNC' AFTER status,
ADD COLUMN source_reference VARCHAR(255) COMMENT 'External transaction ID if from bank sync' AFTER source;

-- Seed data: Enable Banking provider (admin must configure API keys)
INSERT INTO bank_providers (name, display_name, is_active, environment, authorization_url, token_url, api_base_url, config_data, config_notes)
VALUES (
    'enable_banking',
    'Enable Banking',
    FALSE,  -- Admin activates after configuration
    'SANDBOX',
    'https://api.enablebanking.com/auth',
    'https://api.enablebanking.com/token',
    'https://api.enablebanking.com',
    '{"api_key":"","app_id":"","certificate_path":"","private_key_path":""}',
    'Enable Banking requires mTLS authentication with client certificate. Upload certificate files and configure app_id from Enable Banking developer portal.'
);

-- Placeholder for future providers (admin can add these later)
INSERT INTO bank_providers (name, display_name, is_active, environment, authorization_url, token_url, api_base_url, config_data, config_notes)
VALUES
(
    'tink',
    'Tink',
    FALSE,
    'SANDBOX',
    'https://link.tink.com/1.0/authorize',
    'https://api.tink.com/api/v1/oauth/token',
    'https://api.tink.com',
    '{"client_id":"","client_secret":""}',
    'Tink aggregation service. Configure client credentials from Tink Console.'
),
(
    'neonomics',
    'Neonomics',
    FALSE,
    'SANDBOX',
    'https://sandbox.neonomics.io/auth',
    'https://sandbox.neonomics.io/token',
    'https://sandbox.neonomics.io',
    '{"client_id":"","client_secret":"","x_api_key":""}',
    'Neonomics Norwegian banking API. Requires API key and OAuth credentials.'
);
