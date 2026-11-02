import api from './api.js?v=21';
import { formatCurrency, formatDate, showError, showSuccess } from './utils.js?v=21';

function currentMonth() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function shiftMonth(ym, delta) {
    const [y, m] = ym.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(ym) {
    const [y, m] = ym.split('-').map(Number);
    const label = new Intl.DateTimeFormat('nb-NO', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1));
    return label.charAt(0).toUpperCase() + label.slice(1);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

function accountLabel(a) {
    return `${a.account_number} ${a.account_name}`;
}

class SettlementManager {
    constructor() {
        this.month = currentMonth();
        this.initialized = false;
        this.accounts = null;
    }

    // ------------------------------------------------------------------
    // Calculation view
    // ------------------------------------------------------------------
    init() {
        if (!this.initialized) {
            document.getElementById('settlement-prev-month').addEventListener('click', () => {
                this.month = shiftMonth(this.month, -1);
                this.load();
            });
            document.getElementById('settlement-next-month').addEventListener('click', () => {
                this.month = shiftMonth(this.month, 1);
                this.load();
            });
            document.getElementById('settlement-this-month').addEventListener('click', () => {
                this.month = currentMonth();
                this.load();
            });
            this.initialized = true;
        }
        this.load();
    }

    async load() {
        document.getElementById('settlement-month-label').textContent = monthLabel(this.month);
        const container = document.getElementById('settlement-content');
        container.innerHTML = '<p class="subtitle">Beregner…</p>';

        try {
            const data = await api.getSettlementCalculation(this.month);
            await this.ensureAccounts();
            container.innerHTML = this.render(data);
        } catch (error) {
            if (/ikke aktivert/i.test(error.message)) {
                container.innerHTML = `
                    <div class="card">
                        <h2>Månedsavregning er ikke aktivert</h2>
                        <p class="subtitle">Avregningen viser hvor mye hver deltaker bør overføre til driftskontoen for å dekke måneden.
                        Regnskapets eier kan aktivere og konfigurere den under Innstillinger.</p>
                        <button class="btn btn-primary" onclick="app.switchView('ledger-settings')">Gå til innstillinger</button>
                    </div>`;
            } else {
                container.innerHTML = `<div class="card"><p style="color: var(--danger-color);">Kunne ikke hente avregning: ${escapeHtml(error.message)}</p></div>`;
            }
        }
    }

    async ensureAccounts() {
        if (!this.accounts) {
            this.accounts = await api.getAccounts(null, true);
        }
        this.accountById = Object.fromEntries(this.accounts.map(a => [a.id, a]));
    }

    accountName(id) {
        const a = this.accountById?.[id];
        return a ? accountLabel(a) : `#${id}`;
    }

    render(data) {
        const t = data.totals;
        const status = data.month_complete
            ? 'Måneden er avsluttet – tallene er faktiske.'
            : `Per ${formatDate(data.as_of)} · ${data.days_remaining} dager igjen`;

        const memberRows = data.members.map(m => {
            const transfer = parseFloat(m.recommended_transfer);
            const carry = parseFloat(m.carry_in || 0);
            const cls = transfer > 0 ? 'settlement-due' : 'settlement-ahead';
            const hint = transfer > 0 ? 'å overføre' : 'til gode';
            const carryCell = carry === 0
                ? '<span class="subtitle">–</span>'
                : `<span class="${carry > 0 ? 'settlement-ahead' : 'settlement-due'}">${formatCurrency(Math.abs(carry))}<br><small>${carry > 0 ? 'til gode' : 'skyldig'}</small></span>`;
            return `
                <tr>
                    <td><strong>${escapeHtml(m.full_name)}</strong><br><small class="subtitle">${parseFloat(m.share_percent).toLocaleString('nb-NO')} % andel</small></td>
                    <td class="num">${formatCurrency(m.share_amount)}</td>
                    <td class="num">${formatCurrency(m.own_withdrawals)}</td>
                    <td class="num">${formatCurrency(m.contributed)}</td>
                    <td class="num">${carryCell}</td>
                    <td class="num ${cls}"><strong>${formatCurrency(Math.abs(transfer))}</strong><br><small>${hint}</small></td>
                </tr>`;
        }).join('');

        const plannedRows = data.planned.length
            ? data.planned.map(p => `
                <tr>
                    <td>${formatDate(p.expected_date)}${p.overdue ? ' <span class="status-badge status-expired">forfalt</span>' : ''}</td>
                    <td>${escapeHtml(p.description)}</td>
                    <td class="num">${formatCurrency(p.amount)}</td>
                </tr>`).join('')
            : '<tr><td colspan="3" class="subtitle">Ingen registrerte fakturaer med forfall resten av måneden.</td></tr>';

        // Shown, not silently dropped: the purchases behind a card statement
        // were charged to the members in the month they were made, so counting
        // the invoice too would bill them twice
        const cardStatements = (data.card_statements || []);
        const cardStatementNote = cardStatements.length
            ? `<p class="subtitle">${cardStatements.map(c =>
                `Kredittkortfaktura ${escapeHtml(c.description)} · forfall ${formatDate(c.expected_date)} · ${formatCurrency(c.amount)}`
              ).join('<br>')}<br>Holdt utenfor grunnlaget — kjøpene er kostnadsført hver for seg da de ble gjort.</p>`
            : '';

        const recurringRows = data.recurring.length
            ? data.recurring.map(r => `
                <tr>
                    <td>ca. ${r.expected_day}.</td>
                    <td>${escapeHtml(r.description)}${r.period_months > 1 ? ` <small class="subtitle">(hver ${r.period_months}. måned)</small>` : ''}</td>
                    <td class="num">${formatCurrency(r.amount)}</td>
                </tr>`).join('')
            : '<tr><td colspan="3" class="subtitle">Ingen gjenstående faste trekk gjenkjent fra historikken.</td></tr>';

        const excluded = data.excluded_account_ids.length
            ? `<p class="subtitle">Holdt utenfor: ${data.excluded_account_ids.map(id => escapeHtml(this.accountName(id))).join(', ')}
               (${formatCurrency(t.excluded_booked)} bokført denne måneden)</p>`
            : '';

        const carryNote = data.carry_from
            ? ` Over- og underbetaling regnes fra ${formatDate(data.carry_from)}.`
            : ' Overføring mellom måneder er ikke slått på.';

        const liq = data.liquidity;
        const cards = liq.credit_cards.map(c =>
            `<div><span class="subtitle">${escapeHtml(c.name)}:</span> ${formatCurrency(c.owed)} utestående</div>`).join('');

        // The balance is the conservative figure and the one the sum uses. The
        // invoiced amount is what actually leaves on the due date; the gap is
        // what has been charged since the statement closed.
        const cardInvoiced = parseFloat(liq.card_invoiced || 0);
        const cardInvoicedNote = cardInvoiced > 0
            ? `<br><small class="subtitle">Fakturert ${formatCurrency(cardInvoiced)}; resten er belastet etter at terminen ble avsluttet</small>`
            : '';

        const available = liq.expected_available != null ? parseFloat(liq.expected_available) : null;
        // The warning is only honest once the outstanding contributions are
        // counted in. A card the account cannot cover today is normal on the
        // 3rd and a problem on the 14th.
        const shortfall = liq.covers_card === false
            ? `<div class="settlement-warning">Felleskontoen dekker ikke kortregningen som forfaller den ${liq.card_due_day}., selv om alle betaler sin andel. Det mangler ${formatCurrency(parseFloat(liq.credit_card_owed_total) - parseFloat(liq.operating_balance) - parseFloat(liq.outstanding_contributions))}.</div>`
            : '';

        return `
            <p class="subtitle">${status}</p>

            <div class="dashboard-grid">
                <div class="card">
                    <h3>Bokført hittil</h3>
                    <p class="amount">${formatCurrency(t.booked)}</p>
                    <small class="subtitle">Fast ${formatCurrency(t.booked_fixed)} · variabelt ${formatCurrency(t.booked_variable)}</small>
                </div>
                <div class="card">
                    <h3>Gjenstår (anslag)</h3>
                    <p class="amount">${formatCurrency(parseFloat(t.planned_remaining) + parseFloat(t.recurring_remaining) + parseFloat(t.variable_remaining))}</p>
                    <small class="subtitle">Fakturaer ${formatCurrency(t.planned_remaining)} · faste ${formatCurrency(t.recurring_remaining)} · variabelt ${formatCurrency(t.variable_remaining)}</small>
                </div>
                <div class="card">
                    <h3>Prognose for måneden</h3>
                    <p class="amount">${formatCurrency(t.forecast_total)}</p>
                    <small class="subtitle">Inntekt − ${formatCurrency(t.income_booked)} · avdrag + ${formatCurrency(t.debt_principal)} · typisk variabelt ${formatCurrency(t.typical_variable_month)}</small>
                </div>
            </div>

            <div class="card">
                <h2>Deltakere</h2>
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Deltaker</th>
                                <th class="num">Andel av prognose</th>
                                <th class="num">Egne uttak</th>
                                <th class="num">Innbetalt</th>
                                <th class="num">Overført fra før</th>
                                <th class="num">Anbefalt nå</th>
                            </tr>
                        </thead>
                        <tbody>${memberRows}</tbody>
                    </table>
                </div>
                <p class="subtitle" style="margin-top: 0.75rem;">Anbefalt = andel + egne uttak fra driftskontoen − innbetalt denne måneden − det som er til gode fra før.${carryNote}</p>
                ${excluded}
            </div>

            <div class="settlement-columns">
                <div class="card">
                    <h2>Registrerte fakturaer</h2>
                    <table class="table">
                        <thead><tr><th>Forfall</th><th>Beskrivelse</th><th class="num">Beløp</th></tr></thead>
                        <tbody>${plannedRows}</tbody>
                    </table>
                    ${cardStatementNote}
                </div>
                <div class="card">
                    <h2>Forventede faste trekk</h2>
                    <table class="table">
                        <thead><tr><th>Dag</th><th>Motpart</th><th class="num">Beløp</th></tr></thead>
                        <tbody>${recurringRows}</tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <h2>Likviditet</h2>
                ${shortfall}
                <table class="table settlement-liquidity">
                    <tbody>
                        <tr><td>Driftskonto</td><td class="num">${liq.operating_balance != null ? formatCurrency(liq.operating_balance) : '–'}</td></tr>
                        <tr><td>Utestående bidrag</td><td class="num">+ ${formatCurrency(liq.outstanding_contributions)}</td></tr>
                        <tr><td>Kortgjeld <small class="subtitle">(forfall den ${liq.card_due_day}.)</small>${cardInvoicedNote}</td><td class="num">− ${formatCurrency(liq.credit_card_owed_total)}</td></tr>
                        <tr><td>Registrerte fakturaer</td><td class="num">− ${formatCurrency(liq.open_invoices)}</td></tr>
                        <tr class="settlement-liquidity-sum">
                            <td><strong>Disponibelt</strong></td>
                            <td class="num ${available != null && available < 0 ? 'settlement-due' : 'settlement-ahead'}"><strong>${available != null ? formatCurrency(available) : '–'}</strong></td>
                        </tr>
                    </tbody>
                </table>
                ${cards}
                <p class="subtitle" style="margin-top: 0.5rem;">Disponibelt forutsetter at alle betaler sin andel. Anslått variabelt forbruk resten av måneden er ikke trukket fra.</p>
            </div>
        `;
    }

    // ------------------------------------------------------------------
    // Settings card (rendered inside ledger settings)
    // ------------------------------------------------------------------
    async loadSettingsCard(ledger) {
        const container = document.getElementById('settlement-settings-container');
        if (!container) return;
        const isOwner = ledger.user_role === 'OWNER';

        try {
            const [settings, members] = await Promise.all([
                api.getSettlementSettings(),
                api.getLedgerMembers(ledger.id),
            ]);
            this.accounts = await api.getAccounts(null, true);
            this.accountById = Object.fromEntries(this.accounts.map(a => [a.id, a]));
            this.settings = settings;
            this.ledgerMembers = members;
            container.innerHTML = this.renderSettings(settings, members, isOwner);
            if (isOwner) this.bindSettings();
        } catch (error) {
            container.innerHTML = `<p style="color: var(--danger-color);">Kunne ikke hente avregningsinnstillinger: ${escapeHtml(error.message)}</p>`;
        }
    }

    renderSettings(settings, members, isOwner) {
        const dis = isOwner ? '' : 'disabled';
        const assetAccounts = this.accounts.filter(a => a.account_type === 'ASSET' && a.is_active);
        const expenseAccounts = this.accounts.filter(a => a.account_type === 'EXPENSE' && a.is_active);
        const depositCandidates = this.accounts.filter(a => a.is_active && a.account_type !== 'EXPENSE');

        const options = (list, selected) =>
            `<option value="">–</option>` + list.map(a =>
                `<option value="${a.id}" ${a.id === selected ? 'selected' : ''}>${escapeHtml(accountLabel(a))}</option>`).join('');

        const configured = Object.fromEntries(settings.members.map(m => [m.user_id, m]));
        const memberRows = members.map(m => {
            const cfg = configured[m.user_id];
            const defaultShare = cfg ? parseFloat(cfg.share_percent) : (members.length === 1 ? 100 : '');
            return `
                <tr data-user-id="${m.user_id}">
                    <td>${escapeHtml(m.user.full_name)}<br><small class="subtitle">${escapeHtml(m.user.email)}</small></td>
                    <td><input type="number" class="settlement-share" min="0" max="100" step="0.01" value="${defaultShare}" style="width: 6rem;" ${dis}> %</td>
                    <td><select class="settlement-deposit" ${dis}>${options(depositCandidates, cfg?.deposit_account_id ?? null)}</select></td>
                </tr>`;
        }).join('');

        const excludedSet = new Set(settings.excluded_account_ids);
        const excludedList = expenseAccounts.map(a => `
            <label class="settlement-exclude-item">
                <input type="checkbox" class="settlement-exclude" value="${a.id}" ${excludedSet.has(a.id) ? 'checked' : ''} ${dis}>
                ${escapeHtml(accountLabel(a))}
            </label>`).join('');

        return `
            <p class="subtitle">Beregner hvor mye hver deltaker bør overføre til driftskontoen per måned, ut fra bokførte kostnader,
            registrerte fakturaer, faste trekk gjenkjent fra historikken og et anslag for variable kostnader.
            Fungerer både for ett-persons og delte regnskap.</p>

            <div class="form-group">
                <label><input type="checkbox" id="settlement-enabled" ${settings.is_enabled ? 'checked' : ''} ${dis}> Aktiver månedsavregning for dette regnskapet</label>
            </div>

            <div class="form-group">
                <label for="settlement-operating-account">Driftskonto (kontoen felleskostnadene betales fra)</label>
                <select id="settlement-operating-account" ${dis}>${options(assetAccounts, settings.operating_account_id)}</select>
            </div>

            <div class="form-group">
                <label for="settlement-lookback">Måneder historikk for variable kostnader</label>
                <input type="number" id="settlement-lookback" min="1" max="24" value="${settings.variable_lookback_months}" style="width: 6rem;" ${dis}>
            </div>

            <div class="form-group">
                <label for="settlement-carry-start">Overfør over- og underbetaling fra</label>
                <input type="date" id="settlement-carry-start" value="${settings.carry_start || ''}" ${dis}>
                <small class="subtitle">Avvik før denne datoen regnes som oppgjort mellom deltakerne. Tom = ingen overføring mellom måneder.</small>
            </div>

            <div class="form-group">
                <label for="settlement-card-due-day">Forfallsdag for kortregningen</label>
                <input type="number" id="settlement-card-due-day" min="1" max="28" value="${settings.card_due_day}" style="width: 6rem;" ${dis}>
                <small class="subtitle">Kjøpene er allerede fordelt måneden de ble gjort; dagen brukes bare til å varsle om pengene er på plass i tide.</small>
            </div>

            <h3>Deltakere</h3>
            <div class="table-responsive">
                <table class="table">
                    <thead><tr><th>Medlem</th><th>Andel</th><th>Innskuddskonto</th></tr></thead>
                    <tbody>${memberRows}</tbody>
                </table>
            </div>
            <p class="subtitle">Andelene må summere til 100 %. Innskuddskontoen er der medlemmets innbetalinger krediteres og egne uttak fra driftskontoen debiteres; la den stå tom hvis det ikke er aktuelt.</p>

            <h3 style="margin-top: 1.5rem;">Kostnadskontoer som holdes utenfor</h3>
            <p class="subtitle">Kostnader ført på disse kontoene regnes ikke som felleskostnader (f.eks. utlegg som refunderes, eller investeringer én deltaker dekker selv).</p>
            <div class="settlement-exclude-list">${excludedList}</div>

            ${isOwner ? `<button id="settlement-save-btn" class="btn btn-primary" style="margin-top: 1rem;">Lagre avregningsinnstillinger</button>`
                      : `<p class="subtitle" style="margin-top: 1rem;">Kun eier av regnskapet kan endre disse innstillingene.</p>`}
            ${settings.updated_at ? `<p class="subtitle" style="margin-top: 0.5rem;">Sist lagret ${formatDate(settings.updated_at)}</p>` : ''}
        `;
    }

    bindSettings() {
        document.getElementById('settlement-save-btn').addEventListener('click', () => this.saveSettings());
    }

    async saveSettings() {
        const members = [...document.querySelectorAll('#settlement-settings-container tr[data-user-id]')]
            .map(row => ({
                user_id: parseInt(row.dataset.userId, 10),
                share_percent: row.querySelector('.settlement-share').value,
                deposit_account_id: row.querySelector('.settlement-deposit').value || null,
            }))
            .filter(m => m.share_percent !== '' && parseFloat(m.share_percent) > 0)
            .map(m => ({ ...m, share_percent: parseFloat(m.share_percent), deposit_account_id: m.deposit_account_id ? parseInt(m.deposit_account_id, 10) : null }));

        const payload = {
            is_enabled: document.getElementById('settlement-enabled').checked,
            operating_account_id: parseInt(document.getElementById('settlement-operating-account').value, 10) || null,
            variable_lookback_months: parseInt(document.getElementById('settlement-lookback').value, 10) || 3,
            carry_start: document.getElementById('settlement-carry-start').value || null,
            card_due_day: parseInt(document.getElementById('settlement-card-due-day').value, 10) || 15,
            members,
            excluded_account_ids: [...document.querySelectorAll('.settlement-exclude:checked')].map(cb => parseInt(cb.value, 10)),
        };

        try {
            this.settings = await api.updateSettlementSettings(payload);
            showSuccess('Avregningsinnstillinger lagret');
        } catch (error) {
            showError(error.message);
        }
    }
}

const settlementManager = new SettlementManager();
window.settlementManager = settlementManager;
export default settlementManager;
