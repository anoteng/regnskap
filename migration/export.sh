#!/bin/bash
# Export script - run on the OLD server before migration
# Usage: bash /home/andreas/regnskap/migration/export.sh
#
# Creates a database dump that can be imported on the new server.
# Receipts are included (stored as BLOBs in the database).

set -e

EXPORT_DIR="/home/andreas/regnskap-export-$(date +%Y%m%d)"
mkdir -p "$EXPORT_DIR"

echo "=== Privatregnskap.eu - Data Export ==="
echo "Exporting to: $EXPORT_DIR"

# 1. Database dump (includes everything: data + receipts as BLOBs)
echo "[1/3] Dumping database..."
source /home/andreas/regnskap/.env 2>/dev/null
DB_PASS=$(python3 -c "from urllib.parse import unquote; import os; url=os.environ['DATABASE_URL']; print(unquote(url.split(':')[2].rsplit('@',1)[0]))")

mysqldump -u regnskap -p"$DB_PASS" \
  --single-transaction --routines --triggers \
  regnskap > "$EXPORT_DIR/regnskap.sql"
echo "  Database dumped ($(du -h "$EXPORT_DIR/regnskap.sql" | cut -f1))"

# 2. Enable Banking certificates
echo "[2/3] Copying certificates..."
if [ -d /home/andreas/regnskap/certificates ]; then
    cp -a /home/andreas/regnskap/certificates "$EXPORT_DIR/certificates"
    echo "  Certificates copied"
else
    echo "  No certificates directory found (skipped)"
fi

# 3. .env for reference (contains SMTP settings etc.)
echo "[3/3] Copying .env for reference..."
cp /home/andreas/regnskap/.env "$EXPORT_DIR/env.reference"
echo "  .env saved as reference"

echo ""
echo "=== Export complete ==="
echo "Directory: $EXPORT_DIR"
echo "Size: $(du -sh "$EXPORT_DIR" | cut -f1)"
echo ""
echo "Transfer to new server:"
echo "  scp -r $EXPORT_DIR andreas@NEW_SERVER_IP:~/"
echo ""
echo "Then on new server:"
echo "  mysql -u regnskap -p'PASSWORD' regnskap < ~/$(basename $EXPORT_DIR)/regnskap.sql"
echo "  cp -a ~/$(basename $EXPORT_DIR)/certificates/* /home/andreas/regnskap/certificates/"
echo "  chmod 600 /home/andreas/regnskap/certificates/private.key"
