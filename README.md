# Regnskap - Personlig Bokføringssystem

En komplett web-applikasjon for personlig regnskap med dobbelt bokføring, basert på norsk standard kontoplan.

## Funksjoner

- **Dobbelt bokføring**: Korrekt regnskapsprinsipp med debet og kredit
- **Norsk standard kontoplan**: Forhåndskonfigurert med over 100 kontoer
- **Multi-ledger support**: Støtte for flere separate regnskap per bruker
- **Delt regnskap**: Inviter andre brukere til dine regnskap med roller (Owner, Member, Viewer)
- **Transaksjoner**: Manuell registrering og fleksibel CSV-import med kolonnemapping
- **Bankkontoer**: Støtte for brukskontoer, sparekontoer og kredittkort
- **Budsjett**: Lag og følg budsjetter
- **Rapporter**: Balanse og resultatregnskap
- **Kategorisering**: Fleksibel tagging av transaksjoner
- **Kvitteringer**: Upload og koble kvitteringer til transaksjoner

## Teknologi

### Backend
- Python 3.10+
- FastAPI
- SQLAlchemy
- MariaDB/MySQL
- JWT autentisering

### Frontend
- HTML5
- CSS3 (vanilla, ingen framework)
- JavaScript ES6 modules (vanilla, ingen jQuery)

## Installasjon

### Forutsetninger

- Python 3.10 eller nyere
- MariaDB 10.5+ eller MySQL 8.0+
- Node.js (valgfritt, for utvikling)

### 1. Klon repository

```bash
git clone <repository-url>
cd regnskap
```

### 2. Opprett Python virtual environment

```bash
python -m venv venv
source venv/bin/activate  # På Windows: venv\Scripts\activate
```

### 3. Installer Python-avhengigheter

```bash
pip install -r requirements.txt
```

### 4. Sett opp database

Opprett en ny database i MariaDB:

```sql
CREATE DATABASE regnskap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'regnskap_user'@'localhost' IDENTIFIED BY 'ditt_passord';
GRANT ALL PRIVILEGES ON regnskap.* TO 'regnskap_user'@'localhost';
FLUSH PRIVILEGES;
```

Importer databaseskjema:

```bash
mysql -u regnskap_user -p regnskap < database/schema.sql
```

Importer norsk kontoplan:

```bash
mysql -u regnskap_user -p regnskap < database/seed_accounts.sql
```

**For eksisterende installasjoner**: Hvis du oppgraderer fra en eldre versjon uten multi-ledger support, kjør migreringsscriptet:

```bash
mysql -u regnskap_user -p regnskap < database/migrate_to_ledgers.sql
```

### 5. Konfigurer miljøvariabler

Kopier eksempelfilen og rediger verdiene:

```bash
cp .env.example .env
```

Rediger `.env`:

