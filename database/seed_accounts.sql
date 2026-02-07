-- Norwegian Standard Chart of Accounts (Norsk Standard Kontoplan)
-- Simplified version for personal accounting

-- KLASSE 1: EIENDELER (ASSETS)
INSERT INTO accounts (account_number, account_name, account_type, is_system) VALUES
-- Omløpsmidler
('1000', 'EIENDELER', 'ASSET', TRUE),
('1100', 'Kasse, bank og lignende', 'ASSET', TRUE),
('1200', 'Bankinnskudd', 'ASSET', TRUE),
('1201', 'Brukskonto bank', 'ASSET', TRUE),
('1202', 'Sparekonto bank', 'ASSET', TRUE),
('1300', 'Andre fordringer', 'ASSET', TRUE),
('1400', 'Forskuddsbetalte kostnader', 'ASSET', TRUE),

-- Anleggsmidler
('1500', 'Varige driftsmidler', 'ASSET', TRUE),
('1501', 'Bolig', 'ASSET', TRUE),
('1502', 'Hytte/fritidseiendom', 'ASSET', TRUE),
('1503', 'Bil', 'ASSET', TRUE),
('1504', 'Båt', 'ASSET', TRUE),
('1505', 'Inventar og utstyr', 'ASSET', TRUE),

('1600', 'Finansielle investeringer', 'ASSET', TRUE),
('1601', 'Aksjer og andeler', 'ASSET', TRUE),
('1602', 'Obligasjoner', 'ASSET', TRUE),
('1603', 'Fond', 'ASSET', TRUE),
('1604', 'BSU-konto', 'ASSET', TRUE),
('1605', 'IPS/pensjonssparing', 'ASSET', TRUE);

-- KLASSE 2: GJELD OG EGENKAPITAL (LIABILITY & EQUITY)
INSERT INTO accounts (account_number, account_name, account_type, is_system) VALUES
-- Kortsiktig gjeld
('2000', 'GJELD OG EGENKAPITAL', 'LIABILITY', TRUE),
('2100', 'Leverandørgjeld', 'LIABILITY', TRUE),
('2200', 'Skyldige offentlige avgifter', 'LIABILITY', TRUE),
('2300', 'Skyldige skatter', 'LIABILITY', TRUE),
('2400', 'Betalbar skatt', 'LIABILITY', TRUE),
('2500', 'Annen kortsiktig gjeld', 'LIABILITY', TRUE),
('2501', 'Kredittkort', 'LIABILITY', TRUE),
('2502', 'Forbrukslån', 'LIABILITY', TRUE),

-- Langsiktig gjeld
('2600', 'Langsiktig gjeld', 'LIABILITY', TRUE),
('2601', 'Boliglån', 'LIABILITY', TRUE),
('2602', 'Billån', 'LIABILITY', TRUE),
('2603', 'Studielån', 'LIABILITY', TRUE),

-- Egenkapital
('2900', 'Egenkapital', 'EQUITY', TRUE),
('2901', 'Innskutt egenkapital', 'EQUITY', TRUE),
('2902', 'Opptjent egenkapital', 'EQUITY', TRUE),
('2903', 'Årets resultat', 'EQUITY', TRUE);

-- KLASSE 3: SALGSINNTEKT (REVENUE)
INSERT INTO accounts (account_number, account_name, account_type, is_system) VALUES
('3000', 'SALGSINNTEKT', 'REVENUE', TRUE),
('3100', 'Lønn og honorarer', 'REVENUE', TRUE),
('3101', 'Fastlønn', 'REVENUE', TRUE),
('3102', 'Overtid', 'REVENUE', TRUE),
('3103', 'Bonus', 'REVENUE', TRUE),
('3104', 'Feriepenger', 'REVENUE', TRUE),
('3105', 'Naturalytelser', 'REVENUE', TRUE),
('3200', 'Næringsinntekt', 'REVENUE', TRUE),
('3300', 'Pensjon og trygd', 'REVENUE', TRUE),
('3301', 'Alderspensjon', 'REVENUE', TRUE),
('3302', 'AFP', 'REVENUE', TRUE),
('3400', 'Andre inntekter', 'REVENUE', TRUE),
('3401', 'Utbytte', 'REVENUE', TRUE),
('3402', 'Renteinntekter', 'REVENUE', TRUE),
('3403', 'Gevinst ved salg av aksjer', 'REVENUE', TRUE),
('3404', 'Leie-/utleieinntekt', 'REVENUE', TRUE),
('3405', 'Gaver og arv', 'REVENUE', TRUE);

-- KLASSE 4-7: VAREKOSTNAD OG DRIFTSKOSTNADER (EXPENSES)
INSERT INTO accounts (account_number, account_name, account_type, is_system) VALUES
('4000', 'VAREKOSTNAD', 'EXPENSE', TRUE),

-- Lønn og personalkostnader
('5000', 'LØNNSKOSTNAD', 'EXPENSE', TRUE),
('5100', 'Honorarer', 'EXPENSE', TRUE),

