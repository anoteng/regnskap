# TODO: Multi-Ledger (Multi-Regnskap) Implementation

## Status: Database migrert ✅, Backend og Frontend gjenstår

---

## 1. Backend - Schemas (backend/app/schemas.py)

### 1.1 Ledger Schemas
```python
class LedgerBase(BaseModel):
    name: str

class LedgerCreate(LedgerBase):
    pass

class Ledger(LedgerBase):
    id: int
    created_by: int
    created_at: datetime
    is_active: bool

class LedgerWithRole(Ledger):
    user_role: str  # OWNER, MEMBER, VIEWER

class LedgerMemberBase(BaseModel):
    user_id: int
    role: str  # OWNER, MEMBER, VIEWER

class LedgerMemberCreate(BaseModel):
    email: str  # Invite by email
    role: str

class LedgerMember(LedgerMemberBase):
    ledger_id: int
    joined_at: datetime
    user: User  # Include user details
```

### 1.2 Oppdater User schema
- Legg til `last_active_ledger_id: Optional[int]`

---

## 2. Backend - Auth middleware (backend/app/auth.py)

### 2.1 Ledger context dependency
```python
async def get_current_ledger(
    ledger_id: Optional[int] = Header(None, alias="X-Ledger-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Ledger:
    """
    Get current ledger from header or user's last_active_ledger_id.
    Verify user has access to the ledger.
    """
    # If no ledger_id in header, use user's last active
    # Verify user is member of ledger
    # Return ledger object
    pass

async def require_ledger_role(
    required_role: LedgerRole,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """
    Verify user has required role in current ledger.
    OWNER > MEMBER > VIEWER
    """
    pass
```

### 2.2 Helper functions
- `get_user_ledgers(user_id)` - Get all ledgers user has access to
- `get_user_role_in_ledger(user_id, ledger_id)` - Get user's role
- `user_can_write(user_id, ledger_id)` - Check if user can create/edit
- `user_can_read(user_id, ledger_id)` - Check if user can view

---

## 3. Backend - Ledger Routes (backend/app/routes/ledgers.py)

### 3.1 Create new file: `backend/app/routes/ledgers.py`

#### Endpoints:
```python
GET    /api/ledgers/                    # List user's ledgers
POST   /api/ledgers/                    # Create new ledger
GET    /api/ledgers/{ledger_id}         # Get ledger details
PUT    /api/ledgers/{ledger_id}         # Update ledger (name, etc)
DELETE /api/ledgers/{ledger_id}         # Delete ledger (owner only)
POST   /api/ledgers/{ledger_id}/switch  # Switch to this ledger (update last_active)

GET    /api/ledgers/{ledger_id}/members         # List members
POST   /api/ledgers/{ledger_id}/members         # Invite member (by email)
PUT    /api/ledgers/{ledger_id}/members/{user_id} # Update member role
DELETE /api/ledgers/{ledger_id}/members/{user_id} # Remove member

POST   /api/ledgers/{ledger_id}/leave   # Leave ledger (if not owner)
```

### 3.2 Register router in `backend/main.py`
```python
from backend.app.routes import ..., ledgers
app.include_router(ledgers.router, prefix="/api")
```

---

## 4. Backend - Oppdater eksisterende routes

### 4.1 For hver route-fil, endre:

**Fra:**
```python
def get_something(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    items = db.query(Model).filter(Model.user_id == current_user.id).all()
```

**Til:**
```python
def get_something(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    items = db.query(Model).filter(Model.ledger_id == current_ledger.id).all()
```

**OG ved create:**
```python
def create_something(
    data: SomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    db_item = Model(
        ledger_id=current_ledger.id,
        created_by=current_user.id,  # For audit trail
        **data.model_dump()
    )
```

### 4.2 Filer som må oppdateres:
- [ ] `backend/app/routes/transactions.py`
- [ ] `backend/app/routes/bank_accounts.py`
- [ ] `backend/app/routes/budgets.py`
- [ ] `backend/app/routes/categories.py`
- [ ] `backend/app/routes/csv_mappings.py`
- [ ] `backend/app/routes/reports.py`

---

## 5. Frontend - API client (frontend/static/js/api.js)

### 5.1 Legg til ledger context
```javascript
class API {
    constructor() {
        this.token = localStorage.getItem('token');
        this.currentLedgerId = localStorage.getItem('currentLedgerId');
    }

    setCurrentLedger(ledgerId) {
        this.currentLedgerId = ledgerId;
        localStorage.setItem('currentLedgerId', ledgerId);
    }

    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        // Add ledger context to all requests
        if (this.currentLedgerId) {
            headers['X-Ledger-ID'] = this.currentLedgerId;
        }

        // ... rest of request logic
    }

    // New ledger methods
    async getLedgers() { ... }
    async createLedger(data) { ... }
    async switchLedger(ledgerId) { ... }
    async getLedgerMembers(ledgerId) { ... }
    async inviteMember(ledgerId, email, role) { ... }
    async removeMember(ledgerId, userId) { ... }
}
```

---

## 6. Frontend - Ledger selector (frontend/index.html + js)

### 6.1 Oppdater navbar HTML
```html
<div class="navbar-user">
    <select id="ledger-selector" class="ledger-dropdown">
        <!-- Populated dynamically -->
    </select>
    <span id="user-name"></span>
    <button id="logout-btn" class="btn btn-secondary">Logg ut</button>
</div>
```

