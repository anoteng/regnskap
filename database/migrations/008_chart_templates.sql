-- Migration 008: Create three chart of accounts templates
-- Personlig (default), Familie, Organisasjon/Enkeltpersonforetak

-- ============================================
-- 1. Update existing template to "personal_accounting"
-- ============================================
UPDATE chart_of_accounts_templates
SET name = 'personal_accounting',
    display_name = 'Personlig',
    description = 'Enkel kontoplan for personlig økonomi med lønn, bolig, transport, mat og fritid.'
WHERE id = 1;

-- Remove personal/specific accounts from template 1
DELETE FROM template_accounts WHERE template_id = 1 AND account_number IN (
    '3110', '3111',   -- Innskudd Caroline/Andreas
    '6750', '6751', '6752', '6753',  -- Fjørfe
    '6804'            -- Forsikring katt
);

-- ============================================
-- 2. Create "Familie" template
-- ============================================
INSERT INTO chart_of_accounts_templates (name, display_name, description, is_active, is_default)
VALUES ('family_accounting', 'Familie', 'Detaljert kontoplan for felles husholdningsøkonomi med ekstra detaljer for ferie, kjæledyr og delte utgifter.', 1, 0);

SET @family_id = LAST_INSERT_ID();

INSERT INTO template_accounts (template_id, account_number, account_name, account_type, is_default, sort_order) VALUES
-- Eiendeler
(@family_id, '1000', 'EIENDELER', 'ASSET', 1, 100),
(@family_id, '1100', 'Kasse, bank og lignende', 'ASSET', 1, 110),
(@family_id, '1200', 'Bankinnskudd', 'ASSET', 1, 120),
(@family_id, '1201', 'Brukskonto', 'ASSET', 1, 121),
(@family_id, '1202', 'Sparekonto', 'ASSET', 1, 122),
(@family_id, '1203', 'Brukskonto 2', 'ASSET', 1, 123),
(@family_id, '1204', 'Boliglånskonto', 'ASSET', 1, 124),
(@family_id, '1300', 'Andre fordringer', 'ASSET', 1, 130),
(@family_id, '1400', 'Forskuddsbetalte kostnader', 'ASSET', 1, 140),
(@family_id, '1500', 'Varige driftsmidler', 'ASSET', 1, 150),
(@family_id, '1501', 'Bolig', 'ASSET', 1, 151),
(@family_id, '1502', 'Hytte/fritidseiendom', 'ASSET', 1, 152),
(@family_id, '1503', 'Bil', 'ASSET', 1, 153),
(@family_id, '1504', 'Båt', 'ASSET', 1, 154),
(@family_id, '1505', 'Inventar og utstyr', 'ASSET', 1, 155),
(@family_id, '1600', 'Finansielle investeringer', 'ASSET', 1, 160),
(@family_id, '1601', 'Aksjer og andeler', 'ASSET', 1, 161),
(@family_id, '1602', 'Obligasjoner', 'ASSET', 1, 162),
(@family_id, '1603', 'Fond', 'ASSET', 1, 163),
(@family_id, '1604', 'BSU-konto', 'ASSET', 1, 164),
(@family_id, '1605', 'IPS/pensjonssparing', 'ASSET', 1, 165),
-- Gjeld og egenkapital
(@family_id, '2000', 'GJELD OG EGENKAPITAL', 'LIABILITY', 1, 200),
(@family_id, '2100', 'Leverandørgjeld', 'LIABILITY', 1, 210),
(@family_id, '2200', 'Skyldige offentlige avgifter', 'LIABILITY', 1, 220),
(@family_id, '2300', 'Skyldige skatter', 'LIABILITY', 1, 230),
(@family_id, '2400', 'Betalbar skatt', 'LIABILITY', 1, 240),
(@family_id, '2500', 'Annen kortsiktig gjeld', 'LIABILITY', 1, 250),
(@family_id, '2501', 'Kredittkort', 'LIABILITY', 1, 251),
(@family_id, '2502', 'Forbrukslån', 'LIABILITY', 1, 252),
(@family_id, '2600', 'Langsiktig gjeld', 'LIABILITY', 1, 260),
(@family_id, '2601', 'Boliglån', 'LIABILITY', 1, 261),
(@family_id, '2602', 'Billån', 'LIABILITY', 1, 262),
(@family_id, '2603', 'Studielån', 'LIABILITY', 1, 263),
(@family_id, '2900', 'Egenkapital', 'EQUITY', 1, 290),
(@family_id, '2901', 'Innskutt egenkapital', 'EQUITY', 1, 291),
(@family_id, '2902', 'Opptjent egenkapital', 'EQUITY', 1, 292),
(@family_id, '2903', 'Årets resultat', 'EQUITY', 1, 293),
-- Inntekter
(@family_id, '3000', 'INNTEKTER', 'REVENUE', 1, 300),
(@family_id, '3100', 'Lønn og honorarer', 'REVENUE', 1, 310),
(@family_id, '3101', 'Fastlønn', 'REVENUE', 1, 311),
(@family_id, '3102', 'Overtid', 'REVENUE', 1, 312),
(@family_id, '3103', 'Bonus', 'REVENUE', 1, 313),
(@family_id, '3104', 'Feriepenger', 'REVENUE', 1, 314),
(@family_id, '3105', 'Naturalytelser', 'REVENUE', 1, 315),
(@family_id, '3200', 'Næringsinntekt', 'REVENUE', 1, 320),
(@family_id, '3300', 'Pensjon og trygd', 'REVENUE', 1, 330),
(@family_id, '3301', 'Alderspensjon', 'REVENUE', 1, 331),
(@family_id, '3302', 'AFP', 'REVENUE', 1, 332),
(@family_id, '3400', 'Andre inntekter', 'REVENUE', 1, 340),
(@family_id, '3401', 'Utbytte', 'REVENUE', 1, 341),
(@family_id, '3402', 'Renteinntekter', 'REVENUE', 1, 342),
(@family_id, '3403', 'Gevinst ved salg av aksjer', 'REVENUE', 1, 343),
(@family_id, '3404', 'Leie-/utleieinntekt', 'REVENUE', 1, 344),
(@family_id, '3405', 'Gaver og arv', 'REVENUE', 1, 345),
(@family_id, '3406', 'Cashback', 'REVENUE', 1, 346),
-- Kostnader
(@family_id, '4000', 'VAREKOSTNAD', 'EXPENSE', 1, 400),
(@family_id, '5000', 'LØNNSKOSTNAD', 'EXPENSE', 1, 500),
(@family_id, '5100', 'Honorarer', 'EXPENSE', 1, 510),
(@family_id, '6000', 'ANDRE DRIFTSKOSTNADER', 'EXPENSE', 1, 600),
(@family_id, '6100', 'Boligkostnader', 'EXPENSE', 1, 610),
(@family_id, '6101', 'Husleie', 'EXPENSE', 1, 611),
(@family_id, '6102', 'Felleskostnader', 'EXPENSE', 1, 612),
(@family_id, '6103', 'Kommunale avgifter', 'EXPENSE', 1, 613),
(@family_id, '6104', 'Strøm', 'EXPENSE', 1, 614),
(@family_id, '6105', 'Oppvarming', 'EXPENSE', 1, 615),
(@family_id, '6106', 'Renovasjon', 'EXPENSE', 1, 616),
(@family_id, '6107', 'Vedlikehold bolig', 'EXPENSE', 1, 617),
(@family_id, '6108', 'Innbo-/husforsikring', 'EXPENSE', 1, 618),
(@family_id, '6109', 'Boligkostnader investering', 'EXPENSE', 1, 619),
(@family_id, '6110', 'Andre boligkostnader', 'EXPENSE', 1, 620),
(@family_id, '6111', 'Møbler og hvitevarer', 'EXPENSE', 1, 621),
(@family_id, '6200', 'Transportkostnader', 'EXPENSE', 1, 630),
(@family_id, '6201', 'Drivstoff', 'EXPENSE', 1, 631),
(@family_id, '6202', 'Bompenger', 'EXPENSE', 1, 632),
(@family_id, '6203', 'Parkering', 'EXPENSE', 1, 633),
(@family_id, '6204', 'Kollektivtransport', 'EXPENSE', 1, 634),
(@family_id, '6205', 'Bilforsikring', 'EXPENSE', 1, 635),
(@family_id, '6206', 'Vedlikehold bil', 'EXPENSE', 1, 636),
(@family_id, '6207', 'Årsavgift bil', 'EXPENSE', 1, 637),
(@family_id, '6208', 'Andre bilutgifter', 'EXPENSE', 1, 638),
(@family_id, '6300', 'Mat og drikke', 'EXPENSE', 1, 640),
(@family_id, '6301', 'Dagligvarer', 'EXPENSE', 1, 641),
(@family_id, '6302', 'Restaurant og kafe', 'EXPENSE', 1, 642),
(@family_id, '6303', 'Too good to go', 'EXPENSE', 1, 643),
(@family_id, '6400', 'Klær og sko', 'EXPENSE', 1, 650),
(@family_id, '6450', 'Elektronikk', 'EXPENSE', 1, 655),
(@family_id, '6500', 'Helse og velvære', 'EXPENSE', 1, 660),
(@family_id, '6501', 'Medisiner og apotek', 'EXPENSE', 1, 661),
(@family_id, '6502', 'Lege og tannlege', 'EXPENSE', 1, 662),
(@family_id, '6503', 'Fysioterapeut', 'EXPENSE', 1, 663),
(@family_id, '6504', 'Trening og sport', 'EXPENSE', 1, 664),
(@family_id, '6505', 'Frisør og personlig pleie', 'EXPENSE', 1, 665),
(@family_id, '6600', 'Media og kommunikasjon', 'EXPENSE', 1, 670),
(@family_id, '6601', 'Telefon og internett', 'EXPENSE', 1, 671),
(@family_id, '6602', 'TV og strømmetjenester', 'EXPENSE', 1, 672),
(@family_id, '6603', 'Abonnementer', 'EXPENSE', 1, 673),
(@family_id, '6700', 'Fritid og kultur', 'EXPENSE', 1, 680),
(@family_id, '6701', 'Hobby og fritidsaktiviteter', 'EXPENSE', 1, 681),
(@family_id, '6702', 'Kino, teater og konserter', 'EXPENSE', 1, 682),
(@family_id, '6703', 'Bøker og spill', 'EXPENSE', 1, 683),
(@family_id, '6704', 'Ferie og reise - opphold', 'EXPENSE', 1, 684),
(@family_id, '6705', 'Ferie og reise - reiseutgifter', 'EXPENSE', 1, 685),
(@family_id, '6706', 'Ferie og reise - dagligvarer', 'EXPENSE', 1, 686),
(@family_id, '6707', 'Ferie og reise - restaurant', 'EXPENSE', 1, 687),
(@family_id, '6708', 'Ferie og reise - transport', 'EXPENSE', 1, 688),
(@family_id, '6709', 'Ferie og reise - diverse', 'EXPENSE', 1, 689),
(@family_id, '6754', 'Kjæledyr', 'EXPENSE', 1, 695),
(@family_id, '6755', 'Veterinær', 'EXPENSE', 1, 696),
(@family_id, '6800', 'Forsikringer', 'EXPENSE', 1, 700),
(@family_id, '6801', 'Livsforsikring', 'EXPENSE', 1, 701),
(@family_id, '6802', 'Personforsikring', 'EXPENSE', 1, 702),
(@family_id, '6803', 'Reiseforsikring', 'EXPENSE', 1, 703),
(@family_id, '6900', 'Gaver og bidrag', 'EXPENSE', 1, 710),
(@family_id, '6901', 'Gaver til familie og venner', 'EXPENSE', 1, 711),
(@family_id, '6902', 'Veldedige formål', 'EXPENSE', 1, 712),
(@family_id, '6903', 'Diverse', 'EXPENSE', 1, 713),
-- Finanskostnader
(@family_id, '7000', 'FINANSKOSTNADER', 'EXPENSE', 1, 720),
(@family_id, '7100', 'Rentekostnader', 'EXPENSE', 1, 721),
(@family_id, '7101', 'Renter på boliglån', 'EXPENSE', 1, 722),
(@family_id, '7102', 'Renter på billån', 'EXPENSE', 1, 723),
(@family_id, '7103', 'Renter på studielån', 'EXPENSE', 1, 724),
(@family_id, '7104', 'Renter på kredittkort', 'EXPENSE', 1, 725),
(@family_id, '7105', 'Renter på forbrukslån', 'EXPENSE', 1, 726),
(@family_id, '7200', 'Bankgebyrer', 'EXPENSE', 1, 730),
(@family_id, '7300', 'Tap ved salg av aksjer', 'EXPENSE', 1, 740),
(@family_id, '7400', 'Skatter og avgifter', 'EXPENSE', 1, 750),
(@family_id, '7401', 'Forskuddsskatt', 'EXPENSE', 1, 751),
(@family_id, '7402', 'Restskatt', 'EXPENSE', 1, 752),
(@family_id, '7403', 'Formuesskatt', 'EXPENSE', 1, 753),
-- Finansinntekter
(@family_id, '8000', 'FINANSINNTEKTER', 'REVENUE', 1, 800),
(@family_id, '8100', 'Renteinntekter bank', 'REVENUE', 1, 810),
(@family_id, '8200', 'Aksjeutbytte', 'REVENUE', 1, 820),
(@family_id, '8300', 'Gevinst finansielle instrumenter', 'REVENUE', 1, 830);

