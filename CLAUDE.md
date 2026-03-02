# Project Instructions for Claude

## Important System Constraints

- **NO SUDO COMMANDS**: You do not have sudo permissions. Never attempt to run `sudo systemctl restart backend` or any other sudo commands.
- **Backend restart**: Always ask the user to restart the backend manually when changes are made to Python files
- **MySQL password**: The password in .env is URL-encoded, so remember to decode it when using it in shell commands

## Project Context

This is a Norwegian accounting application called "Regnskap" (regnskap = accounting in Norwegian).

### Tech Stack
- **Backend**: FastAPI + MySQL (MariaDB)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks)
- **Database**: MySQL/MariaDB
- **Authentication**: JWT tokens + WebAuthn/Passkeys
- **Bank Integration**: Enable Banking API (PSD2) with OAuth 2.0 + mTLS

### Project Structure
```
/home/andreas/regnskap/
├── backend/
│   ├── app/
│   │   ├── routes/          # API endpoints
│   │   ├── bank_integration/ # Bank sync service
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   └── auth.py          # Authentication
│   └── main.py
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── *.html
├── database/
│   └── migrations/
└── certificates/            # Enable Banking mTLS certificates
```

## Current Work: Bank Integration (Enable Banking)

### Architecture
- Provider abstraction pattern for bank integrations
- Multi-account support: One OAuth session can authorize multiple bank accounts
- Each external account must be explicitly mapped to an internal bank account
- Transactions imported as DRAFT status for user review

### Key Implementation Details

1. **Account Selection Flow**:
   - User initiates OAuth → redirected to bank
   - Bank redirects back to `/oauth/callback`
   - Callback stores account data in `oauth_state` (30 min expiry)
   - User redirected to `bank-connection-select.html`
   - User selects which external account maps to which internal bank account
   - Each selection creates a separate `BankConnection` record

2. **Enable Banking Specifics**:
   - Uses non-standard OAuth with JWT authentication
   - Requires mTLS (client certificates stored in `/certificates/`)
   - Account IDs are UUIDs that **change on each OAuth session**
   - Credit cards may have shorter historical data limits

3. **Transaction Sync**:
   - Fetches from bank via provider API
   - Stores in `bank_transactions` table
   - Deduplicates using MD5 hash (date|amount|desc|ref)
   - Imports new ones as DRAFT transactions with `source='BANK_SYNC'`
   - User reviews in posting queue and adds counter-entries

## Common Commands

### Database Operations
```bash
# Connect to MySQL (password is URL-encoded in .env)
mysql -u regnskap -p regnskap

# Run migration
mysql -u regnskap -p regnskap < database/migrations/XXX_name.sql
```

### Service Management
```bash
# Ask user to run these - you don't have sudo:
systemctl restart backend
systemctl restart frontend
systemctl status backend
```

## Known Issues & Solutions

1. **Enable Banking Account ID Changes**:
   - Account IDs are volatile (change per OAuth session)
   - Always update connection with latest account_id from oauth_state

2. **Enable Banking Transaction History Access Limitations** (CRITICAL):
   - **Within ~1 hour after OAuth authorization**: Full transaction history available (potentially years)
   - **After ~1 hour**: ONLY last 90 days accessible
   - Attempting to fetch older transactions after 1 hour causes ASPSP_ERROR (400 Bad Request)
   - **Solution**:
     - Initial sync: Use `date_from` parameter (e.g., '2026-01-01') without strategy parameter
     - Subsequent syncs: Use `date_from` with `last_sync_at` (capped at 89 days ago)
     - Never request transactions older than 90 days after the initial sync window
   - **Implementation** (from Enable Banking official examples):
     ```python
     # Initial sync with date limit
     params = {'date_from': '2026-01-01'}  # No strategy parameter!

     # Ongoing syncs - limit to last 90 days
     from_date = max(
         bank_connection.last_sync_at,
         datetime.now(timezone.utc) - timedelta(days=89)
     )
     params = {'date_from': from_date.date().isoformat(), 'date_to': date.today().isoformat()}
     ```
   - Source: Enable Banking FAQ + official Python example code

3. **Enable Banking Transaction Fetching**:
   - Use `date_from` parameter (required) and optionally `date_to`
   - Do NOT use `strategy=longest` - it causes ASPSP_ERROR
   - Must handle `continuation_key` for pagination - keep calling until no key returned
   - May receive empty transaction list WITH continuation_key - must continue calling

4. **Credit Card vs Bank Account Differences**:
   - Both follow same time limitations (1 hour initial window, then 90 days)
   - Credit cards may have less historical data available from ASPSP
   - Amount signs must be inverted for LIABILITY accounts (credit cards)

5. **Timezone Issues**:
   - Always use `datetime.utcnow()` for consistency
   - Database stores UTC, converts on display

## Development Workflow

1. Make changes to Python files
2. **Ask user to restart backend**
3. Test in browser
4. Check logs: `journalctl -u backend -f` (ask user if needed)

## Testing Enable Banking

- Sandbox environment is available
- Test bank: DNB sandbox
- Certificates required for mTLS
- User has working sandbox credentials configured

## Migration to Hetzner (planned)

Migration scripts are in `/home/andreas/regnskap/migration/`:
- `export.sh` - Run on old server to create export bundle
- `setup-new-server.sh` - Run on new Hetzner server to set everything up
- `MIGRATION_GUIDE.md` - Full step-by-step guide

### Key migration notes
- **New domain**: `privatregnskap.eu` (was `regnskap.noteng.no`)
- **Callback URL** is built dynamically from `FRONTEND_URL` in `.env` — no hardcoded URLs
- **Enable Banking**: All bank connections must be re-authorized after migration (new OAuth sessions)
- **WebAuthn/Passkeys**: RP_ID changes with domain, so all passkeys must be re-registered
- **MariaDB encryption at rest** will be enabled on the new server
- **Enable Banking mTLS certificates** in `/certificates/` must be copied with correct permissions (private.key chmod 600)

## Language & Communication

- User is Norwegian, comfortable with both Norwegian and English
- Code comments and variable names are in English
- User-facing text (UI, error messages) is in Norwegian
- Documentation can be in English
