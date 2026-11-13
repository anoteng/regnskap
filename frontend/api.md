# Privatregnskap API (les)

Et lese-API for andre programmer: egne apper, regneark, skript. Det kan bare lese, aldri endre.

## Tilgang

1. Logg inn på https://privatregnskap.eu, gå til Regnskapsinnstillinger → **API-nøkler**, og lag en nøkkel.
   Velg om den skal kunne lese alle regnskapene dine eller bare ett, og om den skal utløpe.
2. Nøkkelen vises én gang og begynner med `pr_`. Oppbevar den som et passord.
3. Send den med hver forespørsel:

```
Authorization: Bearer pr_...
```

Nøkkelen leser med dine rettigheter: bare regnskap du er medlem av, og den slutter å virke for et
regnskap hvis du mister tilgangen til det. Den kan tilbakekalles når som helst på samme side.

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
Regnskapene nøkkelen kan lese.
```json
[{"id": 2, "name": "Fellesregnskap", "role": "MEMBER"}]
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

## Feil

Feil kommer som `{"detail": "..."}`:

| Kode | Betyr |
|---|---|
| 400 | Ugyldig parameter, eller `ledger_id` mangler |
| 401 | Nøkkel mangler, er feil, utløpt eller tilbakekalt |
| 404 | Regnskapet finnes ikke eller nøkkelen har ikke tilgang |

## Eksempel

```sh
curl -H "Authorization: Bearer $REGNSKAP_API_KEY" \
  "$REGNSKAP_URL/api/v1/summary/monthly?ledger_id=2&from=2026-01"
```
