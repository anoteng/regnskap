# Vedleggskø - Brukerveiledning

## Oversikt

Vedleggssystemet lar deg laste opp kvitteringer fra mobil og koble dem til transaksjoner i hovedappen.

## Arkitektur

### 1. Database
- `receipts` tabell lagrer metadata og filplassering
- Status: PENDING → MATCHED → ARCHIVED
- Bilder lagres i `uploads/receipts/{ledger_id}/`

### 2. Backend API
- `POST /api/receipts/upload` - last opp bilde
- `GET /api/receipts` - hent køen
- `POST /api/receipts/{id}/match/{transaction_id}` - koble til transaksjon
- `GET /api/receipts/{id}/image` - hent bilde

### 3. Frontend (Desktop)
- **Vedleggskø** i hovedmenyen (📎 Vedlegg)
- Viser alle kvitteringer i rutenett
- Søk og koble til transaksjoner
- Redigere metadata (dato, beløp, notat)

### 4. Mobile PWA
- Tilgjengelig på `/kvittering`
- Tar bilder med kamera eller velger fra galleri
- Enkel opplasting med valgfrie metadata

## Kom i gang

### Steg 1: Kjør database-migrasjon

```bash
# Fra root-mappen
mysql -u [din_bruker] -p regnskap < database/migrations/add_receipts_table.sql
```

### Steg 2: Lag PWA-ikoner

Se `frontend/static/icons/README.md` for instruksjoner.

Rask løsning med ImageMagick:
```bash
cd frontend/static/icons
convert -size 192x192 xc:#2563eb -gravity center -pointsize 120 -fill white -annotate +0+0 "📎" icon-192.png
convert -size 512x512 xc:#2563eb -gravity center -pointsize 320 -fill white -annotate +0+0 "📎" icon-512.png
```

### Steg 3: Restart backend

```bash
# Backend må restartes for å laste nye routes
sudo systemctl restart regnskap-backend
# eller hvis du kjører manuelt:
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## Bruk

### Fra mobil:

1. Gå til `https://regnskap.noteng.no/kvittering` på mobilen
2. **Installer appen** (viktig for best opplevelse):
   - **iOS Safari**: Trykk Del-knappen (⬆️) → "Legg til på Hjem-skjerm"
   - **Android Chrome**: Trykk meny (⋮) → "Legg til på startskjermen"
3. Åpne appen fra hjemskjermen
4. Logg inn
5. Ta bilde av kvittering eller velg fra galleri
6. Legg eventuelt til dato/beløp/notat
7. Last opp - ferdig!

### Fra desktop:

1. Gå til **📎 Vedlegg** i hovedmenyen
2. Se alle opplastede kvitteringer
3. Filtrer: Ubehandlede / Matchet / Alle
4. Klikk på kvittering for å se fullskjerm
5. Klikk "Koble til transaksjon" for å:
   - Søke etter transaksjoner (dato, beløp, beskrivelse)
   - Velge riktig transaksjon
   - Koble automatisk
6. Redigere metadata ved behov
7. Slette hvis ikke relevant

## Fordeler

### Nå (Fase 1 - Manuell matching):
✅ Enkel opplasting fra mobil
✅ Alle kvitteringer samlet på ett sted
✅ Søk og filtrer transaksjoner
✅ Ett klikk for å koble
✅ Offline PWA (fungerer uten nett)

### Fremtid (Fase 2 - AI-matching):
- 🤖 Automatisk utlesing av dato, beløp, butikk
- 🎯 Foreslår matchende transaksjoner automatisk
- 📊 Foreslår kategori basert på innhold
- ⚡ Ett klikk for å godkjenne forslag

## Teknisk

### Filhåndtering
- Maks filstørrelse: 10MB
- Tillatte formater: JPG, PNG, PDF, HEIC
- Lagring: `uploads/receipts/{ledger_id}/{uuid}.{ext}`
- Automatisk sletting ved fjerning av kvittering

### Sikkerhet
- Krever autentisering
- Ledger-isolering (ser kun egne vedlegg)
- HTTPS påkrevd for PWA
- Bilder lagres ikke i database (kun path)

### PWA-funksjoner
- Installeres som app
- Fungerer offline (service worker)
- Kamera-tilgang
- Push-notifikasjoner (kan legges til)

## Feilsøking

### "Kunne ikke laste opp"
- Sjekk at backend kjører
- Sjekk filstørrelse < 10MB
- Sjekk filformat (JPG/PNG/PDF/HEIC)
- Sjekk at `uploads/receipts/` mappen eksisterer og er skrivbar

### "Kunne ikke åpne kamera"
- Mobilen må gi tillatelse til kamera
- Krever HTTPS (http://localhost fungerer også)
- Noen nettlesere krever brukerinteraksjon først

### PWA installeres ikke
- Sjekk at du bruker HTTPS
- Sjekk at `manifest.json` er tilgjengelig
- Sjekk at ikoner eksisterer
- Nettleseren må støtte PWA (Safari 11.1+, Chrome 40+)

## API-eksempler

### Laste opp kvittering

```bash
curl -X POST https://regnskap.noteng.no/api/receipts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Ledger-ID: 1" \
  -F "file=@kvittering.jpg" \
  -F "receipt_date=2025-01-27" \
  -F "amount=125.50" \
  -F "description=Mat fra Rema"
```

### Hente køen

```bash
curl https://regnskap.noteng.no/api/receipts?status=PENDING \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Ledger-ID: 1"
```

### Koble til transaksjon

```bash
curl -X POST https://regnskap.noteng.no/api/receipts/123/match/456 \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Ledger-ID: 1"
```

## Neste steg (Fase 2)

Når grunnfunksjonaliteten fungerer godt, kan vi legge til:

1. **AI-powered OCR** (Claude API eller Tesseract)
   - Ekstraher dato, beløp, butikk automatisk
   - Foreslå matchende transaksjoner
   - Kategoriser automatisk

2. **Forbedringer**
   - Batch-opplasting (flere bilder samtidig)
   - Crop/roter bilder før opplasting
   - QR-kode scanning for eFaktura
   - Push-notifikasjoner når ny kvittering mottas
   - E-post-forwarding (send kvittering på e-post → automatisk opplasting)

3. **Integrasjoner**
   - Google Drive / Dropbox for backup
   - E-postimport (forwarding)
   - SMS-parsing for kvitteringer

Kostnadsestimat AI (Fase 2):
- Claude API: ~2-3 kr/mnd for 100 kvitteringer
- Tesseract (gratis): Mindre nøyaktig men OK for norske kvitteringer
