#!/usr/bin/env python3
"""
Migrate receipt files from filesystem to database BLOB storage.

Run AFTER 011_receipts_to_blob.sql has been applied.

Usage:
    python database/migrations/migrate_receipts_to_db.py

This script:
1. Reads all receipts that have image_path but no file_data
2. Reads the file from disk and stores it in the file_data column
3. Reports any missing files
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from urllib.parse import unquote, urlparse
import pymysql

def get_db_connection():
    db_url = os.getenv('DATABASE_URL', '')
    parsed = urlparse(db_url.replace('mysql+pymysql', 'mysql'))
    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=unquote(parsed.password),
        database=parsed.path.lstrip('/')
    )

def main():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT id, image_path FROM receipts WHERE file_data IS NULL AND image_path IS NOT NULL")
    receipts = cursor.fetchall()

    if not receipts:
        print("No receipts to migrate.")
        return

    print(f"Found {len(receipts)} receipts to migrate.")

    migrated = 0
    missing = 0

    for receipt in receipts:
        path = receipt['image_path']
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = f.read()
            cursor.execute(
                "UPDATE receipts SET file_data = %s WHERE id = %s",
                (data, receipt['id'])
            )
            migrated += 1
            if migrated % 10 == 0:
                conn.commit()
                print(f"  Migrated {migrated}/{len(receipts)}...")
        else:
            print(f"  WARNING: File not found for receipt {receipt['id']}: {path}")
            missing += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nDone: {migrated} migrated, {missing} missing files.")
    if missing == 0:
        print("All files migrated. You can now safely drop the image_path column:")
        print("  ALTER TABLE receipts DROP COLUMN image_path;")
        print("And delete the uploads/receipts directory.")

if __name__ == '__main__':
    main()
