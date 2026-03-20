#!/bin/bash
# Setup script for Hetzner server (privatregnskap.eu)
# Assumes: MariaDB, nginx+SSL, Python 3.13 already installed
#
# Run as user andreas - sudo will be used for systemd steps
# Usage: bash setup-hetzner.sh

set -e

APP_DIR="/home/andreas/regnskap"
DOMAIN="privatregnskap.eu"

echo "=== Privatregnskap.eu - Hetzner Setup ==="
echo ""

# ============================================
# 1. CLONE REPO (if not already there)
# ============================================
if [ ! -d "$APP_DIR/.git" ]; then
    echo "[1/6] Cloning repository..."
    git clone https://github.com/anoteng/regnskap.git "$APP_DIR"
else
    echo "[1/6] Repo already exists, pulling latest..."
    cd "$APP_DIR" && git pull
fi
cd "$APP_DIR"

# ============================================
# 2. PYTHON VENV
# ============================================
echo "[2/6] Setting up Python virtualenv..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv venv --system-site-packages
fi
venv/bin/pip install --quiet 'python-jose[cryptography]' 'webauthn>=1.11.0' openpyxl

echo "  Installed missing packages"

# ============================================
# 3. DATABASE
# ============================================
echo "[3/6] Setting up database..."

DB_PASS=$(openssl rand -base64 24 | tr -d '/+=')
DB_PASS_URL=$(python3 -c "from urllib.parse import quote; print(quote('$DB_PASS', safe=''))")

echo "  Creating database and user..."
sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS regnskap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'regnskap'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON regnskap.* TO 'regnskap'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "  Importing schema..."
mysql -u regnskap -p"$DB_PASS" regnskap < "$APP_DIR/database/schema.sql"

echo "  Importing seed data..."
mysql -u regnskap -p"$DB_PASS" regnskap < "$APP_DIR/database/seed.sql"

echo "  Database ready"

# ============================================
# 4. GENERATE .env
# ============================================
echo "[4/6] Generating .env..."

SECRET_KEY=$(openssl rand -base64 48 | tr -d '/+=')

cat > "$APP_DIR/.env" <<EOF
DATABASE_URL=mysql+pymysql://regnskap:${DB_PASS_URL}@localhost:3306/regnskap
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=https://${DOMAIN}

# WebAuthn / Passkey settings
RP_ID=${DOMAIN}
RP_NAME=Privatregnskap.eu

# SMTP settings for password reset emails
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
EOF

chmod 600 "$APP_DIR/.env"
echo "  .env generated"

# ============================================
# 5. DIRECTORIES
# ============================================
echo "[5/6] Creating directories..."
mkdir -p "$APP_DIR/certificates"

# ============================================
# 6. SYSTEMD SERVICE
# ============================================
echo "[6/6] Installing systemd service..."

sudo tee /etc/systemd/system/regnskap.service > /dev/null <<'EOF'
[Unit]
Description=Privatregnskap.eu FastAPI Application
After=network.target mariadb.service
Requires=mariadb.service

[Service]
Type=simple
User=andreas
Group=andreas
WorkingDirectory=/home/andreas/regnskap
EnvironmentFile=/home/andreas/regnskap/.env
ExecStart=/home/andreas/regnskap/venv/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=regnskap
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable regnskap
echo "  Service installed and enabled"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Database password: $DB_PASS"
echo "(saved in $APP_DIR/.env)"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Copy Enable Banking certificates from old server:"
echo "   scp andreas@media.noteng.no:~/regnskap/certificates/* $APP_DIR/certificates/"
echo "   chmod 600 $APP_DIR/certificates/private.key"
echo ""
echo "2. Fill in SMTP settings in $APP_DIR/.env"
echo ""
echo "3. Export and import data from old server:"
echo "   ssh andreas@media.noteng.no 'cd ~/regnskap && bash migration/export.sh'"
echo "   scp andreas@media.noteng.no:~/regnskap-export-*/regnskap.sql ~/"
echo "   mysql -u regnskap -p'$DB_PASS' regnskap < ~/regnskap.sql"
echo ""
echo "4. Start the app:"
echo "   sudo systemctl start regnskap"
echo "   sudo journalctl -u regnskap -f"
echo ""
echo "5. Re-register passkeys and re-authorize bank connections"
