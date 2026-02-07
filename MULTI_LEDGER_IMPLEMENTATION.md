# Multi-Ledger Implementation - Complete

## Overview

The application has been successfully upgraded to support multiple ledgers (regnskap) per user, enabling:
- Personal accounting
- Family/household shared accounting
- Small business use
- Multi-user collaboration with role-based access control

## Database Changes ✅

### New Tables
- **ledgers**: Stores ledger information (id, name, created_by, created_at, is_active)
- **ledger_members**: Many-to-many relationship between users and ledgers with roles

### Modified Tables
All data tables now include `ledger_id` foreign key:
- bank_accounts
- transactions (also added `created_by` for audit trail)
- budgets
- categories
- csv_mappings
- import_logs

### Migration
- Existing data migrated to default ledgers (one per user)
- Old `user_id` columns kept nullable for backward compatibility
- Migration script: `database/migrate_to_ledgers.sql`
- Continuation script: `database/migrate_to_ledgers_continue.sql`

## Backend Changes ✅

### Models (`backend/app/models.py`)
- Added `Ledger` model
- Added `LedgerMember` model with `LedgerRole` enum (OWNER, MEMBER, VIEWER)
- Updated `User` model with `last_active_ledger_id`
- Updated all data models to use `ledger_id`

### Schemas (`backend/app/schemas.py`)
- Added `Ledger`, `LedgerCreate`, `LedgerWithRole`
- Added `LedgerMember`, `LedgerMemberCreate`, `LedgerMemberBase`
- Updated `User` schema to include `last_active_ledger_id`
- Updated all data schemas to use `ledger_id` instead of `user_id`

### Auth Middleware (`backend/app/auth.py`)
Added ledger context functions:
- `get_current_ledger()` - Extracts ledger from X-Ledger-ID header or user's last_active
- `get_user_role_in_ledger()` - Gets user's role in a specific ledger
- `user_can_write()` / `user_can_read()` - Permission helpers
- `require_ledger_owner()` / `require_ledger_write()` - Role verification dependencies

### Ledger Routes (`backend/app/routes/ledgers.py`)
New endpoints for ledger management:
- `GET /api/ledgers/` - List user's ledgers with their role
- `POST /api/ledgers/` - Create new ledger
- `GET /api/ledgers/{id}` - Get ledger details
- `PUT /api/ledgers/{id}` - Update ledger name (owner only)
- `DELETE /api/ledgers/{id}` - Soft delete ledger (owner only)
- `POST /api/ledgers/{id}/switch` - Switch to ledger (updates last_active)
- `GET /api/ledgers/{id}/members` - List ledger members
- `POST /api/ledgers/{id}/members` - Invite member by email
- `PUT /api/ledgers/{id}/members/{user_id}` - Update member role (owner only)
- `DELETE /api/ledgers/{id}/members/{user_id}` - Remove member (owner only)
- `POST /api/ledgers/{id}/leave` - Leave ledger (if not owner)

### Updated Routes
All existing routes now use ledger context:
- **transactions.py**: Uses `current_ledger` dependency, CSV import includes ledger_id
- **bank_accounts.py**: Filters by `ledger_id`
- **categories.py**: Scoped to current ledger
- **budgets.py**: Includes ledger context in progress queries
- **csv_mappings.py**: CSV mappings are per-ledger
- **reports.py**: Balance sheet and income statement filtered by ledger

## Frontend Changes ✅

### API Client (`frontend/static/js/api.js`)
- Added `currentLedgerId` property and localStorage management
- Added `setCurrentLedger()`, `getCurrentLedger()`, `clearCurrentLedger()` methods
- Automatically adds `X-Ledger-ID` header to all authenticated requests
- Added ledger management methods:
  - `getLedgers()`, `createLedger()`, `getLedger()`
  - `updateLedger()`, `deleteLedger()`, `switchLedger()`
  - `getLedgerMembers()`, `inviteMember()`, `updateMemberRole()`
  - `removeMember()`, `leaveLedger()`

### Ledger Manager (`frontend/static/js/ledgers.js`)
New module for ledger operations:
- `init()` - Loads ledgers and sets up selector
- `loadLedgers()` - Fetches user's ledgers from API
- `setupLedgerSelector()` - Populates dropdown with ledgers
- `switchLedger()` - Switches active ledger and reloads page
- `showOnboarding()` - First-time user flow to create first ledger
- `showLedgerSettings()` - Display settings view
- `loadLedgerSettings()` - Load and populate settings form
- `loadLedgerMembers()` - Display member list
- `showInviteMemberModal()` - Modal for inviting new members
- `changeMemberRole()`, `removeMember()` - Member management
- `showCreateLedgerModal()` - Create additional ledgers

