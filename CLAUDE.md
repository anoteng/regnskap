# Project Instructions for Claude

## Important System Constraints

- **Sudo**: Passwordless sudo is configured for `systemctl restart/status` and `journalctl -u` on services: `regnskap`, `ringlog`, `exerlog`. Only these exact forms work — no extra flags.
- **Backend restart**: Run `sudo systemctl restart regnskap` directly after Python changes
- **MySQL password**: The password in .env is URL-encoded, so remember to decode it when using it in shell commands

## Project Context

This is a Norwegian personal accounting application called **Privatregnskap.eu**.

### Tech Stack
- **Backend**: FastAPI + MySQL (MariaDB 11.8)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks, SPA-style with content-view divs)
- **Database**: MariaDB
- **Authentication**: JWT tokens + WebAuthn/Passkeys
- **Bank Integration**: Enable Banking API (PSD2) with OAuth 2.0 + mTLS
- **Hosting**: Hetzner (IPv6 only, behind Cloudflare proxy)
- **Domain**: privatregnskap.eu

### Project Structure
```
/home/andreas/regnskap/
├── backend/
│   ├── app/
│   │   ├── routes/            # API endpoints
│   │   ├── bank_integration/  # Bank sync service (Enable Banking)
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas
│   │   └── auth.py            # Authentication
│   └── main.py
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   ├── index.html             # Main SPA entry point
│   └── bank-connection-select.html  # OAuth callback account selector
├── database/
│   └── schema.sql             # Full database schema (for fresh installs)
└── certificates/              # Enable Banking mTLS certificates
```

### Frontend Architecture
- SPA using `content-view` divs toggled by `switchView()` in `main.js`
- Navigation via hamburger menu (always-visible toggle, absolute positioned dropdown)
- Bank connections integrated as SPA view (not separate page)
- OAuth callbacks route back to `/?view=bank-connections&success=true`

### Receipt Storage
- Receipts are stored as BLOBs in the database (`file_data LONGBLOB` column)
- SQLAlchemy `deferred()` column loading prevents BLOBs from being loaded on listing queries
- No filesystem storage — backup is just a database dump

## Bank Integration (Enable Banking)

### Architecture
- Provider abstraction pattern for bank integrations
- Multi-account support: One OAuth session can authorize multiple bank accounts
- Each external account must be explicitly mapped to an internal bank account
- Transactions imported as DRAFT status for user review

### Account Selection Flow
1. User initiates OAuth → redirected to bank
2. Bank redirects back to `/oauth/callback`
3. Callback stores account data in `oauth_state` (30 min expiry)
4. User redirected to `bank-connection-select.html`
5. User selects which external account maps to which internal bank account
6. Each selection creates a separate `BankConnection` record

### Enable Banking Specifics
- Uses non-standard OAuth with JWT authentication
- Requires mTLS (client certificates stored in `/certificates/`)
- Account IDs are UUIDs that **change on each OAuth session**
- Credit cards may have shorter historical data limits

### Transaction Sync
- Fetches from bank via provider API
- Stores in `bank_transactions` table
- Deduplicates using MD5 hash (date|amount|desc|ref)
- Imports new ones as DRAFT transactions with `source='BANK_SYNC'`
- User reviews in posting queue and adds counter-entries

### Enable Banking Transaction History (CRITICAL)
- **Within ~1 hour after OAuth authorization**: Full transaction history available (potentially years)
- **After ~1 hour**: ONLY last 90 days accessible
- Attempting to fetch older transactions after 1 hour causes ASPSP_ERROR (400 Bad Request)
- **Implementation**:
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

### Enable Banking Transaction Fetching
- Use `date_from` parameter (required) and optionally `date_to`
- Do NOT use `strategy=longest` - it causes ASPSP_ERROR
- Must handle `continuation_key` for pagination - keep calling until no key returned
- May receive empty transaction list WITH continuation_key - must continue calling

### Credit Card vs Bank Account
- Both follow same time limitations (1 hour initial window, then 90 days)
- Credit cards may have less historical data available from ASPSP
- Amount signs must be inverted for LIABILITY accounts (credit cards)

## Common Commands

### Database Operations
```bash
# Connect to MySQL (password is URL-encoded in .env)
mysql -u regnskap -p regnskap
```

### Service Management
```bash
# These work directly (passwordless sudo configured):
sudo systemctl restart regnskap
sudo systemctl restart ringlog
sudo systemctl restart exerlog
sudo journalctl -u regnskap
sudo journalctl -u regnskap -f
# Same pattern for ringlog and exerlog
```

## Development Workflow

1. Make changes to Python files
2. Run `sudo systemctl restart regnskap` directly
3. Test in browser at https://privatregnskap.eu
4. Check logs with `sudo journalctl -u regnskap -f` directly

## Known Issues

1. **Enable Banking Account ID Changes**: Account IDs are volatile (change per OAuth session). Always update connection with latest account_id from oauth_state.

2. **Timezone**: Always use `datetime.utcnow()` for consistency. Database stores UTC, converts on display.

## Immediate TODO (post-migration)

### 1. Switch email from SMTP to Brevo API
- **Why**: Hetzner server is IPv6 only, SMTP relay services don't work reliably over IPv6
- **Current**: `backend/email.py` uses `smtplib.SMTP_SSL`, config in `backend/config.py` has SMTP settings
- **Target**: Use Brevo HTTP API (https://api.brevo.com/v3/smtp/email) with API key
- **Changes needed**:
  - `backend/config.py`: Replace `smtp_host/smtp_port/smtp_user/smtp_password/smtp_from` with `brevo_api_key`, `email_from`, `email_from_name`
  - `backend/email.py`: Replace smtplib with `requests.post()` to Brevo API
  - `.env` on server: Add `BREVO_API_KEY=...` (user has Brevo account)
- **Brevo API format**:
  ```python
  requests.post("https://api.brevo.com/v3/smtp/email",
      headers={"api-key": api_key, "Content-Type": "application/json"},
      json={"sender": {"name": name, "email": from_email},
            "to": [{"email": to_email}],
            "subject": subject, "htmlContent": html})
  ```

### 2. Fix passkey registration after domain change
- **Symptom**: Cannot register new passkeys on privatregnskap.eu
- **Relevant code**: `backend/app/routes/passkey.py` — `get_rp_id()`, `get_origin()`
- **Config**: `RP_ID` and `FRONTEND_URL` in `.env` must match the new domain
- **Expected .env values**:
  ```
  RP_ID=privatregnskap.eu
  RP_NAME=Privatregnskap.eu
  FRONTEND_URL=https://privatregnskap.eu
  ```
- **Note**: Old passkeys from previous domain will NOT work — they are bound to the old RP_ID. Old entries in `webauthn_credentials` table can be deleted.
- **Debug**: Check browser console for WebAuthn errors. Common issues: origin mismatch, RP_ID mismatch. The `get_origin()` function in passkey.py constructs origin from `rp_id`.

## Language & Communication

- User is Norwegian, comfortable with both Norwegian and English
- Code comments and variable names are in English
- User-facing text (UI, error messages) is in Norwegian
- Documentation can be in English
- **Do not add Co-Authored-By lines to commits**
- **Commit without GPG signing** (`git -c commit.gpgsign=false commit`)

## Planned Features

- **Monthly payment projection**: Calculate how much each person should pay into shared household account. Involves recurring bills, credit card lag (purchases one month, payment the 15th of next month), salary dates (12th and 20th).
- **Expense reduction helper**: Analyze spending patterns and suggest savings.
- **Fuzzy dedup for bank sync**: Improve duplicate detection when importing bank transactions.
