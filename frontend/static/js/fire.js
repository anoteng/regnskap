import api from './api.js?v=15';
import { formatCurrency, showError, showSuccess, showModal, closeModal } from './utils.js?v=15';

const KINDS = {
    LOAN: 'Lån',
    CHILD_SUPPORT: 'Barnebidrag',
    OTHER: 'Annet',
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

function kr(value) {
    if (value === null || value === undefined) return '–';
    return formatCurrency(value);
}

function pct(value) {
    return `${Number(value).toFixed(2).replace('.', ',')} %`;
}

function isoDate(value) {
    if (!value) return '–';
    const [y, m, d] = value.split('-');
    return `${d}.${m}.${y}`;
}

function monthYear(value) {
    if (!value) return '–';
    const [y, m] = value.split('-').map(Number);
    const label = new Intl.DateTimeFormat('nb-NO', { month: 'long', year: 'numeric' })
        .format(new Date(y, m - 1, 1));
    return label.charAt(0).toUpperCase() + label.slice(1);
}

class FireManager {
    constructor() {
        this.settings = null;
        this.accounts = null;
        this.ledgers = null;
        this.result = null;
        this.testDate = null;
    }

    async init() {
        const container = document.getElementById('fire-content');
        container.innerHTML = '<p class="subtitle">Regner…</p>';
        try {
            this.settings = await api.getFireSettings();
            this.accounts = await api.getAccounts();
            this.ledgers = await api.getLedgers();
        } catch (error) {
            container.innerHTML = `<div class="card"><p>${escapeHtml(error.message)}</p></div>`;
            return;
        }

        this.result = null;
        this.error = null;
        if (this.settings.is_enabled && this.settings.birth_date) {
            try {
                this.result = await api.getFireProjection(this.testDate);
            } catch (error) {
                this.error = error.message;
            }
        }
        container.innerHTML = this.render();
        this.bind();
    }

    // ------------------------------------------------------------------
    // Rendering
    // ------------------------------------------------------------------
    render() {
        if (!this.settings.is_enabled) {
            return `
                <div class="card">
                    <h2>Økonomisk uavhengighet</h2>
                    <p>Beregningen leser kapital, forbruk og inntekt rett ut av regnskapet.
                       Den trenger fødselsdato, fordi bundet kapital frigjøres etter alder.</p>
                </div>
                ${this.renderSettings()}
            `;
        }
        return `
            ${this.error ? `<div class="card"><p>${escapeHtml(this.error)}</p></div>` : ''}
            ${this.result ? this.renderHeadline() : ''}
            ${this.result ? this.renderWarnings() : ''}
            ${this.renderObligations()}
            ${this.result ? this.renderCapital() : ''}
            ${this.result ? this.renderProjection() : ''}
            ${this.renderSettings()}
        `;
    }

    renderHeadline() {
        const a = this.result.assumptions;
        const n = this.result.fire_number;
        const e = this.result.earliest;
        const capital = Number(a.capital_available) + Number(a.capital_locked);
        const progress = Number(n.total) > 0
            ? Math.min(100, (capital / Number(n.total)) * 100) : 0;

        return `
            <div class="card">
                <h2>Hvor du står</h2>
                <div class="fire-headline">
                    <div class="fire-figure">
                        <span class="fire-label">FIRE-tallet</span>
                        <strong>${kr(n.total)}</strong>
                        <span class="subtitle">i dagens kroner</span>
                    </div>
                    <div class="fire-figure">
                        <span class="fire-label">Kapital i dag</span>
                        <strong>${kr(capital)}</strong>
                        <span class="subtitle">${progress.toFixed(1).replace('.', ',')} % av målet</span>
                    </div>
                    <div class="fire-figure">
                        <span class="fire-label">Tidligste dato</span>
                        <strong>${e ? monthYear(e.retirement_date) : 'Ikke innen 75'}</strong>
                        <span class="subtitle">${e ? `du er ${e.retirement_age} år` : 'med dagens forutsetninger'}</span>
                    </div>
                </div>

                <table class="table">
                    <tbody>
                        <tr>
                            <td>Varig forbruk, ${kr(n.perpetual_annual_spending)} i året, kapitalisert til ${pct(a.swr_percent)}</td>
                            <td class="num">${kr(n.base_capital)}</td>
                        </tr>
                        ${Number(n.wealth_tax_capital) > 0 ? `
                        <tr>
                            <td>Formuesskatt, ${kr(n.wealth_tax_annual)} i året, som kapitalen selv må bære</td>
                            <td class="num">${kr(n.wealth_tax_capital)}</td>
                        </tr>` : ''}
                        ${Number(n.bridge_capital) > 0 ? `
                        <tr>
                            <td>Nåverdi av kostnadene som tar slutt - lån og bidrag fram til siste termin</td>
                            <td class="num">${kr(n.bridge_capital)}</td>
                        </tr>` : ''}
                        <tr>
                            <th>Samlet behov</th>
                            <th class="num">${kr(n.total)}</th>
                        </tr>
                    </tbody>
                </table>

                <p class="subtitle">
                    Forbruk ${kr(a.monthly_spending)} i måneden, forpliktelser ${kr(a.monthly_obligations)},
                    inntekt ${kr(a.monthly_net_income)}. Realavkastning ${pct(a.real_return_percent)}
                    (${pct(a.expected_return_percent)} nominelt minus ${pct(a.inflation_percent)} inflasjon).
                </p>
                ${this.renderBridge(e)}

                <div class="form-group">
                    <label>Test en annen dato</label>
                    <input type="date" id="fire-test-date" value="${this.testDate || this.settings.target_retirement_date || ''}">
                    <button class="btn btn-sm btn-secondary" id="fire-test-run">Beregn</button>
                    ${this.testDate ? '<button class="btn btn-sm btn-secondary" id="fire-test-clear">Nullstill</button>' : ''}
                </div>
                ${this.result.target ? this.renderTarget(this.result.target) : ''}
            </div>
        `;
    }

    renderBridge(projection) {
        if (!projection || projection.bridge_low === null || projection.bridge_low === undefined) return '';
        const low = Number(projection.bridge_low);
        return `
            <p class="subtitle">
                Broen fram til pensjonskapitalen løsner: lavest ${kr(low)} i ${monthYear(projection.bridge_low_date)}.
                ${low < 0 ? 'Den tilgjengelige potten tar slutt før den bundne åpner.' : ''}
            </p>
        `;
    }

    renderTarget(t) {
        return `
            <div class="card">
                <h3>${monthYear(t.retirement_date)}, ${t.retirement_age} år</h3>
                <p>
                    ${t.success
                        ? `Holder hele veien. Ved ${this.result.assumptions.horizon_age} år står det igjen ${kr(t.rows[t.rows.length - 1].total)}.`
                        : `Går tomt i ${monthYear(t.depleted_date)}.`}
                </p>
                ${t.first_wealth_tax_year
                    ? `<p class="subtitle">Formuesskatt fra ${t.first_wealth_tax_year}.</p>` : ''}
            </div>
        `;
    }

    renderWarnings() {
        const w = this.result.warnings || [];
        if (!w.length) return '';
        return `
            <div class="card">
                <h3>Verdt å se på</h3>
                <ul>${w.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>
            </div>
        `;
    }

    renderCapital() {
        const buckets = this.result.assumptions.buckets;
        if (!buckets.length) {
            return `<div class="card"><h2>Kapital</h2><p>Ingen kontoer er klassifisert ennå.
                Sett rolle på eiendelskontoene i kontoplanen.</p></div>`;
        }
        const label = (b) => {
            if (b.excluded) return 'Ekskludert';
            if (b.unlock_age) return `Bundet til ${b.unlock_age}`;
            return 'Tilgjengelig';
        };
        return `
            <div class="card">
                <h2>Kapital</h2>
                <table class="table">
                    <thead><tr><th>Konto</th><th>Rolle</th><th class="num">Verdsettelse</th><th class="num">Beløp</th></tr></thead>
                    <tbody>
                        ${buckets.map(b => `
                            <tr>
                                <td>${escapeHtml(b.name)}</td>
                                <td>${label(b)}</td>
                                <td class="num">${pct(b.valuation_percent)}</td>
                                <td class="num">${kr(b.amount)}</td>
                            </tr>`).join('')}
                        <tr>
                            <th colspan="3">Tilgjengelig og bundet</th>
                            <th class="num">${kr(Number(this.result.assumptions.capital_available) + Number(this.result.assumptions.capital_locked))}</th>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    renderObligations() {
        const list = this.settings.obligations || [];
        const outcomes = {};
        const source = this.result && (this.result.earliest || this.result.target);
        (source ? source.obligations : []).forEach(o => { outcomes[o.name] = o; });

        return `
            <div class="card">
                <div class="view-header">
                    <h2>Forpliktelser med sluttdato</h2>
                    <button class="btn btn-sm btn-primary" id="fire-add-obligation">Legg til</button>
                </div>
                <p class="subtitle">Lån og bidrag holdes utenfor det løpende forbruket, fordi de tar slutt.
                   Et lån med saldo og rente får nedbetalingsdatoen regnet ut.</p>
                ${list.length ? `
                <table class="table">
                    <thead><tr><th>Navn</th><th>Type</th><th class="num">Per måned</th><th>Slutter</th><th></th></tr></thead>
                    <tbody>
                        ${list.map(ob => {
                            const o = outcomes[ob.name];
                            const ends = o && o.ends ? isoDate(o.ends) : (ob.end_date ? isoDate(ob.end_date) : 'Aldri');
                            return `
                            <tr${ob.is_active ? '' : ' class="fire-off"'}>
                                <td>${escapeHtml(ob.name)}${ob.is_active ? '' : ' (av)'}</td>
                                <td>${KINDS[ob.kind] || ob.kind}</td>
                                <td class="num">${kr(ob.monthly_amount)}</td>
                                <td>${ends}${o && o.derived ? ' <span class="subtitle">(utledet)</span>' : ''}</td>
                                <td class="num">
                                    <button class="btn btn-sm btn-secondary" data-edit-obligation="${ob.id}">Rediger</button>
                                    <button class="btn btn-sm btn-secondary" data-delete-obligation="${ob.id}">Slett</button>
                                </td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>` : '<p>Ingen registrert.</p>'}
            </div>
        `;
    }

    renderProjection() {
        const p = this.result.target || this.result.earliest;
        if (!p) return '';
        return `
            <div class="card">
                <h2>År for år fra ${monthYear(p.retirement_date)}</h2>
                <div class="table-responsive">
                <table class="table">
                    <thead>
                        <tr>
                            <th>År</th><th>Alder</th>
                            <th class="num">Tilgjengelig</th>
                            <th class="num">Bundet</th>
                            <th class="num">Gjeld</th>
                            <th class="num">Forbruk</th>
                            <th class="num">Forpliktelser</th>
                            <th class="num">Formuesskatt</th>
                            <th class="num">Spart</th>
                            <th class="num">Tatt ut</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${p.rows.map(r => `
                            <tr${Number(r.available) < 0 ? ' class="fire-short"' : ''}>
                                <td>${r.year}</td>
                                <td>${r.age}</td>
                                <td class="num">${kr(r.available)}</td>
                                <td class="num">${Number(r.locked) ? kr(r.locked) : '–'}</td>
                                <td class="num">${Number(r.debt) ? kr(r.debt) : '–'}</td>
                                <td class="num">${kr(r.spending)}</td>
                                <td class="num">${Number(r.obligations) ? kr(r.obligations) : '–'}</td>
                                <td class="num">${Number(r.wealth_tax) ? kr(r.wealth_tax) : '–'}</td>
                                <td class="num">${r.working ? kr(r.saved) : '–'}</td>
                                <td class="num">${r.working ? '–' : kr(r.withdrawn)}</td>
                            </tr>`).join('')}
                    </tbody>
                </table>
                </div>
                <p class="subtitle">Alle beløp i dagens kroner.</p>
            </div>
        `;
    }

    renderSettings() {
        const s = this.settings;
        const otherLedgers = (this.ledgers || []).filter(l => l.id !== s.ledger_id);
        const expenseAndRevenue = (this.accounts || [])
            .filter(a => a.account_type === 'EXPENSE' || a.account_type === 'REVENUE');

        return `
            <div class="card">
                <h2>Forutsetninger</h2>
                <form id="fire-settings-form">
                    <div class="form-group">
                        <label><input type="checkbox" id="fire-enabled" ${s.is_enabled ? 'checked' : ''}> Beregn FIRE for dette regnskapet</label>
                    </div>
                    <div class="settlement-columns">
                        <div class="form-group">
                            <label>Fødselsdato</label>
                            <input type="date" id="fire-birth-date" value="${s.birth_date || ''}">
                        </div>
                        <div class="form-group">
                            <label>Pengene skal vare til alder</label>
                            <input type="number" id="fire-horizon-age" min="50" max="120" value="${s.horizon_age}">
                        </div>
                        <div class="form-group">
                            <label>Måldato (valgfri)</label>
                            <input type="date" id="fire-target-date" value="${s.target_retirement_date || ''}">
                        </div>
                    </div>
                    <div class="settlement-columns">
                        <div class="form-group">
                            <label>Uttaksrate (%)</label>
                            <input type="number" id="fire-swr" step="0.01" min="0.1" max="20" value="${s.swr_percent}">
                        </div>
                        <div class="form-group">
                            <label>Inflasjon (%)</label>
                            <input type="number" id="fire-inflation" step="0.01" value="${s.inflation_percent}">
                        </div>
                        <div class="form-group">
                            <label>Forventet avkastning (%)</label>
                            <input type="number" id="fire-return" step="0.01" value="${s.expected_return_percent}">
                        </div>
                    </div>
                    <div class="settlement-columns">
                        <div class="form-group">
                            <label>Standardavvik avkastning (%)</label>
                            <input type="number" id="fire-return-vol" step="0.01" value="${s.return_volatility_percent}">
                        </div>
                        <div class="form-group">
                            <label>Standardavvik inflasjon (%)</label>
                            <input type="number" id="fire-inflation-vol" step="0.01" value="${s.inflation_volatility_percent}">
                        </div>
                        <div class="form-group">
                            <label>Leser forbruk og inntekt fra siste (mnd)</label>
                            <input type="number" id="fire-lookback" min="1" max="120" value="${s.lookback_months}">
                        </div>
                    </div>
                    <p class="subtitle">Standardavvikene brukes ikke av denne beregningen. De står klare til
                       Monte Carlo-simuleringen, som kjører den samme modellen med trukket avkastning.</p>

                    <h3>Fellesregnskap</h3>
                    <div class="settlement-columns">
                        <div class="form-group">
                            <label>Hent forbruk fra</label>
                            <select id="fire-shared-ledger">
                                <option value="">Ingen</option>
                                ${otherLedgers.map(l => `<option value="${l.id}" ${l.id === s.shared_ledger_id ? 'selected' : ''}>${escapeHtml(l.name)}</option>`).join('')}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Din andel (%)</label>
                            <input type="number" id="fire-shared-share" step="0.01" min="0" max="100" value="${s.shared_share_percent ?? ''}">
                        </div>
                    </div>

                    <h3>Formuesskatt</h3>
                    <div class="settlement-columns">
                        <div class="form-group">
                            <label>Bunnfradrag</label>
                            <input type="number" id="fire-wt-threshold" step="1000" value="${s.wealth_tax_threshold}">
                        </div>
                        <div class="form-group">
                            <label>Sats (%)</label>
                            <input type="number" id="fire-wt-rate" step="0.001" value="${s.wealth_tax_rate_percent}">
                        </div>
                        <div class="form-group">
                            <label>Trinn 2 fra</label>
                            <input type="number" id="fire-wt-threshold2" step="1000" value="${s.wealth_tax_step2_threshold ?? ''}">
                        </div>
                        <div class="form-group">
                            <label>Sats trinn 2 (%)</label>
                            <input type="number" id="fire-wt-rate2" step="0.001" value="${s.wealth_tax_step2_rate_percent ?? ''}">
                        </div>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="fire-wt-index" ${s.wealth_tax_index_threshold ? 'checked' : ''}>
                            Bunnfradraget følger lønnsveksten</label>
                    </div>

                    <h3>Holdes utenfor forbruk og inntekt</h3>
                    <p class="subtitle">Motkontoer for verdiendring er alltid utenfor - avkastningen ligger
                       allerede i forventningen over.</p>
                    <div class="settlement-exclude-list">
                        ${expenseAndRevenue.map(a => `
                            <label class="settlement-exclude-item"><input type="checkbox" class="fire-exclude" value="${a.id}"
                                ${(s.excluded_account_ids || []).includes(a.id) ? 'checked' : ''}>
                                ${a.account_number} ${escapeHtml(a.account_name)}</label>`).join('')}
                    </div>

                    <button type="submit" class="btn btn-primary">Lagre forutsetninger</button>
                </form>
            </div>
        `;
    }

    // ------------------------------------------------------------------
    // Events
    // ------------------------------------------------------------------
    bind() {
        const form = document.getElementById('fire-settings-form');
        if (form) form.addEventListener('submit', (e) => { e.preventDefault(); this.save(); });

        const run = document.getElementById('fire-test-run');
        if (run) run.addEventListener('click', () => {
            this.testDate = document.getElementById('fire-test-date').value || null;
            this.init();
        });
        const clear = document.getElementById('fire-test-clear');
        if (clear) clear.addEventListener('click', () => { this.testDate = null; this.init(); });

        const add = document.getElementById('fire-add-obligation');
        if (add) add.addEventListener('click', () => this.showObligationModal(null));

        document.querySelectorAll('[data-edit-obligation]').forEach(btn => {
            btn.addEventListener('click', () => this.showObligationModal(
                parseInt(btn.dataset.editObligation, 10)));
        });
        document.querySelectorAll('[data-delete-obligation]').forEach(btn => {
            btn.addEventListener('click', () => this.deleteObligation(
                parseInt(btn.dataset.deleteObligation, 10)));
        });
    }

    async save() {
        const num = (id) => {
            const v = document.getElementById(id).value;
            return v === '' ? null : parseFloat(v);
        };
        const payload = {
            is_enabled: document.getElementById('fire-enabled').checked,
            birth_date: document.getElementById('fire-birth-date').value || null,
            horizon_age: parseInt(document.getElementById('fire-horizon-age').value, 10) || 95,
            target_retirement_date: document.getElementById('fire-target-date').value || null,
            swr_percent: num('fire-swr') ?? 4,
            inflation_percent: num('fire-inflation') ?? 2.5,
            expected_return_percent: num('fire-return') ?? 7,
            return_volatility_percent: num('fire-return-vol') ?? 15,
            inflation_volatility_percent: num('fire-inflation-vol') ?? 1.5,
            lookback_months: parseInt(document.getElementById('fire-lookback').value, 10) || 12,
            shared_ledger_id: parseInt(document.getElementById('fire-shared-ledger').value, 10) || null,
            shared_share_percent: num('fire-shared-share'),
            wealth_tax_threshold: num('fire-wt-threshold') ?? 0,
            wealth_tax_rate_percent: num('fire-wt-rate') ?? 0,
            wealth_tax_step2_threshold: num('fire-wt-threshold2'),
            wealth_tax_step2_rate_percent: num('fire-wt-rate2'),
            wealth_tax_index_threshold: document.getElementById('fire-wt-index').checked,
            excluded_account_ids: [...document.querySelectorAll('.fire-exclude:checked')]
                .map(cb => parseInt(cb.value, 10)),
        };
        try {
            await api.updateFireSettings(payload);
            showSuccess('Forutsetningene er lagret');
            await this.init();
        } catch (error) {
            showError(error.message);
        }
    }

    showObligationModal(id) {
        const ob = id ? (this.settings.obligations || []).find(o => o.id === id) : null;
        const liabilities = (this.accounts || [])
            .filter(a => a.account_type === 'LIABILITY' || a.account_type === 'EXPENSE');

        showModal(ob ? 'Rediger forpliktelse' : 'Ny forpliktelse', `
            <form id="fire-obligation-form">
                <div class="form-group">
                    <label>Navn</label>
                    <input type="text" id="ob-name" value="${ob ? escapeHtml(ob.name) : ''}" required>
                </div>
                <div class="form-group">
                    <label>Type</label>
                    <select id="ob-kind">
                        ${Object.entries(KINDS).map(([k, v]) =>
                            `<option value="${k}" ${ob && ob.kind === k ? 'selected' : ''}>${v}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Per måned</label>
                    <input type="number" id="ob-monthly" step="0.01" value="${ob ? ob.monthly_amount : ''}" required>
                </div>
                <div class="form-group">
                    <label>Saldo (lån, valgfritt - gir utledet sluttdato)</label>
                    <input type="number" id="ob-balance" step="0.01" value="${ob && ob.balance !== null ? ob.balance : ''}">
                </div>
                <div class="form-group">
                    <label>Rente (%)</label>
                    <input type="number" id="ob-interest" step="0.0001" value="${ob && ob.interest_percent !== null ? ob.interest_percent : ''}">
                </div>
                <div class="form-group">
                    <label>Sluttdato (overstyrer utregningen)</label>
                    <input type="date" id="ob-end-date" value="${ob && ob.end_date ? ob.end_date : ''}">
                </div>
                <div class="form-group">
                    <label>Konto (valgfri)</label>
                    <select id="ob-account">
                        <option value="">Ingen</option>
                        ${liabilities.map(a => `<option value="${a.id}" ${ob && ob.account_id === a.id ? 'selected' : ''}>${a.account_number} ${escapeHtml(a.account_name)}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="ob-inflation" ${ob && ob.inflation_adjusted ? 'checked' : ''}>
                        Følger indeks (barnebidrag ja, fast lånetermin nei)</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="ob-frees" ${!ob || ob.frees_up_cash ? 'checked' : ''}>
                        Beløpet går til sparing når forpliktelsen tar slutt</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="ob-debt" ${!ob || ob.counts_as_debt ? 'checked' : ''}>
                        Teller som gjeld i formuesskatten</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="ob-active" ${!ob || ob.is_active ? 'checked' : ''}> Aktiv</label>
                </div>
                <button type="submit" class="btn btn-primary">Lagre</button>
            </form>
        `);

        document.getElementById('fire-obligation-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const val = (fid) => {
                const v = document.getElementById(fid).value;
                return v === '' ? null : parseFloat(v);
            };
            const payload = {
                name: document.getElementById('ob-name').value,
                kind: document.getElementById('ob-kind').value,
                account_id: parseInt(document.getElementById('ob-account').value, 10) || null,
                monthly_amount: val('ob-monthly') ?? 0,
                balance: val('ob-balance'),
                interest_percent: val('ob-interest'),
                end_date: document.getElementById('ob-end-date').value || null,
                inflation_adjusted: document.getElementById('ob-inflation').checked,
                frees_up_cash: document.getElementById('ob-frees').checked,
                counts_as_debt: document.getElementById('ob-debt').checked,
                is_active: document.getElementById('ob-active').checked,
            };
            try {
                if (ob) await api.updateFireObligation(ob.id, payload);
                else await api.createFireObligation(payload);
                closeModal();
                showSuccess('Forpliktelsen er lagret');
                await this.init();
            } catch (error) {
                showError(error.message);
            }
        });
    }

    async deleteObligation(id) {
        const ob = (this.settings.obligations || []).find(o => o.id === id);
        if (!confirm(`Slette ${ob ? ob.name : 'forpliktelsen'}?`)) return;
        try {
            await api.deleteFireObligation(id);
            showSuccess('Forpliktelsen er slettet');
            await this.init();
        } catch (error) {
            showError(error.message);
        }
    }
}

const fireManager = new FireManager();
window.fireManager = fireManager;
export default fireManager;
