-- Add transaction status field for posting queue functionality
-- This allows transactions to be reviewed before being posted

-- Add status enum to transactions table
ALTER TABLE transactions
ADD COLUMN status ENUM('DRAFT', 'POSTED', 'RECONCILED') DEFAULT 'POSTED' AFTER is_reconciled;

-- Update existing transactions to POSTED status
UPDATE transactions SET status = 'POSTED';

-- Make status NOT NULL after populating
ALTER TABLE transactions
MODIFY status ENUM('DRAFT', 'POSTED', 'RECONCILED') NOT NULL DEFAULT 'POSTED';

-- Add index for faster filtering
ALTER TABLE transactions
ADD INDEX idx_status (status);
