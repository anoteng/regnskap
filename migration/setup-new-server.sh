#!/bin/bash
# Setup script for NEW Hetzner server
# Run as root on the new server
# Usage: sudo bash setup-new-server.sh
#
# Prerequisites:
#   - Debian 13 (or similar) installed
#   - User 'andreas' exists
#   - Export directory transferred to /home/andreas/regnskap-export-YYYYMMDD/

set -e

DOMAIN="privatregnskap.eu"
EXPORT_DIR=$(ls -d /home/andreas/regnskap-export-* 2>/dev/null | head -1)

if [ -z "$EXPORT_DIR" ]; then
    echo "ERROR: No export directory found at /home/andreas/regnskap-export-*"
    echo "Transfer export from old server first."
    exit 1
fi

echo "=== Regnskap - New Server Setup ==="
echo "Using export: $EXPORT_DIR"
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
# 2. MARIADB SETUP
# ============================================
echo "[2/8] Setting up MariaDB..."

# Create database and user
mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS regnskap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'regnskap'@'localhost' IDENTIFIED BY '4^jLTtsB&fI&uo*#j@M0';
GRANT ALL PRIVILEGES ON regnskap.* TO 'regnskap'@'localhost';
FLUSH PRIVILEGES;
SQL

# Import database
echo "  Importing database..."
mysql -u regnskap -p'4^jLTtsB&fI&uo*#j@M0' regnskap < "$EXPORT_DIR/regnskap.sql"
echo "  Database imported"

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
# 4. APPLICATION
# ============================================
echo "[4/8] Deploying application..."
tar xzf "$EXPORT_DIR/regnskap-app.tar.gz" -C /home/andreas/
chown -R andreas:andreas /home/andreas/regnskap

# Restore certificates with correct permissions
cp -a "$EXPORT_DIR/certificates/"* /home/andreas/regnskap/certificates/
chmod 600 /home/andreas/regnskap/certificates/private.key
chown andreas:andreas /home/andreas/regnskap/certificates/*

# ============================================
# 5. PYTHON VENV
# ============================================
echo "[5/8] Setting up Python virtualenv..."
su - andreas -c "
  cd /home/andreas/regnskap
  python3 -m venv venv --system-site-packages
  venv/bin/pip install 'python-jose[cryptography]' 'webauthn>=1.11.0'
"

# ============================================
# 6. UPDATE .env
# ============================================
echo "[6/8] Updating .env..."
sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" /home/andreas/regnskap/.env
sed -i "s|RP_ID=.*|RP_ID=$DOMAIN|" /home/andreas/regnskap/.env
echo "  Updated FRONTEND_URL and RP_ID to $DOMAIN"

# ============================================
# 7. SYSTEMD SERVICE
# ============================================
echo "[7/8] Creating systemd service..."
cat > /etc/systemd/system/regnskap.service <<'EOF'
[Unit]
Description=Regnskap FastAPI Application
After=network.target mysql.service
Requires=mysql.service

[Service]
Type=simple
User=andreas
Group=andreas
WorkingDirectory=/home/andreas/regnskap
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EnvironmentFile=/home/andreas/regnskap/.env
ExecStart=/home/andreas/regnskap/venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8002
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
cat > /etc/nginx/sites-available/$DOMAIN <<EOF
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
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /docs {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8002;
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

    access_log /var/log/nginx/regnskap.access.log;
    error_log /var/log/nginx/regnskap.error.log;
}
EOF

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== Setup complete ==="
echo ""
echo "REMAINING MANUAL STEPS:"
echo ""
echo "1. Point DNS for $DOMAIN to this server's IP"
echo ""
echo "2. Get SSL certificate (after DNS is active):"
echo "   sudo certbot --nginx -d $DOMAIN"
echo ""
echo "3. Start the application:"
echo "   sudo systemctl start regnskap"
echo ""
echo "4. Re-authorize Enable Banking connections:"
echo "   - Go to https://$DOMAIN"
echo "   - Navigate to Bankkoblinger"
echo "   - Re-connect each bank account (new OAuth session needed)"
echo ""
echo "5. Re-register Passkeys (WebAuthn RP_ID changed):"
echo "   - Users must log in with password first"
echo "   - Then register new passkeys for the new domain"
echo ""
echo "6. Verify MariaDB encryption:"
echo "   sudo mysql -e \"SHOW GLOBAL VARIABLES LIKE '%encrypt%';\""