-- Andre driftskostnader
('6000', 'ANDRE DRIFTSKOSTNADER', 'EXPENSE', TRUE),

-- Bolig
('6100', 'Boligkostnader', 'EXPENSE', TRUE),
('6101', 'Husleie', 'EXPENSE', TRUE),
('6102', 'Felleskostnader', 'EXPENSE', TRUE),
('6103', 'Kommunale avgifter', 'EXPENSE', TRUE),
('6104', 'Strøm', 'EXPENSE', TRUE),
('6105', 'Oppvarming', 'EXPENSE', TRUE),
('6106', 'Renovasjon', 'EXPENSE', TRUE),
('6107', 'Vedlikehold bolig', 'EXPENSE', TRUE),
('6108', 'Innbo-/husforsikring', 'EXPENSE', TRUE),

-- Transport
('6200', 'Transportkostnader', 'EXPENSE', TRUE),
('6201', 'Drivstoff', 'EXPENSE', TRUE),
('6202', 'Bompenger', 'EXPENSE', TRUE),
('6203', 'Parkering', 'EXPENSE', TRUE),
('6204', 'Kollektivtransport', 'EXPENSE', TRUE),
('6205', 'Bilforsikring', 'EXPENSE', TRUE),
('6206', 'Vedlikehold bil', 'EXPENSE', TRUE),
('6207', 'Årsavgift bil', 'EXPENSE', TRUE),

-- Mat og husholdning
('6300', 'Mat og drikke', 'EXPENSE', TRUE),
('6301', 'Dagligvarer', 'EXPENSE', TRUE),
('6302', 'Restaurant og kafe', 'EXPENSE', TRUE),

-- Klær og sko
('6400', 'Klær og sko', 'EXPENSE', TRUE),

-- Helse og velvære
('6500', 'Helse og velvære', 'EXPENSE', TRUE),
('6501', 'Medisiner og apotek', 'EXPENSE', TRUE),
('6502', 'Lege og tannlege', 'EXPENSE', TRUE),
('6503', 'Fysioterapeut', 'EXPENSE', TRUE),
('6504', 'Trening og sport', 'EXPENSE', TRUE),
('6505', 'Frisør og personlig pleie', 'EXPENSE', TRUE),

-- Media og kommunikasjon
('6600', 'Media og kommunikasjon', 'EXPENSE', TRUE),
('6601', 'Telefon og internett', 'EXPENSE', TRUE),
('6602', 'TV og strømmetjenester', 'EXPENSE', TRUE),
('6603', 'Aviser og blader', 'EXPENSE', TRUE),

-- Fritid og kultur
('6700', 'Fritid og kultur', 'EXPENSE', TRUE),
('6701', 'Hobby og fritidsaktiviteter', 'EXPENSE', TRUE),
('6702', 'Kino, teater og konserter', 'EXPENSE', TRUE),
('6703', 'Bøker og spill', 'EXPENSE', TRUE),
('6704', 'Ferie og reise', 'EXPENSE', TRUE),

-- Forsikringer
('6800', 'Forsikringer', 'EXPENSE', TRUE),
('6801', 'Livsforsikring', 'EXPENSE', TRUE),
('6802', 'Personforsikring', 'EXPENSE', TRUE),
('6803', 'Reiseforsikring', 'EXPENSE', TRUE),

-- Gaver og bidrag
('6900', 'Gaver og bidrag', 'EXPENSE', TRUE),
('6901', 'Gaver til familie og venner', 'EXPENSE', TRUE),
('6902', 'Veldedige formål', 'EXPENSE', TRUE),

-- Finanskostnader
('7000', 'FINANSKOSTNADER', 'EXPENSE', TRUE),
('7100', 'Rentekostnader', 'EXPENSE', TRUE),
('7101', 'Renter på boliglån', 'EXPENSE', TRUE),
('7102', 'Renter på billån', 'EXPENSE', TRUE),
('7103', 'Renter på studielån', 'EXPENSE', TRUE),
('7104', 'Renter på kredittkort', 'EXPENSE', TRUE),
('7105', 'Renter på forbrukslån', 'EXPENSE', TRUE),
('7200', 'Bankgebyrer', 'EXPENSE', TRUE),
('7300', 'Tap ved salg av aksjer', 'EXPENSE', TRUE),

-- Skatter og avgifter
('7400', 'Skatter og avgifter', 'EXPENSE', TRUE),
('7401', 'Forskuddsskatt', 'EXPENSE', TRUE),
('7402', 'Restskatt', 'EXPENSE', TRUE),
('7403', 'Formuesskatt', 'EXPENSE', TRUE);

-- KLASSE 8: FINANSINNTEKTER (Andre inntekter er flyttet til 3400)
INSERT INTO accounts (account_number, account_name, account_type, is_system) VALUES
('8000', 'FINANSINNTEKTER', 'REVENUE', TRUE),
('8100', 'Renteinntekter bank', 'REVENUE', TRUE),
('8200', 'Aksjeutbytte', 'REVENUE', TRUE),
('8300', 'Gevinst finansielle instrumenter', 'REVENUE', TRUE);
