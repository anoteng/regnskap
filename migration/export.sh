#!/bin/bash
# Export script - run on the OLD server before migration
# Usage: bash /home/andreas/regnskap/migration/export.sh

set -e

EXPORT_DIR="/home/andreas/regnskap-export-$(date +%Y%m%d)"
mkdir -p "$EXPORT_DIR"

echo "=== Regnskap Migration Export ==="
echo "Exporting to: $EXPORT_DIR"

# 1. Database dump
echo "[1/4] Dumping database..."
mysqldump -u regnskap -p'4^jLTtsB&fI&uo*#j@M0' \
  --single-transaction --routines --triggers \
  regnskap > "$EXPORT_DIR/regnskap.sql"
echo "  Database dumped ($(du -h "$EXPORT_DIR/regnskap.sql" | cut -f1))"

# 2. Application code (excluding venv and temp files)
echo "[2/4] Archiving application..."
tar czf "$EXPORT_DIR/regnskap-app.tar.gz" \
  -C /home/andreas \
  --exclude='regnskap/venv' \
  --exclude='regnskap/.git' \
  --exclude='regnskap/__pycache__' \
  --exclude='regnskap/backend/__pycache__' \
  --exclude='regnskap/backend/app/__pycache__' \
  --exclude='regnskap/migration' \
  --exclude='*.pyc' \
  regnskap/
echo "  Application archived ($(du -h "$EXPORT_DIR/regnskap-app.tar.gz" | cut -f1))"

# 3. Enable Banking certificates (separate for security)
echo "[3/4] Copying certificates..."
cp -a /home/andreas/regnskap/certificates "$EXPORT_DIR/certificates"
echo "  Certificates copied"

# 4. Config files for reference
echo "[4/4] Copying config references..."
cp /etc/systemd/system/regnskap.service "$EXPORT_DIR/regnskap.service"
cp /etc/nginx/sites-available/regnskap.noteng.no "$EXPORT_DIR/nginx-regnskap.conf"
echo "  Config files copied"

echo ""
echo "=== Export complete ==="
echo "Directory: $EXPORT_DIR"
echo ""
echo "Transfer to new server with:"
echo "  scp -r $EXPORT_DIR andreas@NEW_SERVER_IP:~/"
