/*M!999999\- enable the sandbox mode */ 

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;
DROP TABLE IF EXISTS `accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `account_number` varchar(10) NOT NULL,
  `account_name` varchar(255) NOT NULL,
  `account_type` enum('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE') NOT NULL,
  `parent_account_id` int(11) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `description` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_account_per_ledger` (`ledger_id`,`account_number`),
  KEY `idx_account_type` (`account_type`),
  KEY `idx_parent` (`parent_account_id`),
  KEY `idx_ledger` (`ledger_id`),
  CONSTRAINT `accounts_ibfk_1` FOREIGN KEY (`parent_account_id`) REFERENCES `accounts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_account_ledger` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1456 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ai_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `provider` varchar(50) NOT NULL COMMENT 'openai, anthropic, etc.',
  `api_key` text NOT NULL,
  `model` varchar(100) NOT NULL COMMENT 'gpt-4o, claude-3-5-sonnet, etc.',
  `is_active` tinyint(1) DEFAULT 1,
  `max_tokens` int(11) DEFAULT 4000,
  `temperature` decimal(3,2) DEFAULT 0.30,
  `config_notes` text DEFAULT NULL COMMENT 'Admin notes about this configuration',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ai_usage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_usage` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `ledger_id` int(11) DEFAULT NULL,
  `provider` varchar(50) NOT NULL,
  `model` varchar(100) NOT NULL,
  `operation_type` varchar(50) NOT NULL COMMENT 'receipt_analysis, posting_suggestion, etc.',
  `tokens_used` int(11) NOT NULL,
  `cost_usd` decimal(10,6) DEFAULT NULL COMMENT 'Estimated cost in USD',
  `request_data` text DEFAULT NULL COMMENT 'JSON data about the request',
  `response_data` text DEFAULT NULL COMMENT 'JSON data about the response',
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `ledger_id` (`ledger_id`),
  KEY `idx_ai_usage_user_id` (`user_id`),
  KEY `idx_ai_usage_created_at` (`created_at`),
  KEY `idx_ai_usage_operation` (`operation_type`),
  CONSTRAINT `ai_usage_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ai_usage_ibfk_2` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_accounts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `account_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `account_type` enum('CHECKING','SAVINGS','CREDIT_CARD') NOT NULL,
  `account_number` varchar(50) DEFAULT NULL,
  `balance` decimal(15,2) DEFAULT 0.00,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`),
  KEY `account_id` (`account_id`),
  KEY `idx_ledger` (`ledger_id`),
  CONSTRAINT `bank_accounts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_accounts_ibfk_2` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`),
  CONSTRAINT `bank_accounts_ibfk_3` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_connections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_connections` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `bank_account_id` int(11) NOT NULL COMMENT 'Links to existing bank_accounts table',
  `provider_id` int(11) NOT NULL,
  `external_bank_id` varchar(255) DEFAULT NULL COMMENT 'Bank institution ID from provider (ASPSP for Enable Banking)',
  `external_account_id` varchar(255) NOT NULL COMMENT 'Account ID from provider API',
  `external_account_name` varchar(255) DEFAULT NULL COMMENT 'Account name from bank',
  `external_account_iban` varchar(50) DEFAULT NULL COMMENT 'IBAN if available',
  `external_account_bic` varchar(20) DEFAULT NULL COMMENT 'BIC/SWIFT if available',
  `access_token` text DEFAULT NULL COMMENT 'Encrypted OAuth access token',
  `refresh_token` text DEFAULT NULL COMMENT 'Encrypted OAuth refresh token',
  `token_expires_at` datetime DEFAULT NULL COMMENT 'When access token expires',
  `status` varchar(20) DEFAULT 'ACTIVE' COMMENT 'ACTIVE, EXPIRED, DISCONNECTED, ERROR',
  `connection_error` text DEFAULT NULL COMMENT 'Last error message if status=ERROR',
  `last_sync_at` datetime DEFAULT NULL COMMENT 'Last sync attempt (success or failure)',
  `last_successful_sync_at` datetime DEFAULT NULL COMMENT 'Last successful sync',
  `auto_sync_enabled` tinyint(1) DEFAULT 1 COMMENT 'Enable automatic syncing',
  `initial_sync_from_date` date DEFAULT NULL,
  `sync_frequency_hours` int(11) DEFAULT 24 COMMENT 'Hours between auto-syncs',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `created_by` int(11) NOT NULL COMMENT 'User who created the connection',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_external_account` (`provider_id`,`external_account_id`),
  KEY `created_by` (`created_by`),
  KEY `idx_ledger_connections` (`ledger_id`),
  KEY `idx_bank_account` (`bank_account_id`),
  KEY `idx_sync_status` (`status`,`last_sync_at`),
  CONSTRAINT `bank_connections_ibfk_1` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_connections_ibfk_2` FOREIGN KEY (`bank_account_id`) REFERENCES `bank_accounts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_connections_ibfk_3` FOREIGN KEY (`provider_id`) REFERENCES `bank_providers` (`id`),
  CONSTRAINT `bank_connections_ibfk_4` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_providers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_providers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL COMMENT 'Provider identifier: enable_banking, tink, neonomics',
  `display_name` varchar(100) NOT NULL COMMENT 'Human-readable name',
  `is_active` tinyint(1) DEFAULT 1,
  `environment` varchar(20) NOT NULL COMMENT 'SANDBOX or PRODUCTION',
  `config_data` text DEFAULT NULL COMMENT 'JSON: API keys, certificate paths, app IDs, etc.',
  `authorization_url` varchar(500) DEFAULT NULL COMMENT 'OAuth authorization endpoint',
  `token_url` varchar(500) DEFAULT NULL COMMENT 'OAuth token exchange endpoint',
  `api_base_url` varchar(500) DEFAULT NULL COMMENT 'Base URL for API calls',
  `config_notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_active_providers` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_sync_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_sync_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bank_connection_id` int(11) NOT NULL,
  `sync_type` varchar(20) NOT NULL COMMENT 'MANUAL, AUTO, OAUTH_CONNECT',
  `sync_status` varchar(20) NOT NULL COMMENT 'SUCCESS, PARTIAL, FAILED',
  `transactions_fetched` int(11) DEFAULT 0 COMMENT 'Number of transactions fetched from bank',
  `transactions_imported` int(11) DEFAULT 0 COMMENT 'Number of new transactions imported',
  `transactions_duplicate` int(11) DEFAULT 0 COMMENT 'Number of duplicates skipped',
  `sync_from_date` date DEFAULT NULL COMMENT 'Start of sync date range',
  `sync_to_date` date DEFAULT NULL COMMENT 'End of sync date range',
  `error_message` text DEFAULT NULL COMMENT 'Error message if sync failed',
  `error_code` varchar(50) DEFAULT NULL COMMENT 'Error code from provider if available',
  `started_at` datetime NOT NULL,
  `completed_at` datetime DEFAULT NULL COMMENT 'When sync finished (NULL if still running)',
  `duration_seconds` int(11) DEFAULT NULL COMMENT 'Duration in seconds',
  `triggered_by` int(11) DEFAULT NULL COMMENT 'User ID for manual sync, NULL for auto-sync',
  PRIMARY KEY (`id`),
  KEY `triggered_by` (`triggered_by`),
  KEY `idx_connection_logs` (`bank_connection_id`,`started_at` DESC),
  KEY `idx_status` (`sync_status`),
  KEY `idx_started_at` (`started_at`),
  CONSTRAINT `bank_sync_logs_ibfk_1` FOREIGN KEY (`bank_connection_id`) REFERENCES `bank_connections` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_sync_logs_ibfk_2` FOREIGN KEY (`triggered_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=99 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `bank_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bank_connection_id` int(11) NOT NULL,
  `external_transaction_id` varchar(255) NOT NULL COMMENT 'Unique transaction ID from provider',
  `transaction_date` date NOT NULL COMMENT 'Transaction date (value date or booking date)',
  `booking_date` date DEFAULT NULL COMMENT 'When transaction was posted/booked',
  `value_date` date DEFAULT NULL COMMENT 'Value date for interest calculation',
  `amount` decimal(15,2) NOT NULL COMMENT 'Transaction amount',
  `currency` varchar(3) DEFAULT 'NOK',
  `description` text DEFAULT NULL COMMENT 'Transaction description/memo',
  `reference` varchar(255) DEFAULT NULL COMMENT 'Reference number (end-to-end ID, etc.)',
  `merchant_name` varchar(255) DEFAULT NULL COMMENT 'Creditor or debtor name',
  `merchant_category` varchar(100) DEFAULT NULL COMMENT 'Merchant category code if available',
  `dedup_hash` varchar(32) NOT NULL COMMENT 'MD5 hash of date|amount|description|reference',
  `import_status` varchar(20) DEFAULT 'PENDING' COMMENT 'PENDING, IMPORTED, DUPLICATE, IGNORED',
  `imported_transaction_id` int(11) DEFAULT NULL COMMENT 'Links to transactions table if imported',
  `raw_data` text DEFAULT NULL COMMENT 'Full JSON response from provider API',
  `fetched_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_external_transaction` (`bank_connection_id`,`external_transaction_id`),
  KEY `imported_transaction_id` (`imported_transaction_id`),
  KEY `idx_dedup_hash` (`dedup_hash`),
  KEY `idx_import_status` (`import_status`),
  KEY `idx_connection_date` (`bank_connection_id`,`transaction_date`),
  CONSTRAINT `bank_transactions_ibfk_1` FOREIGN KEY (`bank_connection_id`) REFERENCES `bank_connections` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_transactions_ibfk_2` FOREIGN KEY (`imported_transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2543 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `budget_lines`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `budget_lines` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `budget_id` int(11) NOT NULL,
  `account_id` int(11) DEFAULT NULL,
  `period` int(11) NOT NULL,
  `amount` decimal(15,2) NOT NULL DEFAULT 0.00,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_budget_line` (`budget_id`,`account_id`,`period`),
  KEY `idx_budget_period` (`budget_id`,`period`),
  KEY `budget_lines_ibfk_account` (`account_id`),
  CONSTRAINT `budget_lines_ibfk_1` FOREIGN KEY (`budget_id`) REFERENCES `budgets` (`id`) ON DELETE CASCADE,
  CONSTRAINT `budget_lines_ibfk_account` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1909 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `budgets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `budgets` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `year` int(11) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `created_by` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by` (`created_by`),
  KEY `idx_ledger_year` (`ledger_id`,`year`),
  CONSTRAINT `budgets_ibfk_1` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `budgets_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `name` varchar(100) NOT NULL,
  `color` varchar(7) DEFAULT NULL,
  `icon` varchar(50) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_category` (`user_id`,`name`),
  KEY `idx_ledger` (`ledger_id`),
  CONSTRAINT `categories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `categories_ibfk_2` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `chart_of_accounts_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `chart_of_accounts_templates` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `display_name` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `is_default` tinyint(1) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_active` (`is_active`),
  KEY `idx_default` (`is_default`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `csv_mappings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `csv_mappings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `name` varchar(255) NOT NULL,
  `date_column` varchar(100) NOT NULL,
  `description_column` varchar(100) NOT NULL,
  `amount_column` varchar(100) NOT NULL,
  `reference_column` varchar(100) DEFAULT NULL,
  `date_format` varchar(50) DEFAULT 'YYYY-MM-DD',
  `decimal_separator` varchar(1) DEFAULT '.',
  `delimiter` varchar(1) DEFAULT ',',
  `invert_amount` tinyint(1) DEFAULT 0 COMMENT 'If true, multiply amount by -1 (for banks where negative = expense)',
  `skip_rows` int(11) DEFAULT 0,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_mapping_name` (`user_id`,`name`),
  KEY `idx_ledger` (`ledger_id`),
  CONSTRAINT `csv_mappings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `csv_mappings_ibfk_2` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `import_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `import_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `bank_account_id` int(11) NOT NULL,
  `csv_mapping_id` int(11) DEFAULT NULL,
  `file_name` varchar(255) NOT NULL,
  `rows_imported` int(11) DEFAULT 0,
  `rows_failed` int(11) DEFAULT 0,
  `import_date` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `bank_account_id` (`bank_account_id`),
  KEY `csv_mapping_id` (`csv_mapping_id`),
  KEY `idx_ledger` (`ledger_id`),
  CONSTRAINT `import_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `import_logs_ibfk_2` FOREIGN KEY (`bank_account_id`) REFERENCES `bank_accounts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `import_logs_ibfk_3` FOREIGN KEY (`csv_mapping_id`) REFERENCES `csv_mappings` (`id`) ON DELETE SET NULL,
  CONSTRAINT `import_logs_ibfk_4` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `journal_entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `journal_entries` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `transaction_id` int(11) NOT NULL,
  `account_id` int(11) NOT NULL,
  `debit` decimal(15,2) DEFAULT 0.00,
  `credit` decimal(15,2) DEFAULT 0.00,
  `description` varchar(500) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_transaction` (`transaction_id`),
  KEY `idx_account` (`account_id`),
  CONSTRAINT `journal_entries_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `journal_entries_ibfk_2` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`),
  CONSTRAINT `check_debit_credit` CHECK (`debit` > 0 and `credit` = 0 or `credit` > 0 and `debit` = 0)
) ENGINE=InnoDB AUTO_INCREMENT=3181 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ledger_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ledger_members` (
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `role` enum('OWNER','MEMBER','VIEWER') NOT NULL DEFAULT 'MEMBER',
  `joined_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`ledger_id`,`user_id`),
  KEY `idx_user` (`user_id`),
  CONSTRAINT `ledger_members_ibfk_1` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ledger_members_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ledgers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ledgers` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `created_by` int(11) NOT NULL,
  `chart_template_id` int(11) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `is_active` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `idx_created_by` (`created_by`),
  KEY `idx_template` (`chart_template_id`),
  CONSTRAINT `fk_ledger_template` FOREIGN KEY (`chart_template_id`) REFERENCES `chart_of_accounts_templates` (`id`) ON DELETE SET NULL,
  CONSTRAINT `ledgers_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `oauth_states`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `oauth_states` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `state_token` varchar(64) NOT NULL COMMENT 'Random token for CSRF protection',
  `user_id` int(11) NOT NULL,
  `ledger_id` int(11) NOT NULL,
  `bank_account_id` int(11) NOT NULL COMMENT 'Which bank account user is connecting',
  `provider_id` int(11) NOT NULL,
  `external_bank_id` varchar(100) DEFAULT NULL,
  `initial_sync_from_date` date DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `expires_at` datetime NOT NULL COMMENT '10 minute expiry for security',
  `used_at` datetime DEFAULT NULL COMMENT 'When state was consumed (callback received)',
  `accounts_data` text DEFAULT NULL COMMENT 'JSON array of accounts from OAuth provider',
  PRIMARY KEY (`id`),
  UNIQUE KEY `state_token` (`state_token`),
  KEY `user_id` (`user_id`),
  KEY `ledger_id` (`ledger_id`),
  KEY `bank_account_id` (`bank_account_id`),
  KEY `provider_id` (`provider_id`),
  KEY `idx_state_token` (`state_token`),
  KEY `idx_expires` (`expires_at`),
  CONSTRAINT `oauth_states_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `oauth_states_ibfk_2` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `oauth_states_ibfk_3` FOREIGN KEY (`bank_account_id`) REFERENCES `bank_accounts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `oauth_states_ibfk_4` FOREIGN KEY (`provider_id`) REFERENCES `bank_providers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `password_reset_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_tokens` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `token` varchar(64) NOT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `expires_at` datetime NOT NULL,
  `used_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_token` (`token`),
  CONSTRAINT `password_reset_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `receipts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `receipts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `uploaded_by` int(11) NOT NULL,
  `file_data` longblob DEFAULT NULL,
  `original_filename` varchar(255) DEFAULT NULL,
  `file_size` int(11) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL,
  `upload_date` datetime DEFAULT current_timestamp(),
  `attachment_type` enum('RECEIPT','INVOICE') NOT NULL DEFAULT 'RECEIPT',
  `receipt_date` date DEFAULT NULL,
  `due_date` date DEFAULT NULL COMMENT 'Due date for invoices',
  `amount` decimal(10,2) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `status` enum('PENDING','MATCHED','ARCHIVED') DEFAULT 'PENDING',
  `matched_transaction_id` int(11) DEFAULT NULL,
  `matched_at` datetime DEFAULT NULL,
  `matched_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `ai_extracted_date` date DEFAULT NULL COMMENT 'Date extracted by AI',
  `ai_extracted_amount` decimal(10,2) DEFAULT NULL COMMENT 'Amount extracted by AI',
  `ai_extracted_vendor` varchar(255) DEFAULT NULL COMMENT 'Vendor/merchant name',
  `ai_extracted_description` text DEFAULT NULL COMMENT 'Description extracted by AI',
  `ai_suggested_account` varchar(10) DEFAULT NULL COMMENT 'Suggested account number',
  `ai_confidence` decimal(3,2) DEFAULT NULL COMMENT 'AI confidence score 0-1',
  `ai_processed_at` datetime DEFAULT NULL COMMENT 'When AI processing was done',
  `ai_processing_error` text DEFAULT NULL COMMENT 'Error if AI processing failed',
  PRIMARY KEY (`id`),
  KEY `uploaded_by` (`uploaded_by`),
  KEY `matched_by` (`matched_by`),
  KEY `idx_ledger_status` (`ledger_id`,`status`),
  KEY `idx_upload_date` (`upload_date`),
  KEY `idx_receipt_date` (`receipt_date`),
  KEY `idx_matched_transaction` (`matched_transaction_id`),
  CONSTRAINT `receipts_ibfk_1` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `receipts_ibfk_2` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`),
  CONSTRAINT `receipts_ibfk_3` FOREIGN KEY (`matched_transaction_id`) REFERENCES `transactions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `receipts_ibfk_4` FOREIGN KEY (`matched_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `subscription_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `subscription_plans` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `tier` varchar(10) NOT NULL,
  `description` text DEFAULT NULL,
  `price_monthly` decimal(10,2) NOT NULL DEFAULT 0.00,
  `price_yearly` decimal(10,2) DEFAULT NULL,
  `features` text DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `max_documents` int(11) DEFAULT NULL COMMENT 'Max total documents/receipts (NULL = unlimited)',
  `max_monthly_uploads` int(11) DEFAULT NULL COMMENT 'Max uploads per month (NULL = unlimited)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `tier` (`tier`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `template_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `template_accounts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `template_id` int(11) NOT NULL,
  `account_number` varchar(10) NOT NULL,
  `account_name` varchar(255) NOT NULL,
  `account_type` enum('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE') NOT NULL,
  `parent_account_number` varchar(10) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `is_default` tinyint(1) DEFAULT 1 COMMENT 'If true, included by default when creating ledger',
  `sort_order` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_account_per_template` (`template_id`,`account_number`),
  KEY `idx_template_type` (`template_id`,`account_type`),
  KEY `idx_parent` (`template_id`,`parent_account_number`),
  CONSTRAINT `template_accounts_ibfk_1` FOREIGN KEY (`template_id`) REFERENCES `chart_of_accounts_templates` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=334 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `transaction_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `transaction_categories` (
  `transaction_id` int(11) NOT NULL,
  `category_id` int(11) NOT NULL,
  PRIMARY KEY (`transaction_id`,`category_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `transaction_categories_ibfk_1` FOREIGN KEY (`transaction_id`) REFERENCES `transactions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `transaction_categories_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `transactions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ledger_id` int(11) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `transaction_date` date NOT NULL,
  `description` varchar(500) NOT NULL,
  `reference` varchar(100) DEFAULT NULL,
  `is_reconciled` tinyint(1) DEFAULT 0,
  `status` enum('DRAFT','POSTED','RECONCILED') NOT NULL DEFAULT 'POSTED',
  `source` varchar(20) DEFAULT 'MANUAL' COMMENT 'MANUAL, CSV_IMPORT, BANK_SYNC',
  `source_reference` varchar(255) DEFAULT NULL COMMENT 'External transaction ID if from bank sync',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `ai_suggested` tinyint(1) DEFAULT 0 COMMENT 'Whether this was AI-suggested',
  `ai_suggestion_data` text DEFAULT NULL COMMENT 'JSON with AI suggestion details',
  PRIMARY KEY (`id`),
  KEY `idx_user_date` (`user_id`,`transaction_date`),
  KEY `idx_date` (`transaction_date`),
  KEY `idx_ledger` (`ledger_id`),
  KEY `created_by` (`created_by`),
  KEY `idx_status` (`status`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `transactions_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2627 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_monthly_usage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_monthly_usage` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `year` int(11) NOT NULL,
  `month` int(11) NOT NULL,
  `upload_count` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `ai_operations_count` int(11) DEFAULT 0 COMMENT 'AI operations this month',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_month` (`user_id`,`year`,`month`),
  KEY `idx_user_monthly_usage_user_id` (`user_id`),
  KEY `idx_user_monthly_usage_period` (`year`,`month`),
  CONSTRAINT `user_monthly_usage_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_subscriptions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_subscriptions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `plan_id` int(11) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'ACTIVE',
  `started_at` datetime DEFAULT current_timestamp(),
  `expires_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `discount_percentage` decimal(5,2) DEFAULT 0.00,
  `custom_price` decimal(10,2) DEFAULT NULL,
  `is_free_forever` tinyint(1) DEFAULT 0,
  `admin_notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `plan_id` (`plan_id`),
  KEY `idx_user_subscriptions_user_id` (`user_id`),
  KEY `idx_user_subscriptions_status` (`status`),
  CONSTRAINT `user_subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_subscriptions_ibfk_2` FOREIGN KEY (`plan_id`) REFERENCES `subscription_plans` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `hashed_password` varchar(255) NOT NULL,
  `full_name` varchar(255) NOT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `last_active_ledger_id` int(11) DEFAULT NULL,
  `is_admin` tinyint(1) DEFAULT 0,
  `ai_access_enabled` tinyint(1) DEFAULT 1 COMMENT 'Admin can disable AI access for specific users',
  `ai_access_blocked_reason` text DEFAULT NULL COMMENT 'Reason why AI access was blocked',
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_email` (`email`),
  KEY `last_active_ledger_id` (`last_active_ledger_id`),
  KEY `idx_users_is_admin` (`is_admin`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`last_active_ledger_id`) REFERENCES `ledgers` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `webauthn_credentials`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `webauthn_credentials` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `credential_id` varchar(1024) NOT NULL,
  `public_key` text NOT NULL,
  `sign_count` int(11) NOT NULL DEFAULT 0,
  `credential_name` varchar(255) DEFAULT NULL,
  `transports` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`transports`)),
  `aaguid` varchar(36) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `last_used_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `credential_id` (`credential_id`) USING HASH,
  KEY `idx_user_id` (`user_id`),
  KEY `idx_credential_id` (`credential_id`(255)),
  CONSTRAINT `webauthn_credentials_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

