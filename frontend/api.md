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

### `GET /fire`
FIRE-oppsettet for regnskapet og appens eget svar. Gir 404 hvis regnskapet ikke har FIRE slått på.
Valgfritt `?retirement_date=ÅÅÅÅ-MM-DD` regner i tillegg ut hva som skjer om man slutter å jobbe da
(`result.target`); uten den brukes måldatoen fra oppsettet, om den finnes.

Alle beløp er i dagens kroner per måned, om ikke annet står.

- `settings`: fødselsdato, horisont (alderen beregningen går til), uttaksrate (`swr_percent`),
  forventet avkastning og inflasjon (nominelt; `real_return_percent` er realavkastningen), hvor
  mange måneder forbruket snittes over (`lookback_months`), andelen av fellesregnskapet som regnes
  med (`shared_ledger_id`, `shared_share_percent`), gevinstskatt på aksjesparekonto og formuesskatt.
- `obligations`: kostnader og lån som tar slutt.
  - `cost_account` er kostnadskontoen den bokføres på (med `ledger_id`, siden den kan ligge i
    fellesregnskapet). Den kontoen er holdt utenfor forbruket, og kostnaden løper i stedet med
    `per_month` til `until`.
  - `account` er gjeldskontoen for et lån. `balance` er restgjelden som brukes, lest fra kontoen
    når den ikke er oppgitt.
  - `until` er siste måned. `until_derived: true` betyr at den er regnet ut fra saldo, rente og
    terminbeløp, ikke oppgitt. `first_payment` er satt når betalingen starter senere.
  - `indexed`: om beløpet følger inflasjonen. `frees_up_cash`: om beløpet går til sparing når
    forpliktelsen er slutt. `counts_as_debt`: om restgjelden trekkes fra formuen.
- `income_streams`: pensjoner som kommer som inntekt, med alder og måned de starter (`from`) og
  eventuelt slutter (`until`). `per_month` er brutto; `tax_percent` er den effektive skatten som
  trekkes, og `net_per_month` det som er igjen. Skatt 0 betyr at beløpet er oppgitt netto.
- `excluded_cost_accounts`: kostnadskontoer som er holdt utenfor forbruket av andre grunner, typisk
  overføringen til fellesregnskapet, som telles via andelen i stedet.
- `capital`: kapital per konto. `unlock_age` er satt for bundet pensjon, `payout_years` hvis den
  betales ut over flere år, `annual_contribution` er årlig innskudd (`contribution_by_employer`:
  betalt av arbeidsgiver, ikke av egen lønn), `payout_tax_percent` er skatten på hver utbetaling
  fra bundet pensjon (IPS 22), `gains_tax: true` markerer aksjesparekonto: innskuddene tas ut
  skattefritt først, deretter skattes gevinsten med `settings.gains_tax_percent`. `deposits` er innskutt beløp på aksjesparekonto,
  `valuation_percent` er verdsettelsen i formuesgrunnlaget, og `excluded` betyr at pengene ikke
  er dine å bruke.
- `result`: appens svar. `monthly_spending` er forbruket utenom forpliktelsene,
  `fire_number.total` er kapitalen som trengs, og `earliest` er første måned planen holder til
  horisonten (`null` hvis den ikke gjør det før 75 år). `bridge_low` er det laveste den frie
  kapitalen kommer før pensjonen frigjøres. `gains_tax_total` og `pension_tax_total` er skatten
  på uttak fra aksjesparekonto og på pensjon fram til horisonten, og `taxes_by_year` viser den år
  for år sammen med formuesskatten. FIRE-tallet tar med gevinstskatten som et anslag; datoen
  regner den nøyaktig. `warnings` er appens egne merknader til tallene.

```json
{"ledger_id": 5, "as_of": "2026-11-22",
 "settings": {"birth_date": "1985-06-01", "age": 41, "horizon_age": 90, "swr_percent": 3.5,
              "expected_return_percent": 6.0, "inflation_percent": 2.5, "real_return_percent": 3.41,
              "shared_ledger_id": 2, "shared_share_percent": 50.0, "...": "..."},
 "obligations": [
   {"name": "Barnebidrag", "kind": "CHILD_SUPPORT", "is_active": true, "account": null,
    "cost_account": {"ledger_id": 5, "number": "6904", "name": "Barnebidrag"},
    "per_month": 4000.0, "first_payment": null, "until": "2030-08", "until_derived": false,
    "balance": null, "interest_percent": null, "indexed": true,
    "frees_up_cash": true, "counts_as_debt": false, "total_interest": 0.0},
   {"name": "Studielån", "kind": "LOAN",
    "account": {"ledger_id": 5, "number": "2603", "name": "Studielån"},
    "cost_account": {"ledger_id": 5, "number": "7103", "name": "Renter på studielån"},
    "per_month": 2500.0, "until": "2038-05", "until_derived": true,
    "balance": 250000.0, "interest_percent": 4.5, "...": "..."}],
 "income_streams": [{"name": "Folketrygd", "per_month": 15000.0, "tax_percent": 20.0,
                     "net_per_month": 12000.0, "from_age": 67, "from": "2052-06",
                     "until_age": null, "until": null, "indexed": true, "is_active": true}],
 "excluded_cost_accounts": [{"ledger_id": 5, "number": "6102", "name": "Felleskostnader"}],
 "capital": {"available": 400000.0, "locked": 120000.0, "excluded": 0.0,
             "accounts": [{"number": "1605", "name": "IPS", "amount": 30000.0,
                           "unlock_age": 62, "payout_years": 10, "payout_tax_percent": 22.0,
                           "gains_tax": false, "...": "..."}]},
 "result": {"monthly_spending": 25000.0, "monthly_net_income": 45000.0,
            "monthly_obligations": 6500.0,
            "fire_number": {"total": 9000000.0, "...": "..."},
            "earliest": {"date": "2043-01-01", "age": 57, "success": true, "depleted": null,
                         "bridge_low": 100000.0, "bridge_low_date": "2052-05-01",
                         "first_wealth_tax_year": 2040, "gains_tax_total": 400000.0,
                         "pension_tax_total": 250000.0, "taxes_by_year": ["..."]},
            "target": null, "warnings": []}}
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
