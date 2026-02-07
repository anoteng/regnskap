# Brukeradministrasjon

## Oversikt

Brukeradmin-modulen gir administratorer mulighet til å administrere brukere, abonnementer og tilgang til systemet.

## Funksjoner

### 🔐 Admin-tilgang
- Kun brukere med `is_admin = TRUE` har tilgang til admin-panelet
- Admin-menyvalget vises automatisk for admin-brukere

### 👥 Brukeradministrasjon
- **Søk og filtrer** brukere etter navn/e-post
- **Vis detaljer** om hver bruker:
  - Grunnleggende info (navn, e-post, status)
  - Antall regnskap
  - Nåværende abonnement
  - Registreringsdato
- **Rediger brukere**:
  - Endre navn og e-post
  - Aktivere/deaktivere brukere
  - Gjøre brukere til admin
  - Sette nytt passord

### 💰 Abonnementssystem

#### Tre nivåer:
1. **FREE (Gratis)** - 0 kr/mnd
   - Ubegrenset regnskap
   - Manuell postering
   - Grunnleggende rapporter

2. **BASIC** - 49 kr/mnd
   - Alt i Gratis
   - CSV-import
   - Vedleggshåndtering
   - Avanserte rapporter
   - Multi-bruker

3. **AI** - 99 kr/mnd (fremtidig)
   - Alt i Basic
   - AI-forslag til postering
   - Automatisk kvitteringstolking
   - Smart kategorisering
   - Prediktiv analyse

#### Fleksibel prissetting:
- **Rabatt (0-100%)** - Gi rabatt på abonnement
  - Sett til 100% for gratis tilgang
- **Spesialpris** - Overstyr standard månedspris
- **Gratis for alltid** - Permanent gratis tilgang
- **Utløpsdato** - Sett når abonnement utløper
  - Blank = ingen utløp
- **Admin-notater** - Legg til interne notater

### 📊 Statistikk
Dashboard viser:
- Totale brukere
- Aktive brukere
- Totale regnskap
- Aktive abonnementer
- Fordeling per abonnementsnivå

## Installasjon

### 1. Kjør database-migrering

```bash
psql -U your_user -d your_database -f database/migrations/002_admin_and_subscriptions.sql
```

### 2. Gjør din bruker til admin

```sql
UPDATE users SET is_admin = TRUE WHERE email = 'din-email@example.com';
```

### 3. Restart backend

```bash
# Hvis du bruker systemd:
sudo systemctl restart regnskap

# Eller direkte:
uvicorn backend.main:app --reload
```

## Bruk

### Tilgang til admin-panel
1. Logg inn som admin-bruker
2. Klikk på **🔐 Admin** i navigasjonsmenyen
3. Du får tilgang til:
   - Statistikk dashboard
   - Brukerliste
   - Redigeringsfunksjoner

### Administrere en bruker

1. **Søk etter bruker** i søkefeltet
2. **Klikk "Rediger"** på ønsket bruker
3. **Endre detaljer**:
   - Oppdater navn/e-post
   - Aktiver/deaktiver bruker
   - Gjør til admin
4. **Administrer abonnement**:
   - Velg abonnementsplan
   - Sett utløpsdato (valgfritt)
   - Gi rabatt eller spesialpris
   - Merk som "Gratis for alltid" om ønsket
5. **Sett nytt passord** (valgfritt)
6. **Klikk "Lagre endringer"**

### Gi gratis tilgang

Det finnes tre måter:

**1. 100% rabatt:**
```
Abonnementsplan: Basic (eller AI)
Rabatt: 100%
```

**2. Gratis for alltid:**
```
Abonnementsplan: Basic (eller AI)
✓ Gratis for alltid
```

**3. Spesialpris 0 kr:**
```
Abonnementsplan: Basic (eller AI)
Spesialpris: 0
```

### Eksempler

**Familie/venner (gratis):**
```
Plan: AI
Rabatt: 100%
✓ Gratis for alltid
Admin-notater: "Familie - gratis tilgang"
```

**Prøveperiode (30 dager):**
```
Plan: AI
Utløpsdato: [30 dager frem i tid]
Rabatt: 100%
Admin-notater: "30-dagers prøveperiode"
```

**Early adopter-rabatt:**
```
Plan: AI
Rabatt: 50%
✓ Gratis for alltid
Admin-notater: "Early adopter - 50% rabatt permanent"
```

**Spesialpris for student:**
```
Plan: Basic
Spesialpris: 25
Utløpsdato: [1 år frem]
Admin-notater: "Studentrabatt - gyldig til [dato]"
```

## API Endpoints

### Admin-tilgang kreves for alle

**Statistikk:**
- `GET /api/admin/stats` - Hent admin-statistikk

**Brukere:**
- `GET /api/admin/users` - Liste brukere (med søk/filter)
- `GET /api/admin/users/{id}` - Hent brukerdetaljer
- `PATCH /api/admin/users/{id}` - Oppdater bruker
- `POST /api/admin/users/{id}/password` - Sett passord

**Abonnementer:**
- `GET /api/admin/subscription-plans` - Liste planer
- `POST /api/admin/users/{id}/subscription` - Opprett/oppdater abonnement
- `DELETE /api/admin/users/{id}/subscription` - Kanseller abonnement

## Database-struktur

### users (oppdatert)
```sql
+ is_admin BOOLEAN DEFAULT FALSE
```

### subscription_plans
```sql
id, name, tier, description, price_monthly, features, is_active
```

### user_subscriptions
```sql
id, user_id, plan_id, status, started_at, expires_at, cancelled_at,
discount_percentage, custom_price, is_free_forever, admin_notes
```

## Fremtidige funksjoner

- **Betalingsintegrasjon** (Stripe/Vipps)
- **Automatisk fakturering**
- **AI-funksjoner** for AI-tier
- **Bruksstatistikk per bruker**
- **E-postvarsler** ved utløp
- **Selvbetjeningsportal** for brukere

## Sikkerhet

- Admin-endepunkter krever `is_admin = TRUE`
- Passord hashet med bcrypt
- Ingen sensitive data i logger
- Admin-handlinger kan auditlogges (fremtidig)
