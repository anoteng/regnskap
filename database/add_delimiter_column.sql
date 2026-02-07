-- Add delimiter column to csv_mappings table
-- Run this if you already have the csv_mappings table

ALTER TABLE csv_mappings
ADD COLUMN delimiter VARCHAR(1) DEFAULT ',' AFTER decimal_separator;
