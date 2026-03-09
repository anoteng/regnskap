-- Migration: Move receipt file storage from filesystem to database BLOB
-- This allows receipts to be included in database backups and replication

-- Add file_data column for storing file contents
ALTER TABLE receipts ADD COLUMN file_data LONGBLOB DEFAULT NULL AFTER image_path;

-- After running migrate_receipts_to_db.py to copy files into the column:
ALTER TABLE receipts DROP COLUMN image_path;