```env
DATABASE_URL=mysql+pymysql://regnskap_user:ditt_passord@localhost:3306/regnskap
SECRET_KEY=generer-en-tilfeldig-sikker-nøkkel-her
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generer en sikker SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 6. Start applikasjonen

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Applikasjonen er nå tilgjengelig på: http://localhost:8000

## Bruk

### Første gangs oppsett

1. Åpne http://localhost:8000 i nettleseren
2. Klikk på "Registrer deg"
3. Opprett en brukerkonto med navn, e-post og passord
4. Logg inn med dine nye legitimasjoner
5. Opprett ditt første regnskap (f.eks. "Mitt personlige regnskap")
6. Nå er du klar til å begynne!

### Arbeide med flere regnskap

Du kan opprette og administrere flere regnskap:

- **Bytte mellom regnskap**: Bruk dropdown-menyen øverst i høyre hjørne
- **Opprette nytt regnskap**: Klikk på "+ Nytt" knappen ved siden av regnskap-velgeren
- **Administrere regnskap**: Gå til "⚙️ Innstillinger" for å endre navn, invitere medlemmer, eller slette

### Invitere andre til ditt regnskap

1. Gå til "⚙️ Innstillinger"
2. Klikk "Inviter medlem" under Medlemmer-seksjonen
3. Skriv inn e-postadressen til personen du vil invitere
4. Velg rolle:
   - **Owner**: Full tilgang (kan administrere medlemmer og slette regnskap)
   - **Member**: Kan se og redigere transaksjoner, budsjetter, etc.
   - **Viewer**: Kun lesetilgang
5. Klikk "Inviter"
6. Den inviterte personen vil nå se regnskapet i sin regnskap-velger

### Opprette bankkontoer

1. Gå til Dashboard
2. Før du kan registrere transaksjoner, må du opprette minst én bankkonto
3. Bankkontoer kobles til kontoer i kontoplanen (f.eks. konto 1201 for brukskonto)

### Kredittkort

Se [KREDITTKORT_GUIDE.md](KREDITTKORT_GUIDE.md) for detaljert guide om hvordan du håndterer kredittkort i systemet.

**Kort oppsummert**:
- Opprett bankkonto av type "Kredittkort" koblet til konto 2501
- Importer transaksjoner fra kredittkort-CSV (systemet håndterer automatisk korrekt debet/kredit)
- Registrer fakturabetaling som manuell transaksjon (debet kredittkort, kredit bankkonto)

### Registrere transaksjoner

#### Manuell transaksjon

1. Gå til "Transaksjoner"
2. Klikk "Ny transaksjon"
3. Fyll ut dato, beskrivelse og referanse
4. Legg til journal-posteringer (minimum 2):
   - Velg konto
   - Angi beløp som enten debet eller kredit
   - Sørg for at sum debet = sum kredit

**Eksempel - Lønnsutbetaling:**
```
Debet: Konto 1201 (Brukskonto) - 50 000 kr
Kredit: Konto 3101 (Fastlønn) - 50 000 kr
```

#### CSV-import

1. Gå til "Transaksjoner"
2. Klikk "Importer CSV"
3. Velg bankkonto
4. Last opp CSV-fil med følgende format:

```csv
date,description,amount,reference
2025-01-15,Lønn,50000.00,LØN-JAN
2025-01-16,Rema 1000,-856.50,VISA-1234
```

### Rapporter

#### Balanse

Viser eiendeler, gjeld og egenkapital per en gitt dato.

1. Gå til "Rapporter"
2. Velg "Balanse"
3. Velg dato
4. Klikk "Generer"

#### Resultatregnskap

Viser inntekter og kostnader for en periode.

1. Gå til "Rapporter"
2. Velg "Resultat"
3. Velg fra- og til-dato
4. Klikk "Generer"

### Budsjetter

1. Gå til "Budsjett"
2. Klikk "Nytt budsjett"
3. Velg konto (f.eks. "6301 - Dagligvarer")
4. Angi budsjettbeløp og periode
5. Følg fremgang i real-time

## Prosjektstruktur

```
regnskap/
├── backend/
│   ├── app/
│   │   ├── models.py          # SQLAlchemy modeller
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── auth.py            # Autentisering og tilgangskontroll
│   │   └── routes/            # API endpoints
│   │       ├── auth.py
│   │       ├── ledgers.py     # Ledger management
│   │       ├── accounts.py
│   │       ├── bank_accounts.py
│   │       ├── transactions.py
│   │       ├── categories.py
│   │       ├── budgets.py
│   │       ├── csv_mappings.py
│   │       └── reports.py
│   ├── config.py              # Konfigurasjon
│   ├── database.py            # Database tilkobling
│   └── main.py                # FastAPI app
├── database/
│   ├── schema.sql             # Database skjema
│   ├── seed_accounts.sql      # Norsk kontoplan
│   └── migrate_to_ledgers.sql # Multi-ledger migrering
├── frontend/
│   ├── index.html             # Hovedside
│   └── static/
│       ├── css/
│       │   └── styles.css     # Styling
│       └── js/
│           ├── api.js         # API klient
│           ├── auth.js        # Autentisering
│           ├── ledgers.js     # Ledger management
│           ├── main.js        # Hovedapp
│           ├── transactions.js # Transaksjoner
│           ├── bank-accounts.js
│           ├── reports.js     # Rapporter
│           └── utils.js       # Hjelpefunksjoner
├── .env                       # Miljøvariabler (ikke commit)
├── .env.example               # Eksempel miljøvariabler
├── requirements.txt           # Python avhengigheter
├── README.md                  # Denne filen
├── TODO_MULTI_LEDGER.md       # Multi-ledger implementeringsplan
└── MULTI_LEDGER_IMPLEMENTATION.md  # Komplett implementeringsdokumentasjon
```

## API Dokumentasjon

FastAPI genererer automatisk interaktiv API-dokumentasjon:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Utvikling

### Kjør i utviklingsmodus

```bash
uvicorn backend.main:app --reload
```

### Database migrasjoner

Når du gjør endringer i databaseskjemaet:

1. Oppdater `database/schema.sql`
2. Kjør migrering manuelt eller gjenopprett databasen

### Logging

Applikasjonen logger til konsollen. For produksjon, konfigurer logging til fil.

## Produksjon

### Sikkerhetsanbefalinger

1. Bruk en sterk SECRET_KEY
2. Kjør bak en reverse proxy (nginx/Apache)
3. Aktiver HTTPS
4. Konfigurer CORS strengt
5. Bruk en dedikert database-bruker med minimale rettigheter
6. Aktiver database backups

### Deployment med systemd

Opprett `/etc/systemd/system/regnskap.service`:

```ini
[Unit]
Description=Regnskap FastAPI App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/regnskap
Environment="PATH=/path/to/regnskap/venv/bin"
ExecStart=/path/to/regnskap/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

Start service:

```bash
sudo systemctl enable regnskap
sudo systemctl start regnskap
```

### Nginx konfigurasjon

```nginx
server {
    listen 80;
    server_name regnskap.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Feilsøking

### Database connection error

- Sjekk at MariaDB kjører: `sudo systemctl status mariadb`
- Verifiser DATABASE_URL i `.env`
- Test tilkobling: `mysql -u regnskap_user -p regnskap`

### Token validation error

- Slett og generer ny SECRET_KEY
- Logg ut og inn på nytt

### Import fails

- Sjekk CSV-format (kommaseparert, UTF-8)
- Verifiser at datoer er i ISO-format (YYYY-MM-DD)
- Sjekk at beløp bruker punktum som desimalskilletegn

## Bidrag

Bidrag er velkomne! Vennligst opprett en issue først for større endringer.

## Lisens

MIT License

## Kontakt

For spørsmål eller support, opprett en issue i repository
