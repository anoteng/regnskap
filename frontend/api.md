# Privatregnskap API

Et API for andre programmer: egne apper, regneark, skript, assistenter. Det leser, og kan også
bokføre hvis nøkkelen er laget for det.

## Tilgang

1. Logg inn på https://privatregnskap.eu, gå til Regnskapsinnstillinger → **API-nøkler**, og lag en nøkkel.
   Velg om den skal nå alle regnskapene dine eller bare ett, om den skal utløpe, og om den skal
   kunne bokføre (**Kun lese** eller **Lese og bokføre**).
2. Nøkkelen vises én gang og begynner med `pr_`. Oppbevar den som et passord.
3. Send den med hver forespørsel:

```
Authorization: Bearer pr_...
```

Nøkkelen har dine rettigheter og aldri mer: bare regnskap du er medlem av, og den slutter å virke for
et regnskap hvis du mister tilgangen til det. En nøkkel som kan bokføre, gjør det bare i regnskap der
du er eier eller medlem; der du bare har lesetilgang (`VIEWER`), kan den bare lese. Den kan tilbakekalles når som helst på samme side.

Grunnadresse: `https://privatregnskap.eu/api/v1`

## Velge regnskap

Kan nøkkelen lese mer enn ett regnskap, må alle kall unntatt `/ledgers` ha `?ledger_id=`.
Er den låst til ett regnskap, kan parameteren utelates.

## Beløp

- Beløp er tall i kroner med to desimaler.
- Fortegn følger kontotypen: eiendeler (`ASSET`) og kostnader (`EXPENSE`) øker med debet;
  gjeld (`LIABILITY`), egenkapital (`EQUITY`) og inntekter (`REVENUE`) øker med kredit.
  En kostnad på 500 kr er altså `500`, ikke `-500`.
- Overføringer mellom egne kontoer er verken inntekt eller kostnad.
- Kladder fra banksynk (`status: DRAFT`) er med, som i appens egne rapporter. De har bare banksiden
  til de er bokført, så de flytter banksaldoen, men ikke inntekter og kostnader.

## Endepunkter

### `GET /ledgers`
Regnskapene nøkkelen kan lese, og om den kan bokføre i hvert av dem.
```json
[{"id": 2, "name": "Fellesregnskap", "role": "VIEWER", "can_write": false},
 {"id": 3, "name": "Privat", "role": "OWNER", "can_write": true}]
```

### `GET /accounts`
Kontoplanen. Inntekts- og kostnadskontoene er kategoriene. `?include_inactive=true` tar med deaktiverte kontoer.
```json
[{"id": 257, "number": "1201", "name": "Brukskonto", "type": "ASSET",
  "parent_id": null, "parent_number": null, "description": null, "is_active": true,
  "fire_role": "AVAILABLE", "fire_unlock_age": null, "wealth_valuation_percent": 100.0}]
```

### `GET /bank-accounts`
Bankkontoer og kort, med dagens saldo fra regnskapet.
```json
[{"id": 5, "name": "Brukskonto", "type": "CHECKING", "bank_account_number": "12345678901",
  "account_id": 257, "account_number": "1201", "is_active": true, "balance": 18250.0}]
```

### `GET /transactions`
Transaksjoner med alle posteringslinjer, eldste først.

| Parameter | |
|---|---|
| `from`, `to` | Datoer, `ÅÅÅÅ-MM-DD`, begge inkludert |
| `account_id` eller `account_number` | Bare transaksjoner som berører kontoen (alle linjene tas med) |
| `status` | `DRAFT`, `POSTED` eller `RECONCILED` |
| `limit` | 1–1000, standard 500 |
| `cursor` | `next_cursor` fra forrige side |

```json
{"transactions": [
  {"id": 1234, "date": "2026-01-11", "description": "REMA 1000", "reference": null,
   "status": "POSTED", "source": "BANK_SYNC",
   "lines": [
     {"account_id": 257, "account_number": "1201", "account_name": "Brukskonto",
      "account_type": "ASSET", "debit": 0.0, "credit": 412.5, "description": null},
     {"account_id": 301, "account_number": "6001", "account_name": "Dagligvarer",
      "account_type": "EXPENSE", "debit": 412.5, "credit": 0.0, "description": null}]}],
 "next_cursor": "2026-01-11_1234"}
```
`next_cursor` er `null` på siste side.

### `GET /balances/monthly?from=ÅÅÅÅ-MM&to=ÅÅÅÅ-MM`
Per måned og konto: bevegelse i måneden, og for balansekontoer (`ASSET`, `LIABILITY`, `EQUITY`)
saldoen ved utgangen av den. Kontoer uten noen av delene utelates.
Standard er de siste tolv månedene til og med inneværende; høyst 240 måneder per kall.
```json
{"ledger_id": 2, "months": [
  {"month": "2026-10", "accounts": [
    {"account_id": 257, "account_number": "1201", "account_name": "Brukskonto",
     "type": "ASSET", "movement": 3120.0, "balance": 18250.0},
    {"account_id": 301, "account_number": "6001", "account_name": "Dagligvarer",
     "type": "EXPENSE", "movement": 7400.0}]}]}
```

