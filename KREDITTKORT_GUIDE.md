# Guide: Kredittkort i Regnskap

## Forklaring av dobbel bokføring for kredittkort

Kredittkort er **gjeldskontoer** (LIABILITY), som betyr at de fungerer motsatt av bankkontoer (ASSET) i dobbel bokføring.

## Kontoplan

Standard kontoer for kredittkort:
- **2501 - Kredittkort**: Gjeldskonto for kredittkortsaldo
- **7104 - Renter på kredittkort**: Utgiftskonto for kredittkort-renter

## Oppsett

### 1. Opprett bankkonto for kredittkortet

1. Gå til **Bankkontoer**
2. Klikk **Ny bankkonto**
3. Fyll ut:
   - **Navn**: F.eks. "Visa kredittkort"
   - **Type**: Kredittkort
   - **Kontonummer**: Siste 4 siffer (valgfri)
   - **Koble til konto**: Velg "2501 - Kredittkort"
4. Klikk **Opprett bankkonto**

### 2. Importer transaksjoner fra kredittkort

CSV-import håndterer automatisk korrekt debet/kredit-logikk basert på kontotype.

**For kredittkort (LIABILITY)**:
- Positive beløp (kjøp) = **kredit** på kredittkonto (øker gjeld)
- Negative beløp (refusjon) = **debet** på kredittkonto (reduserer gjeld)

**Eksempel CSV-fil fra kredittkort**:
```csv
Dato;Beskrivelse;Beløp;Referanse
2025-01-15;Rema 1000;856.50;VISA-1234
2025-01-16;Shell Bensin;650.00;VISA-1235
2025-01-20;Refusjon fra butikk;-200.00;VISA-1236
```

## Eksempler på transaksjoner

### Kjøp på kredittkort (500 kr dagligvarer)

```
Debet:  6301 Dagligvarer (utgift)      500 kr
Kredit: 2501 Kredittkort (gjeld)       500 kr
```

**Resultat**:
- Gjelden din øker med 500 kr
- Utgiften registreres

### Refusjon på kredittkort (200 kr)

```
Debet:  2501 Kredittkort (gjeld)       200 kr
Kredit: 6301 Dagligvarer (utgift)      200 kr
```

**Resultat**:
- Gjelden din reduseres med 200 kr
- Utgiften reverseres

### Betaling av kredittkortfaktura (5000 kr)

Dette gjøres som en **manuell transaksjon**:

1. Gå til **Transaksjoner** → **Ny transaksjon**
2. Fyll ut:
   - **Dato**: Fakturaens forfallsdato
   - **Beskrivelse**: "Betaling kredittkortfaktura"
3. Legg til posteringer:
   - **Debet**: 2501 Kredittkort - 5000 kr (reduserer gjeld)
   - **Kredit**: 1201 Brukskonto - 5000 kr (reduserer eiendel)
4. Klikk **Lagre transaksjon**

**Resultat**:
- Kredittkortsaldoen går ned med 5000 kr
- Bankkontoen går ned med 5000 kr

## Balanse og rapporter

### I balansen vil kredittkort vises under **Gjeld**:

```
Eiendeler:
  1201 Brukskonto         15 000 kr

Gjeld:
  2501 Kredittkort        -3 500 kr    (negativ = gjeld)

Egenkapital:
  Netto formue            11 500 kr
```

## Viktige punkter

1. **CSV-import for kredittkort**: Systemet håndterer automatisk korrekt debet/kredit når du importerer fra kredittkort
2. **Betaling av faktura**: Må gjøres som manuell transaksjon
3. **Gjeldsaldo**: Vises som negativt tall i balansen (høyere gjeld = mer negativt)
4. **Ikke bland kontoer**: Bruk 2501 for kredittkortet, ikke bankkontoer

## Feilsøking

### "Transaksjon ikke balansert"-feil
- Sjekk at sum debet = sum kredit
- For kredittkortkjøp: debet utgift, kredit kredittkort
- For fakturabetaling: debet kredittkort, kredit bankkonto

### Feil fortegn på saldo
- Kredittkort skal ha **negativ** saldo når du skylder penger
- Hvis saldoen er positiv, er posteringene feil vei
