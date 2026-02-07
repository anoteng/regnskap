-- Add invert_amount field to csv_mappings table
ALTER TABLE csv_mappings
ADD COLUMN invert_amount BOOLEAN DEFAULT FALSE AFTER delimiter;

-- Add comment
ALTER TABLE csv_mappings
MODIFY invert_amount BOOLEAN DEFAULT FALSE COMMENT 'If true, multiply amount by -1 (for banks where negative = expense)';