-- ============================================
-- 3. Create "Organisasjon" template (NS 4102-inspired)
-- ============================================
INSERT INTO chart_of_accounts_templates (name, display_name, description, is_active, is_default)
VALUES ('business_accounting', 'Organisasjon / Enkeltpersonforetak', 'Norsk standard kontoplan for næringsdrivende og enkeltpersonforetak.', 1, 0);

SET @biz_id = LAST_INSERT_ID();

INSERT INTO template_accounts (template_id, account_number, account_name, account_type, is_default, sort_order) VALUES
-- 1xxx Eiendeler
(@biz_id, '1000', 'EIENDELER', 'ASSET', 1, 100),
(@biz_id, '1200', 'Bankinnskudd', 'ASSET', 1, 120),
(@biz_id, '1201', 'Driftskonto', 'ASSET', 1, 121),
(@biz_id, '1202', 'Skattetrekkskonto', 'ASSET', 1, 122),
(@biz_id, '1203', 'Sparekonto', 'ASSET', 1, 123),
(@biz_id, '1300', 'Kundefordringer', 'ASSET', 1, 130),
(@biz_id, '1400', 'Andre fordringer', 'ASSET', 1, 140),
(@biz_id, '1500', 'Forskuddsbetalte kostnader', 'ASSET', 1, 150),
(@biz_id, '1700', 'Varige driftsmidler', 'ASSET', 1, 170),
(@biz_id, '1710', 'Maskiner og anlegg', 'ASSET', 1, 171),
(@biz_id, '1720', 'Inventar og utstyr', 'ASSET', 1, 172),
(@biz_id, '1730', 'Biler og transportmidler', 'ASSET', 1, 173),
(@biz_id, '1740', 'IT-utstyr', 'ASSET', 1, 174),
-- 2xxx Gjeld og egenkapital
(@biz_id, '2000', 'GJELD OG EGENKAPITAL', 'LIABILITY', 1, 200),
(@biz_id, '2400', 'Leverandørgjeld', 'LIABILITY', 1, 240),
(@biz_id, '2500', 'Skyldig merverdiavgift', 'LIABILITY', 1, 250),
(@biz_id, '2600', 'Skyldig skattetrekk', 'LIABILITY', 1, 260),
(@biz_id, '2700', 'Skyldig arbeidsgiveravgift', 'LIABILITY', 1, 270),
(@biz_id, '2770', 'Skyldig feriepenger', 'LIABILITY', 1, 277),
(@biz_id, '2780', 'Annen kortsiktig gjeld', 'LIABILITY', 1, 278),
(@biz_id, '2800', 'Langsiktig gjeld', 'LIABILITY', 1, 280),
(@biz_id, '2801', 'Banklån', 'LIABILITY', 1, 281),
(@biz_id, '2900', 'Egenkapital', 'EQUITY', 1, 290),
(@biz_id, '2901', 'Egenkapital', 'EQUITY', 1, 291),
(@biz_id, '2050', 'Privatkonto / eiers egenkapitalkonto', 'EQUITY', 1, 205),
(@biz_id, '2903', 'Årets resultat', 'EQUITY', 1, 293),
-- 3xxx Salgsinntekter
(@biz_id, '3000', 'SALGSINNTEKTER', 'REVENUE', 1, 300),
(@biz_id, '3100', 'Salgsinntekt, avgiftspliktig', 'REVENUE', 1, 310),
(@biz_id, '3200', 'Salgsinntekt, avgiftsfri', 'REVENUE', 1, 320),
(@biz_id, '3400', 'Offentlige tilskudd', 'REVENUE', 1, 340),
(@biz_id, '3600', 'Leieinntekter', 'REVENUE', 1, 360),
(@biz_id, '3900', 'Annen driftsrelatert inntekt', 'REVENUE', 1, 390),
-- 4xxx Varekostnad
(@biz_id, '4000', 'VAREKOSTNAD', 'EXPENSE', 1, 400),
(@biz_id, '4100', 'Innkjøp av varer', 'EXPENSE', 1, 410),
(@biz_id, '4200', 'Innkjøp av tjenester (underleverandør)', 'EXPENSE', 1, 420),
(@biz_id, '4300', 'Frakt og forsikring innkjøp', 'EXPENSE', 1, 430),
(@biz_id, '4500', 'Fremmedytelser og underentreprise', 'EXPENSE', 1, 450),
-- 5xxx Lønnskostnader
(@biz_id, '5000', 'LØNNSKOSTNADER', 'EXPENSE', 1, 500),
(@biz_id, '5100', 'Lønn til ansatte', 'EXPENSE', 1, 510),
(@biz_id, '5200', 'Feriepenger', 'EXPENSE', 1, 520),
(@biz_id, '5300', 'Arbeidsgiveravgift', 'EXPENSE', 1, 530),
(@biz_id, '5400', 'Pensjonskostnader', 'EXPENSE', 1, 540),
(@biz_id, '5500', 'Andre personalkostnader', 'EXPENSE', 1, 550),
(@biz_id, '5900', 'Godtgjørelse til eier (ENK)', 'EXPENSE', 1, 590),
-- 6xxx Annen driftskostnad
(@biz_id, '6000', 'ANNEN DRIFTSKOSTNAD', 'EXPENSE', 1, 600),
(@biz_id, '6100', 'Leiekostnader kontor/lager', 'EXPENSE', 1, 610),
(@biz_id, '6200', 'Strøm og oppvarming', 'EXPENSE', 1, 620),
(@biz_id, '6300', 'Renhold og renovasjon', 'EXPENSE', 1, 630),
(@biz_id, '6400', 'Kontorekvisita', 'EXPENSE', 1, 640),
(@biz_id, '6500', 'IT og programvare', 'EXPENSE', 1, 650),
(@biz_id, '6600', 'Telefon og internett', 'EXPENSE', 1, 660),
(@biz_id, '6700', 'Reklame og markedsføring', 'EXPENSE', 1, 670),
(@biz_id, '6800', 'Forsikringer', 'EXPENSE', 1, 680),
(@biz_id, '6900', 'Reise- og diettkostnader', 'EXPENSE', 1, 690),
(@biz_id, '6901', 'Bilgodtgjørelse', 'EXPENSE', 1, 691),
(@biz_id, '6902', 'Reisekostnader', 'EXPENSE', 1, 692),
(@biz_id, '6903', 'Diettkostnader', 'EXPENSE', 1, 693),
(@biz_id, '6940', 'Porto og frakt', 'EXPENSE', 1, 694),
(@biz_id, '6950', 'Kontingenter og abonnementer', 'EXPENSE', 1, 695),
(@biz_id, '6990', 'Diverse driftskostnader', 'EXPENSE', 1, 699),
-- 7xxx Avskrivninger og finanskostnader
(@biz_id, '7000', 'AVSKRIVNINGER OG FINANSKOSTNADER', 'EXPENSE', 1, 700),
(@biz_id, '7100', 'Avskrivninger', 'EXPENSE', 1, 710),
(@biz_id, '7400', 'Tap på fordringer', 'EXPENSE', 1, 740),
(@biz_id, '7700', 'Rentekostnader', 'EXPENSE', 1, 770),
(@biz_id, '7710', 'Renter på banklån', 'EXPENSE', 1, 771),
(@biz_id, '7770', 'Bankgebyrer', 'EXPENSE', 1, 777),
(@biz_id, '7800', 'Tap på finansielle instrumenter', 'EXPENSE', 1, 780),
-- 8xxx Finansinntekter
(@biz_id, '8000', 'FINANSINNTEKTER', 'REVENUE', 1, 800),
(@biz_id, '8100', 'Renteinntekter', 'REVENUE', 1, 810),
(@biz_id, '8200', 'Gevinst ved salg av aksjer', 'REVENUE', 1, 820),
(@biz_id, '8300', 'Andre finansinntekter', 'REVENUE', 1, 830);
