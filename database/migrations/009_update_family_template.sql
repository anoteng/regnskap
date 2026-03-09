-- Migration 009: Update family_accounting template to match user's refined accounts
-- Based on changes made to "Familieregnskap - test" (ledger 10)

-- Rename 6704 from "Ferie og reise - opphold" to "Ferie og reise" (parent category)
UPDATE template_accounts
SET account_name = 'Ferie og reise'
WHERE template_id = 4 AND account_number = '6704';

-- Set accounts to is_default=0 (hidden by default, user can enable)
UPDATE template_accounts
SET is_default = 0
WHERE template_id = 4 AND account_number IN (
    '1505',  -- Inventar og utstyr
    '1600',  -- Finansielle investeringer
    '1601',  -- Aksjer og andeler
    '1602',  -- Obligasjoner
    '1603',  -- Fond
    '1604',  -- BSU-konto
    '1605',  -- IPS/pensjonssparing
    '3101',  -- Fastlønn
    '3102',  -- Overtid
    '3103',  -- Bonus
    '3104',  -- Feriepenger
    '3105',  -- Naturalytelser
    '3300',  -- Pensjon og trygd
    '3301',  -- Alderspensjon
    '3302',  -- AFP
    '6705',  -- Ferie og reise - reiseutgifter
    '6706',  -- Ferie og reise - dagligvarer
    '6707',  -- Ferie og reise - restaurant
    '6708',  -- Ferie og reise - transport
    '6709',  -- Ferie og reise - diverse
    '6901',  -- Gaver til familie og venner
    '8200',  -- Aksjeutbytte
    '8300'   -- Gevinst finansielle instrumenter
);
