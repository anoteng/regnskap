# Passkey-innlogging (WebAuthn)

## Oversikt

Passkeys er moderne, sikker autentisering som bruker biometri (fingeravtrykk, Face ID) eller enhetens PIN i stedet for passord. Basert på FIDO2/WebAuthn-standarden.

## Fordeler

✅ **Mer sikkert enn passord**
- Kan ikke phishes (funker kun på riktig domene)
- Ingen passord å stjele eller glemme
- Kryptografisk sikker

✅ **Bedre brukeropplevelse**
- Ett trykk for å logge inn
- Fungerer på tvers av enheter (synkroniseres via iCloud/Google)
- Spesielt bra på mobil

✅ **Ingen ekstra kostnad**
- Innebygd i alle moderne enheter og nettlesere
- Ingen SMS-kostnader eller ekstra maskinvare nødvendig

## Støtte

### Nettlesere som støtter passkeys:
- Safari 16+ (iOS 16+, macOS 13+)
- Chrome 108+ (Android, Windows, macOS, Linux)
- Edge 108+
- Firefox 119+ (kun macOS/Windows)

### Enheter:
- iPhone/iPad med Face ID eller Touch ID
- Android-telefoner med fingeravtrykk/face unlock
- Mac med Touch ID
- Windows 10/11 med Windows Hello
- YubiKey og andre FIDO2 sikkerhetsnøkler

## Komme i gang

### 1. Legg til din første passkey

1. Logg inn med passord
2. Gå til **⚙️ Innstillinger**
3. Klikk **➕ Legg til passkey** under "Passkeys"
4. Gi den et navn (f.eks. "Min iPhone", "MacBook Pro")
5. Godkjenn med fingeravtrykk/Face ID

### 2. Logg inn med passkey

**Desktop:**
1. Gå til innloggingssiden
2. Klikk **🔐 Logg inn med passkey**
3. Godkjenn med fingeravtrykk/Face ID/PIN
4. Ferdig!

**Mobil PWA:**
1. Åpne kvitteringsappen
2. Klikk **🔐 Logg inn med passkey**
3. Godkjenn med biometri
4. Ferdig!

### 3. Administrer passkeys

I innstillinger kan du:
- Se alle dine passkeys
- Gi dem nye navn
- Slette passkeys du ikke lenger bruker
- Se når de sist ble brukt

## Beste praksis

✅ **Legg til passkey på alle enhetene dine**
- Egen passkey for telefon, laptop, arbeidsdatamaskin, etc.
- Gi dem beskrivende navn så du vet hvilken som er hvilken

✅ **Behold passordinnlogging som backup**
- Passkeys synkroniseres via iCloud/Google, men hvis du bytter økosystem (iOS → Android) kan du midlertidig miste tilgang
- Passordet fungerer alltid som fallback

✅ **Bruk YubiKey for ekstra sikkerhet** (valgfritt)
- Fysisk sikkerhetsnøkkel som fungerer på alle enheter
- Kan ikke stjeles via nettfisking

## Produksjonsoppsett

For at passkeys skal fungere i produksjon, må du oppdatere `.env`:

```bash
# Produksjon
RP_ID=regnskap.noteng.no
RP_NAME=Regnskap

# Utvikling (default)
RP_ID=localhost
RP_NAME=Regnskap
```

**Viktig:**
- `RP_ID` må matche domenet brukeren besøker
- HTTPS er påkrevd i produksjon (localhost fungerer uten)
- Passkeys registrert på localhost fungerer ikke på produksjonsdomenet og vice versa

## Feilsøking

### "Passkeys er ikke støttet i denne nettleseren"
- Oppdater nettleseren til nyeste versjon
- På Firefox: kun macOS/Windows støttes
- Prøv Chrome/Safari

### "Kunne ikke opprette passkey"
- Sjekk at du har gitt nettleseren tillatelse til å bruke biometri
- På Mac: Systeminnstillinger → Touch ID må være aktivert
- På Windows: Windows Hello må være satt opp

### "Invalid or expired challenge"
- Prøv å refresh siden og forsøk igjen
- Challenges utløper etter en tid for sikkerhet

### Passkey fungerer ikke etter serverrestart
- Challenges lagres i minne (ikke persistent)
- Dette er normalt og kun påvirker pågående registreringer/innlogginger
- Registrerte passkeys fungerer alltid

### Passkeys synkroniseres ikke mellom enheter
- **iOS/macOS:** Krever at enheter er logget inn på samme iCloud-konto
- **Android/Chrome:** Krever Google Password Manager
- **På tvers av plattformer:** Legg til ny passkey på hver enhet

## Teknisk implementering

### Backend
- `/api/auth/passkey/register/begin` - Start registrering
- `/api/auth/passkey/register/complete` - Fullfør registrering
- `/api/auth/passkey/login/begin` - Start innlogging
- `/api/auth/passkey/login/complete` - Fullfør innlogging (returnerer JWT)
- `/api/auth/passkey/credentials` - Liste brukerens passkeys
- `/api/auth/passkey/credentials/{id}` - Slett passkey

### Frontend
- `PasskeyManager` klasse i `passkey.js`
- Håndterer Base64url encoding/decoding
- Wrapper `navigator.credentials` API
- Fungerer både på desktop og mobil PWA

### Database
```sql
CREATE TABLE webauthn_credentials (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    credential_id VARCHAR(1024) NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count INT NOT NULL DEFAULT 0,
    credential_name VARCHAR(255),
    created_at TIMESTAMP,
    last_used_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Videre utvikling

Mulige forbedringer:

1. **Persistent challenge-lagring**
   - Flytt fra in-memory dict til Redis
   - Tillater serverrestart uten å miste pågående challenges

2. **Conditional UI**
   - Detekter automatisk tilgjengelige passkeys (`PublicKeyCredential.isConditionalMediationAvailable()`)
   - Autofyll-lignende UX i innloggingsskjema

3. **Attestation verification**
   - Verifiser at passkey kommer fra ekte enhet (ikke simulator)
   - Krever root certificates database

4. **Cross-platform credentials**
   - Støtt "roaming authenticators" (YubiKey, etc.)
   - Tillat både platform (Touch ID) og cross-platform (USB-nøkkel)

5. **Backup codes**
   - Generer engangskoder som backup
   - Hvis bruker mister alle enheter

## Ressurser

- [WebAuthn Awesome List](https://github.com/herrjemand/awesome-webauthn)
- [passkeys.dev](https://passkeys.dev/) - Utviklerressurser
- [FIDO Alliance](https://fidoalliance.org/)
- [py_webauthn dokumentasjon](https://github.com/duo-labs/py_webauthn)

## Sikkerhet

Passkeys er designet for å være phishing-resistent:
- Fungerer kun på domenet de ble registrert på
- Private nøkler forlater aldri enheten
- Ingen delte hemmeligheter (ingen passord å stjele)
- Sign count forhindrer kloning av credentials

For beste sikkerhet:
- Bruk HTTPS i produksjon
- Sett streng `RP_ID` (ikke wildcards)
- Logg og monitorér sign count anomalier
- Krev user verification (fingeravtrykk/PIN)
