#!/bin/bash
# Setup script for NEW Hetzner server
# Run as root on the new server
# Usage: sudo bash setup-new-server.sh
#
# This script sets up a fresh installation with empty database + seed data.
# Import a dump from the old server afterwards to migrate data.
#
# Prerequisites:
#   - Debian 12/13 installed
#   - User 'andreas' exists
#   - Git repo cloned to /home/andreas/regnskap

set -e

DOMAIN="privatregnskap.eu"
APP_DIR="/home/andreas/regnskap"

if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: $APP_DIR not found"
    echo "Clone the repo first: git clone <repo> $APP_DIR"
    exit 1
fi

echo "=== Privatregnskap.eu - Server Setup ==="
echo "Domain: $DOMAIN"
echo ""

# ============================================
# 1. SYSTEM PACKAGES
# ============================================
echo "[1/8] Installing system packages..."
apt update
apt install -y \
  mariadb-server \
  nginx \
  certbot python3-certbot-nginx \
  python3-venv python3-pip \
  python3-fastapi python3-uvicorn python3-sqlalchemy \
  python3-pymysql python3-cryptography python3-passlib \
  python3-dotenv python3-pydantic python3-pydantic-settings \
  python3-multipart \
  python3-httpx python3-jwt

# ============================================
# 2. GENERATE DATABASE PASSWORD
# ============================================
echo "[2/8] Setting up MariaDB..."

DB_PASS=$(openssl rand -base64 24 | tr -d '/+=')
DB_PASS_URL=$(python3 -c "from urllib.parse import quote; print(quote('$DB_PASS', safe=''))")

mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS regnskap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'regnskap'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON regnskap.* TO 'regnskap'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "  Database and user created"

# Import schema
echo "  Importing schema..."
mysql -u regnskap -p"$DB_PASS" regnskap < "$APP_DIR/database/schema.sql"

# Import seed data (templates, subscription plans, bank providers)
echo "  Importing seed data..."
mysql -u regnskap -p"$DB_PASS" regnskap < "$APP_DIR/database/seed.sql"

echo "  Database ready"

# ============================================
# 3. MARIADB ENCRYPTION AT REST
# ============================================
echo "[3/8] Configuring MariaDB encryption at rest..."
mkdir -p /etc/mysql/encryption
openssl rand -hex 32 > /tmp/keyraw
echo "1;$(cat /tmp/keyraw)" > /etc/mysql/encryption/keys.enc
rm /tmp/keyraw
chmod 600 /etc/mysql/encryption/keys.enc
chown mysql:mysql /etc/mysql/encryption/keys.enc

cat > /etc/mysql/mariadb.conf.d/70-encryption.cnf <<'EOF'
[mariadb]
plugin_load_add = file_key_management
file_key_management_filename = /etc/mysql/encryption/keys.enc

innodb_encrypt_tables = ON
innodb_encrypt_log = ON
innodb_encryption_threads = 4
encrypt_tmp_disk_tables = ON
encrypt_tmp_files = ON
encrypt_binlog = ON
EOF

systemctl restart mariadb
echo "  MariaDB encryption enabled"

# ============================================
# 4. MARIADB REPLICATION (REPLICA CONFIG)
# ============================================
echo "[4/8] Configuring MariaDB for replication..."
cat > /etc/mysql/mariadb.conf.d/80-replication.cnf <<'EOF'
[mariadb]
server-id = 1
log_bin = /var/log/mysql/mariadb-bin
binlog_format = ROW
expire_logs_days = 14
max_binlog_size = 100M
EOF

systemctl restart mariadb
echo "  Binary logging enabled (ready for replica setup)"

# ============================================
# 5. PYTHON VENV
# ============================================
echo "[5/8] Setting up Python virtualenv..."
su - andreas -c "
  cd $APP_DIR
  python3 -m venv venv --system-site-packages
  venv/bin/pip install 'python-jose[cryptography]' 'webauthn>=1.11.0' openpyxl
"

# ============================================
# 6. GENERATE .env
# ============================================
echo "[6/8] Generating .env..."

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

chown andreas:andreas "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
echo "  .env generated (fill in SMTP settings manually)"

# ============================================
# 7. SYSTEMD SERVICE
# ============================================
echo "[7/8] Creating systemd service..."
cat > /etc/systemd/system/regnskap.service <<'EOF'
[Unit]
Description=Privatregnskap.eu FastAPI Application
After=network.target mysql.service
Requires=mysql.service

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

systemctl daemon-reload
systemctl enable regnskap

# ============================================
# 8. NGINX + SSL
# ============================================
echo "[8/8] Configuring nginx..."
cat > /etc/nginx/sites-available/$DOMAIN <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 20M;

    location /api {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    access_log /var/log/nginx/$DOMAIN.access.log;
    error_log /var/log/nginx/$DOMAIN.error.log;
}
NGINX

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== Setup complete ==="
echo ""
echo "Database password: $DB_PASS"
echo "(saved in $APP_DIR/.env)"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Copy Enable Banking certificates:"
echo "   scp certificates/* andreas@$(hostname -I | awk '{print $1}'):$APP_DIR/certificates/"
echo "   chmod 600 $APP_DIR/certificates/private.key"
echo ""
echo "2. Fill in SMTP settings in $APP_DIR/.env"
echo ""
echo "3. Point DNS for $DOMAIN to this server"
echo ""
echo "4. Get SSL certificate (after DNS is active):"
echo "   sudo certbot --nginx -d $DOMAIN"
echo ""
echo "5. Start the app:"
echo "   sudo systemctl start regnskap"
echo ""
echo "6. To import data from old server:"
echo "   # On old server:"
echo "   bash migration/export.sh"
echo "   scp ~/regnskap-export-*/regnskap.sql andreas@NEW_IP:~/"
echo "   # On new server:"
echo "   mysql -u regnskap -p'$DB_PASS' regnskap < ~/regnskap.sql"
echo ""
echo "7. Re-register passkeys (domain changed) and re-authorize bank connections"