### 6.2 Ny fil: `frontend/static/js/ledgers.js`
```javascript
class LedgerManager {
    async init() {
        await this.loadLedgers();
        this.setupLedgerSelector();
    }

    async loadLedgers() {
        this.ledgers = await api.getLedgers();
        if (this.ledgers.length === 0) {
            // Show onboarding: create first ledger
            this.showOnboarding();
        }
    }

    setupLedgerSelector() {
        const selector = document.getElementById('ledger-selector');
        // Populate dropdown
        // Handle change event
        // Switch ledger on selection
    }

    async switchLedger(ledgerId) {
        await api.switchLedger(ledgerId);
        api.setCurrentLedger(ledgerId);
        window.location.reload(); // Reload to get new ledger data
    }

    showOnboarding() {
        // Show modal: "Opprett ditt første regnskap"
        // Input: Ledger name (default: "{user.full_name}s regnskap")
        // Button: Create
    }

    showLedgerSettings() {
        // Show modal with:
        // - Ledger name (editable if owner)
        // - Members list (with roles)
        // - Invite member button (if owner/admin)
        // - Leave/Delete ledger buttons
    }
}
```

### 6.3 Oppdater main.js
```javascript
import ledgerManager from './ledgers.js';

class App {
    async init() {
        if (auth.isAuthenticated()) {
            await ledgerManager.init();

            // If no ledger selected yet, don't show main view
            if (!api.currentLedgerId) {
                return; // Onboarding will handle it
            }

            this.showMainView();
        } else {
            this.showAuthView();
        }
    }
}
```

---

## 7. Frontend - Ledger management UI

### 7.1 Legg til menyvalg i navbar (eller settings-ikon)
```html
<li><a href="#" data-view="ledger-settings">Regnskapsinnstillinger</a></li>
```

### 7.2 Ny view i HTML
```html
<div id="ledger-settings-view" class="content-view" style="display: none;">
    <h1>Regnskapsinnstillinger</h1>

    <div class="card">
        <h2>Regnskapsdetaljer</h2>
        <div class="form-group">
            <label>Navn</label>
            <input type="text" id="ledger-name" value="Mitt regnskap">
        </div>
        <button id="save-ledger-btn" class="btn btn-primary">Lagre</button>
    </div>

    <div class="card">
        <h2>Medlemmer</h2>
        <table class="table" id="members-table">
            <!-- Populated dynamically -->
        </table>
        <button id="invite-member-btn" class="btn btn-primary">Inviter medlem</button>
    </div>

    <div class="card">
        <h2>Farlig sone</h2>
        <button id="leave-ledger-btn" class="btn btn-danger">Forlat regnskap</button>
        <button id="delete-ledger-btn" class="btn btn-danger">Slett regnskap</button>
    </div>
</div>
```

---

## 8. Testing

### 8.1 Test scenarios
- [ ] Ny bruker registrerer seg → Må opprette første regnskap
- [ ] Bruker oppretter nytt regnskap
- [ ] Bruker bytter mellom regnskap
- [ ] Owner inviterer medlem via email
- [ ] Medlem logger inn og ser delt regnskap
- [ ] Viewer kan bare se, ikke redigere
- [ ] Member kan opprette transaksjoner
- [ ] Owner kan slette regnskap
- [ ] Bruker forlater regnskap (ikke owner)
- [ ] Alle transaksjoner/data er isolert per regnskap

---

## 9. Future: Monetization support (notater for senere)

### 9.1 Database endringer (fremtidig)
```sql
-- Add to ledgers table:
ALTER TABLE ledgers ADD COLUMN subscription_tier ENUM('FREE', 'BASIC', 'PRO') DEFAULT 'FREE';
ALTER TABLE ledgers ADD COLUMN subscription_expires_at TIMESTAMP NULL;
ALTER TABLE ledgers ADD COLUMN max_transactions INT DEFAULT 1000;  -- Limit for FREE tier

-- Or on users table if per-user billing:
ALTER TABLE users ADD COLUMN subscription_tier ENUM('FREE', 'BASIC', 'PRO') DEFAULT 'FREE';
ALTER TABLE users ADD COLUMN max_ledgers INT DEFAULT 1;  -- FREE users = 1 ledger
```

### 9.2 Business logic
- FREE tier: 1 regnskap, max 1000 transaksjoner, 1 medlem
- BASIC tier: 3 regnskap, ubegrenset transaksjoner, 3 medlemmer per regnskap
- PRO tier: Ubegrenset alt

### 9.3 Admin interface (fremtidig)
- `/admin` route (kun for superuser/admin rolle)
- Liste over alle brukere og deres regnskap
- Manuell upgrade/downgrade av subscription
- Statistikk og metrics

---

## Prioritert rekkefølge for implementering:

1. **Backend auth middleware** (get_current_ledger) - viktigst!
2. **Backend ledger schemas**
3. **Backend ledger routes** (GET/POST /api/ledgers/)
4. **Oppdater eksisterende routes** (en og en)
5. **Frontend API client** (ledger context)
6. **Frontend onboarding** (opprett første regnskap)
7. **Frontend ledger selector**
8. **Frontend ledger settings/members**

---

## Estimat: 3-4 timer totalt arbeid

**Backend:** ~2 timer
**Frontend:** ~1.5 timer
**Testing:** ~30 min
