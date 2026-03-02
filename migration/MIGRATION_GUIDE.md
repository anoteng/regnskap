# Regnskap Migration Guide: debianserver → Hetzner

## Overview
- **From:** debianserver (regnskap.noteng.no)
- **To:** Hetzner server (privatregnskap.eu)
- **App:** FastAPI + MariaDB + nginx, vanilla JS frontend
- **Bank integration:** Enable Banking with mTLS certificates

## Pre-migration (old server)

```bash
cd /home/andreas/regnskap
bash migration/export.sh
scp -r /home/andreas/regnskap-export-* andreas@NEW_SERVER_IP:~/
```

## Setup (new server)

```bash
sudo bash /home/andreas/regnskap-export-*/../../regnskap/migration/setup-new-server.sh
```

Or if the script wasn't transferred, copy it from the repo:
```bash
# Transfer just the migration scripts
scp /home/andreas/regnskap/migration/*.sh andreas@NEW_SERVER_IP:~/
# Then on new server:
sudo bash ~/setup-new-server.sh
```

## Post-migration manual steps

### 1. DNS
Point `privatregnskap.eu` A/AAAA records to the new Hetzner server IP.

### 2. SSL Certificate
```bash
sudo certbot --nginx -d privatregnskap.eu
```

### 3. Start app
```bash
sudo systemctl start regnskap
sudo journalctl -u regnskap -f  # verify startup
```

### 4. Re-authorize bank connections
Enable Banking OAuth sessions are tied to the callback URL and server.
All bank connections must be re-authorized:
- Navigate to Bankkoblinger in the app
- For each connection: initiate a new connection to the same bank
- The system will detect existing connections and update them (re-auth flow)

**IMPORTANT:** The Enable Banking callback URL in the backend config must be updated.
Check `backend/config.py` for `CALLBACK_URL` or similar — it must point to
`https://privatregnskap.eu/oauth/callback` (or wherever the callback is configured).

### 5. Re-register Passkeys
WebAuthn passkeys are bound to the RP_ID (domain). Since the domain changes
from `regnskap.noteng.no` to `privatregnskap.eu`, all existing passkeys become
invalid. Users must:
1. Log in with username/password
2. Register new passkeys for the new domain

### 6. Update Enable Banking redirect URL
In the Enable Banking dashboard/configuration, update the authorized
redirect URI to `https://privatregnskap.eu/oauth/callback`.

## Key files that need domain updates

| File | Setting | Old value | New value |
|------|---------|-----------|-----------|
| `.env` | `FRONTEND_URL` | `https://regnskap.noteng.no` | `https://privatregnskap.eu` |
| `.env` | `RP_ID` | `regnskap.noteng.no` | `privatregnskap.eu` |
| `backend/config.py` | callback URL | Check for old domain | Update to new domain |
| nginx config | `server_name` | `regnskap.noteng.no` | `privatregnskap.eu` |

## Verification checklist

- [ ] MariaDB running with encryption at rest
- [ ] App starts without errors (`journalctl -u regnskap`)
- [ ] HTTPS working (certbot)
- [ ] Can log in with password
- [ ] Can register new passkey
- [ ] Bank connections page loads (ASPSPs list)
- [ ] Can initiate new bank connection
- [ ] Budget report works
- [ ] Transaction list with filters works

## Rollback
The old server remains untouched. If migration fails, just point DNS back.