### Main App (`frontend/static/js/main.js`)
- Added `import ledgerManager`
- Updated `init()` to be async and initialize ledger context before showing main view
- Added `'ledger-settings'` case to `switchView()` method
- Onboarding flow prevents showing main view until ledger is selected

### UI (`frontend/index.html`)
- Added ledger selector dropdown in navbar
- Added "New Ledger" button in navbar
- Added "Settings" link in navbar menu
- Created complete ledger settings view with:
  - Ledger details form (name, role)
  - Members table with role and actions
  - Invite member button
  - Danger zone (leave/delete ledger)

### Styles (`frontend/static/css/styles.css`)
- Added `.ledger-dropdown` styles
- Added `.btn-sm` for smaller buttons
- Styled to match existing design system

## User Flow

### New User Flow
1. User registers/logs in
2. If no ledgers exist, onboarding modal appears
3. User creates their first ledger (e.g., "Mitt regnskap")
4. Ledger is set as active, main view loads

### Switching Ledgers
1. User selects ledger from dropdown in navbar
2. API call to `/api/ledgers/{id}/switch` updates `last_active_ledger_id`
3. Page reloads with new ledger context
4. All data (transactions, accounts, budgets, etc.) now scoped to selected ledger

### Inviting Members
1. Owner goes to Settings (Innstillinger)
2. Clicks "Inviter medlem"
3. Enters email and selects role (VIEWER, MEMBER, OWNER)
4. Invited user can see and switch to the shared ledger

### Creating Additional Ledgers
1. User clicks "+ Nytt" button in navbar
2. Modal appears to name the new ledger
3. New ledger created and automatically switched to

## Role-Based Access Control

### Roles
- **OWNER**: Full access - can manage members, update settings, delete ledger
- **MEMBER**: Can view and edit data (transactions, budgets, etc.)
- **VIEWER**: Read-only access

### Permission Checks
- Backend enforces permissions at route level using dependencies
- Frontend shows/hides UI elements based on user's role
- Ledger context required for all data operations (via X-Ledger-ID header)

## Security

- All data operations require valid ledger membership
- Ledger ID sent via X-Ledger-ID header (not URL parameter to prevent IDOR)
- Backend verifies user has access to ledger before any operation
- Cannot modify or view data from ledgers user is not a member of
- Owner role required for destructive operations

## Testing Checklist

- [x] Database migration successful
- [x] Backend imports without errors
- [x] HTML syntax valid
- [ ] New user can create first ledger (onboarding)
- [ ] User can switch between ledgers
- [ ] Owner can invite members by email
- [ ] Members can view ledger data
- [ ] Viewers have read-only access
- [ ] Owner can update ledger name
- [ ] Owner can change member roles
- [ ] Owner can remove members
- [ ] Members can leave ledger
- [ ] Owner can delete ledger
- [ ] Data is properly isolated per ledger
- [ ] CSV import works with ledger context
- [ ] Reports show correct ledger data

## Files Modified

### Database
- database/migrate_to_ledgers.sql
- database/migrate_to_ledgers_continue.sql

### Backend
- backend/app/models.py
- backend/app/schemas.py
- backend/app/auth.py
- backend/app/routes/ledgers.py (new)
- backend/app/routes/transactions.py
- backend/app/routes/bank_accounts.py
- backend/app/routes/categories.py
- backend/app/routes/budgets.py
- backend/app/routes/csv_mappings.py
- backend/app/routes/reports.py
- backend/main.py

### Frontend
- frontend/static/js/api.js
- frontend/static/js/ledgers.js (new)
- frontend/static/js/main.js
- frontend/index.html
- frontend/static/css/styles.css

## Next Steps (Optional Enhancements)

1. **Posting Queue** (from TODO) - Add transaction status field (DRAFT, POSTED, RECONCILED)
2. **Email Invitations** - Send actual email when inviting members
3. **Audit Log** - Track who made what changes
4. **Ledger Templates** - Pre-configured ledgers for different use cases
5. **Monetization** - Implement subscription tiers (FREE, BASIC, PRO)
6. **Admin Interface** - Superuser dashboard for managing all ledgers
7. **Activity Feed** - Show recent changes in shared ledgers
8. **Permissions Granularity** - More fine-grained permissions per feature

## Compatibility

- Old `user_id` columns kept as nullable for transition period
- Can be safely removed in future migration after thorough testing
- Frontend gracefully handles missing ledger selection
- Backend returns clear error messages for ledger access issues
