# Migration Guide: Home Server → Hetzner

## Overview
- **From:** debianserver (regnskap.noteng.no)
- **To:** Hetzner server (privatregnskap.eu)
- **App:** FastAPI + MariaDB + nginx, vanilla JS frontend
- **Bank integration:** Enable Banking with mTLS certificates

## Option A: Fresh install + data import (recommended)

### 1. Setup new server

On the Hetzner server:
```bash
# Clone repo
git clone <repo> /home/andreas/regnskap

# Run setup (as root)
sudo bash /home/andreas/regnskap/migration/setup-new-server.sh
```

This creates the database with schema + seed data, installs dependencies,
configures nginx, and generates a fresh .env with new passwords.

### 2. Export data from old server

On the old server:
```bash
bash /home/andreas/regnskap/migration/export.sh
scp -r ~/regnskap-export-* andreas@HETZNER_IP:~/
```

### 3. Import data on new server

```bash
# Import database dump (replaces seed data with real data)
mysql -u regnskap -p'PASSWORD' regnskap < ~/regnskap-export-*/regnskap.sql

# Copy certificates
cp -a ~/regnskap-export-*/certificates/* /home/andreas/regnskap/certificates/
chmod 600 /home/andreas/regnskap/certificates/private.key
```

### 4. Post-migration

```bash
# DNS: Point privatregnskap.eu to Hetzner IP

# SSL certificate (after DNS propagation)
sudo certbot --nginx -d privatregnskap.eu

# Fill in SMTP settings in .env
nano /home/andreas/regnskap/.env

# Start app
sudo systemctl start regnskap
```

## Option B: Ongoing replication (after migration)

Once both servers are running, set up MariaDB replication for automatic backup:

### On Hetzner (master):
```bash
# Create replication user
sudo mysql -e "
  CREATE USER 'repl'@'%' IDENTIFIED BY 'REPL_PASSWORD';
  GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
  FLUSH PRIVILEGES;
"

# Get binary log position
sudo mysql -e "SHOW MASTER STATUS;"
```

### On home server (replica):
```bash
# Configure as replica
sudo mysql -e "
  CHANGE MASTER TO
    MASTER_HOST='HETZNER_IP',
    MASTER_USER='repl',
    MASTER_PASSWORD='REPL_PASSWORD',
    MASTER_LOG_FILE='mariadb-bin.XXXXXX',
    MASTER_LOG_POS=POSITION;
  START SLAVE;
  SHOW SLAVE STATUS\G
"
```

### Nightly backup dumps (cron on home server):
```bash
# /etc/cron.d/regnskap-backup
0 3 * * * andreas mysqldump -u regnskap -p'PASSWORD' --single-transaction regnskap | gzip > /home/andreas/backups/regnskap-$(date +\%Y\%m\%d).sql.gz
0 4 * * * andreas find /home/andreas/backups -name "regnskap-*.sql.gz" -mtime +30 -delete
```

## Post-migration checklist

- [ ] MariaDB running with encryption at rest
- [ ] App starts without errors (`journalctl -u regnskap`)
- [ ] HTTPS working (certbot)
- [ ] Can log in with password
- [ ] Can register new passkey
- [ ] SMTP working (test password reset)
- [ ] Bank connections page loads
- [ ] Budget report works
- [ ] Receipt upload works (stored in DB)
- [ ] Data export works (Excel + ZIP)

## Things that need re-doing after migration

| What | Why | How |
|------|-----|-----|
| Passkeys | RP_ID changed (domain) | Users log in with password, register new passkeys |
| Bank connections | OAuth tied to callback URL | Re-authorize each connection |
| Enable Banking redirect | Dashboard config | Update callback URL in Enable Banking portal |

## Rollback
The old server remains untouched. If migration fails, point DNS back.