### `GET /summary/monthly?from=ÅÅÅÅ-MM&to=ÅÅÅÅ-MM`
Inntekter, kostnader og netto per måned, og eiendeler, gjeld og nettoformue ved utgangen av hver måned
(bokførte verdier; fond er med til siste registrerte markedsverdi).
```json
{"ledger_id": 2, "months": [
  {"month": "2026-10", "income": 52000.0, "expenses": 47500.0, "net": 4500.0,
   "assets": 2400000.0, "liabilities": 1900000.0, "net_worth": 500000.0}]}
```

## Bokføre

Krever en nøkkel med **Lese og bokføre**, og et regnskap der `can_write` er `true`.
API-et endrer aldri bokførte bilag; retting og reversering gjøres i appen.

### Posteringslinjer

Alle skrivekall bruker samme form for linjer. Kontoen oppgis med `account_number` eller `account_id`,
og hver linje har enten `debit` eller `credit`, større enn null:
```json
{"account_number": "6301", "debit": 412.5, "description": "valgfri"}
```
Et bilag må ha minst to linjer, og sum debet må være lik sum kredit.

### `POST /transactions/{id}/post`
Bokfører en kladd fra banksynken. Kladden har banksiden; send motpostene, gjerne fordelt på flere
kontoer. `description` kan erstatte bankens tekst. Svaret er bilaget, som i `GET /transactions`.
```json
{"lines": [
  {"account_number": "6301", "debit": 300},
  {"account_number": "6302", "debit": 112.5}],
 "description": "REMA 1000, mat og kaffe"}
```
Et kjøp på 412,50 har banklinjen `credit: 412.5` på bankkontoen, så motpostene står i debet.
En innbetaling er motsatt: motposten står i kredit (for eksempel lønn på en inntektskonto).

### `GET /transactions/chain-suggestions`
Par av kladder som ser ut som de to sidene av én overføring mellom egne kontoer: samme beløp,
motsatt side, høyst to dager mellom. Krever bare lesetilgang.
```json
[{"first_id": 4501, "second_id": 4502, "amount": 862.0,
  "first_date": "2026-06-23", "second_date": "2026-06-23",
  "first_description": "Overføring", "second_description": "Overføring",
  "first_account": "Regningskonto", "second_account": "Brukskonto", "confidence": "HIGH"}]
```
`confidence` er `HIGH` ved samme dato, ellers `MEDIUM`.

### `POST /transactions/chain`
Slår sammen to kladder, én på hver side av en overføring, til ett bokført bilag. Begge må være
kladder med bare banklinjen, på ulike kontoer, og beløpene må gå nøyaktig opp. Det tidligste bilaget
beholdes; det andre forsvinner. Svaret er det sammenslåtte bilaget.
```json
{"first_id": 4501, "second_id": 4502}
```

### `POST /transactions`
Et nytt bilag, for eksempel noe som ikke går gjennom banken. `status` er `POSTED` (standard) eller
`DRAFT`. Bilaget merkes `source: "API"`.
```json
{"date": "2026-10-31", "description": "Kontant fra mor", "reference": null, "status": "POSTED",
 "lines": [
   {"account_number": "1100", "debit": 500},
   {"account_number": "3405", "credit": 500}]}
```

### `DELETE /transactions/{id}`
Sletter en kladd som ble laget via API-et. Andre bilag slettes i appen.

### `POST /accounts`
Ny konto i kontoplanen. Bare `number`, `name` og `type` (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`,
`EXPENSE`) er påkrevd.
```json
{"number": "1630", "name": "Fond", "type": "ASSET", "parent_number": "1600",
 "description": null, "fire_role": "AVAILABLE", "fire_unlock_age": null,
 "wealth_valuation_percent": 80, "value_change_account_number": "8300"}
```
`value_change_account_number` er kontoen verdiendringer føres mot (se under).

### `POST /accounts/{id}/market-value`
Setter en eiendelskonto (fond, aksjer, pensjon) til markedsverdien på en dato, standard i dag.
Forskjellen fra bokført saldo føres mot kontoens verdiendringskonto. Verdier må legges inn i
datorekkefølge; samme dato på nytt erstatter den forrige.
```json
{"value": 125000, "date": "2026-11-13"}
```
Svaret er `{"adjustment": <bilag>}`, eller `{"adjustment": null}` hvis kontoen allerede stod på verdien.

## Feil

Feil kommer som `{"detail": "..."}`:

| Kode | Betyr |
|---|---|
| 400 | Ugyldig parameter, `ledger_id` mangler, eller bilaget balanserer ikke |
| 401 | Nøkkel mangler, er feil, utløpt eller tilbakekalt |
| 403 | Nøkkelen kan bare lese, eller du har bare lesetilgang til regnskapet |
| 404 | Regnskapet, bilaget eller kontoen finnes ikke, eller nøkkelen har ikke tilgang |
| 409 | Bilaget er allerede bokført, kontonummeret finnes, eller bilaget kan ikke slettes her |

## Eksempel

```sh
curl -H "Authorization: Bearer $REGNSKAP_API_KEY" \
  "$REGNSKAP_URL/api/v1/summary/monthly?ledger_id=2&from=2026-01"
```
