import api from './api.js?v=25';
import { formatCurrency, showError, showSuccess, showModal, closeModal } from './utils.js?v=25';

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

function millions(value) {
    const m = Number(value) / 1e6;
    if (m === 0) return '0';
    return `${m.toFixed(m < 10 ? 1 : 0).replace('.', ',')} mill`;
}

function thousands(value) {
    return new Intl.NumberFormat('nb-NO', { maximumFractionDigits: 0 }).format(Number(value));
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
        this.costAccounts = null;
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
            // Expense accounts from the shared ledger too: a household
            // mortgage books its interest there, and that is the one link
            // that stops it being counted twice.
            this.costAccounts = this.settings.is_enabled
                ? await api.getFireCostAccounts() : [];
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
            ${this.result ? this.renderChart() : ''}
            ${this.result ? this.renderWarnings() : ''}
            ${this.renderObligations()}
            ${this.renderIncomeStreams()}
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
                        ${Number(n.pension_capital) > 0 ? `
                        <tr>
                            <td>Nåverdi av pensjonene, som kapitalen slipper å reise</td>
                            <td class="num">−${kr(n.pension_capital)}</td>
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

    // ------------------------------------------------------------------
    // The accumulation chart
    //
    // Capital is in millions and a year's spending in hundreds of
    // thousands, so they cannot share one axis. The right-hand axis is
    // therefore the left-hand one multiplied by the withdrawal rate: a
    // capital curve read against it *is* the four per cent line. That makes
    // the crossing with the spending curve a real one rather than an
    // artefact of scaling two axes against each other.
    // ------------------------------------------------------------------
    renderChart() {
        const chart = this.result.chart;
        if (!chart || chart.points.length < 2) return '';

        const swr = Number(chart.swr_percent) / 100;
        const pts = chart.points;
        const W = 960, H = 420;
        const M = { top: 16, right: 82, bottom: 34, left: 82 };
        const iw = W - M.left - M.right;
        const ih = H - M.top - M.bottom;

        // A cost drawn on the right axis is that cost divided by the
        // withdrawal rate when drawn on the left one. One scale, two readings.
        const asCapital = (annual) => (swr > 0 ? Number(annual) / swr : 0);
        const values = pts.flatMap(p => [
            Number(p.capital_saving),
            Number(p.capital_no_deposits),
            asCapital(p.annual_cost),
        ]);
        const rawMax = Math.max(...values, 1);
        const step = Math.pow(10, Math.floor(Math.log10(rawMax))) / 2;
        const yMax = Math.ceil(rawMax / step) * step;

        const x = (i) => M.left + (iw * i) / (pts.length - 1);
        const y = (v) => M.top + ih - (ih * Math.max(0, Number(v))) / yMax;
        const xOfYear = (year) => {
            const i = pts.findIndex(p => p.year === year);
            return i < 0 ? null : x(i);
        };
        const line = (pick) => pts.map((p, i) => `${x(i).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(' ');

        const ticks = 5;
        const grid = Array.from({ length: ticks + 1 }, (_, k) => {
            const v = (yMax * k) / ticks;
            const gy = y(v);
            return `
                <line x1="${M.left}" y1="${gy.toFixed(1)}" x2="${W - M.right}" y2="${gy.toFixed(1)}"
                      stroke="#e2e8f0" stroke-width="1"/>
                <text x="${M.left - 8}" y="${(gy + 4).toFixed(1)}" text-anchor="end"
                      font-size="11" fill="#64748b">${millions(v)}</text>
                <text x="${W - M.right + 8}" y="${(gy + 4).toFixed(1)}" text-anchor="start"
                      font-size="11" fill="#64748b">${thousands(v * swr)}</text>`;
        }).join('');

        // A label every fifth year, and always the last one
        const xLabels = pts.map((p, i) => {
            const last = i === pts.length - 1;
            if (p.year % 5 !== 0 && !last) return '';
            return `<text x="${x(i).toFixed(1)}" y="${H - 12}" text-anchor="middle"
                          font-size="11" fill="#64748b">${p.year}</text>`;
        }).join('');

        const marker = (year, colour, label) => {
            const mx = xOfYear(year);
            if (mx === null) return '';
            return `
                <line x1="${mx.toFixed(1)}" y1="${M.top}" x2="${mx.toFixed(1)}" y2="${M.top + ih}"
                      stroke="${colour}" stroke-width="1.5" stroke-dasharray="3 3"/>
                <text x="${(mx + 5).toFixed(1)}" y="${M.top + 14}" font-size="11" fill="${colour}">${label}</text>`;
        };

        const e = this.result.earliest;
        const fireYear = e ? Number(e.retirement_date.slice(0, 4)) : null;
        const hasPension = pts.some(p => Number(p.pension_income) > 0);

        return `
            <div class="card">
                <h2>Veien dit</h2>
                <div class="fire-chart">
                <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"
                     role="img" aria-label="Framskriving av kapital mot arlig forbruk">
                    ${grid}
                    ${xLabels}
                    ${fireYear ? marker(fireYear, '#10b981', `FIRE ${fireYear}`) : ''}
                    ${chart.crossing_year ? marker(chart.crossing_year, '#2563eb', `4 % dekker ${chart.crossing_year}`) : ''}
                    <polyline fill="none" stroke="#2563eb" stroke-width="2.5"
                              points="${line(p => p.capital_saving)}"/>
                    <polyline fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="6 4"
                              points="${line(p => p.capital_no_deposits)}"/>
                    <polyline fill="none" stroke="#ef4444" stroke-width="2.5"
                              points="${line(p => asCapital(p.annual_cost))}"/>
                    ${hasPension ? `
                    <polyline fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="2 3"
                              points="${line(p => asCapital(p.annual_need))}"/>` : ''}
                    <line x1="${M.left}" y1="${M.top + ih}" x2="${W - M.right}" y2="${M.top + ih}"
                          stroke="#94a3b8" stroke-width="1"/>
                </svg>
                </div>
                <ul class="fire-legend">
                    <li><span style="background:#2563eb"></span>Kapital med dagens sparing</li>
                    <li><span style="background:#94a3b8"></span>Uten flere innskudd, bare avkastning</li>
                    <li><span style="background:#ef4444"></span>Forbruk, forpliktelser og formuesskatt</li>
                    ${hasPension ? '<li><span style="background:#f59e0b"></span>Det kapitalen selv må dekke, etter pensjon</li>' : ''}
                </ul>
                <p class="subtitle">
                    Venstre akse er kapital, høyre akse er ${pct(chart.swr_percent)} av den.
                    De blå og grå kurvene lest mot høyre akse <em>er</em> ${pct(chart.swr_percent)}-linjen,
                    så der den krysser den røde, bærer kapitalen forbruket av seg selv.
                    ${chart.crossing_year
                        ? `Det skjer i ${chart.crossing_year}, når du er ${chart.crossing_age} år.`
                        : 'Det skjer ikke innenfor beregningen.'}
                </p>
                <p class="subtitle">
                    Bare kapital du kan ta ut er med. Pensjonskapital som er bundet til en
                    alder teller ikke, fordi ${pct(chart.swr_percent)} av noe du ikke kommer til
                    ikke betaler regninger.
                    ${fireYear ? `Den grønne streken er den tidligste datoen beregningen finner (${fireYear}):
                       den spør om pengene <em>rekker</em> til ${this.result.assumptions.horizon_age} år,
                       ikke om de varer evig, og kommer derfor tidligere.` : ''}
                </p>
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
            const inn = Number(b.annual_contribution) > 0
                ? `, ${thousands(b.annual_contribution)}/år inn` : '';
            if (b.unlock_age && b.payout_years) {
                return `Bundet til ${b.unlock_age}, utbetales over ${b.payout_years} år${inn}`;
            }
            if (b.unlock_age) return `Bundet til ${b.unlock_age}${inn}`;
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
        const byId = new Map((this.costAccounts || []).map(a => [a.id, a]));
        const costName = (accountId) => {
            const a = accountId ? byId.get(accountId) : null;
            return a ? `${a.account_number} ${escapeHtml(a.account_name)}`
                     : '<span class="subtitle">Ikke koblet</span>';
        };
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
                    <thead><tr><th>Navn</th><th>Type</th><th class="num">Per måned</th><th>Slutter</th><th>Bokføres på</th><th></th></tr></thead>
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
                                <td>${costName(ob.cost_account_id)}</td>
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

    renderIncomeStreams() {
        const list = (this.settings.income_streams) || [];
        return `
            <div class="card">
                <div class="view-header">
                    <h2>Pensjon som utbetales</h2>
                    <button class="btn btn-sm btn-primary" id="fire-add-stream">Legg til</button>
                </div>
                <p class="subtitle">Folketrygd og tjenestepensjon er ingen saldo du eier, men en
                   utbetaling som starter på en bursdag. Den kan ikke brukes tidlig og skattlegges
                   ikke som formue, så den hører hjemme i kontantstrømmen og ikke blant kontoene.
                   Beløpet er i dagens kroner, etter skatt. Hent tallene fra nav.no og spk.no.</p>
                ${list.length ? `
                <table class="table">
                    <thead><tr><th>Navn</th><th class="num">Per måned</th><th>Fra alder</th><th>Til alder</th><th>Indeks</th><th></th></tr></thead>
                    <tbody>
                        ${list.map(st => `
                            <tr${st.is_active ? '' : ' class="fire-off"'}>
                                <td>${escapeHtml(st.name)}${st.is_active ? '' : ' (av)'}</td>
                                <td class="num">${kr(st.monthly_amount)}</td>
                                <td>${st.start_age}</td>
                                <td>${st.end_age ?? 'Livsvarig'}</td>
                                <td>${st.inflation_adjusted ? 'Ja' : 'Nei'}</td>
                                <td class="num">
                                    <button class="btn btn-sm btn-secondary" data-edit-stream="${st.id}">Rediger</button>
                                    <button class="btn btn-sm btn-secondary" data-delete-stream="${st.id}">Slett</button>
                                </td>
                            </tr>`).join('')}
                    </tbody>
                </table>` : '<p>Ingen registrert. Uten disse ser planen dyrere ut enn den er.</p>'}
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
                            <th class="num">Pensjon</th>
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
                                <td class="num">${Number(r.pension_income) ? kr(r.pension_income) : '–'}</td>
                                <td class="num">${Number(r.saved) ? kr(r.saved) : '–'}</td>
                                <td class="num">${Number(r.withdrawn) ? kr(r.withdrawn) : '–'}</td>
                            </tr>`).join('')}
                    </tbody>
                </table>
                </div>
                <p class="subtitle">Alle beløp i dagens kroner. Første og siste rad dekker
                   et delår. Uttak skjer fra den tyngst formuesbeskattede potten først, så
                   pensjonskapital som ikke teller i formuen blir stående lengst.</p>
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

        const addStream = document.getElementById('fire-add-stream');
        if (addStream) addStream.addEventListener('click', () => this.showStreamModal(null));

        document.querySelectorAll('[data-edit-stream]').forEach(btn => {
            btn.addEventListener('click', () => this.showStreamModal(
                parseInt(btn.dataset.editStream, 10)));
        });
        document.querySelectorAll('[data-delete-stream]').forEach(btn => {
            btn.addEventListener('click', () => this.deleteStream(
                parseInt(btn.dataset.deleteStream, 10)));
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
            .filter(a => a.account_type === 'LIABILITY');
        const costs = this.costAccounts || [];
        const multiLedger = new Set(costs.map(a => a.ledger_id)).size > 1;

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
                    <label>Saldokonto (valgfri)</label>
                    <select id="ob-account">
                        <option value="">Ingen</option>
                        ${liabilities.map(a => `<option value="${a.id}" ${ob && ob.account_id === a.id ? 'selected' : ''}>${a.account_number} ${escapeHtml(a.account_name)}</option>`).join('')}
                    </select>
                    <small class="subtitle">Gjeldskontoen restgjelden leses fra, så lånet
                        følger regnskapet. La saldofeltet over stå tomt hvis du bruker denne.</small>
                </div>
                <div class="form-group">
                    <label>Kostnadskonto (valgfri)</label>
                    <select id="ob-cost-account">
                        <option value="">Ingen</option>
                        ${costs.map(a => `<option value="${a.id}" ${ob && ob.cost_account_id === a.id ? 'selected' : ''}>${a.account_number} ${escapeHtml(a.account_name)}${multiLedger ? ` — ${escapeHtml(a.ledger_name)}` : ''}</option>`).join('')}
                    </select>
                    <small class="subtitle">Kontoen kostnaden allerede bokføres på — rentene på
                        et lån, utbetalingen av et bidrag. Den holdes utenfor forbruket, ellers
                        telles den samme kronen to ganger.</small>
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
                cost_account_id: parseInt(document.getElementById('ob-cost-account').value, 10) || null,
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

    showStreamModal(id) {
        const st = id ? (this.settings.income_streams || []).find(x => x.id === id) : null;
        showModal(st ? 'Rediger pensjon' : 'Ny pensjon', `
            <form id="fire-stream-form">
                <div class="form-group">
                    <label>Navn</label>
                    <input type="text" id="st-name" value="${st ? escapeHtml(st.name) : ''}"
                           placeholder="Folketrygd, SPK, …" required>
                </div>
                <div class="form-group">
                    <label>Per måned, i dagens kroner etter skatt</label>
                    <input type="number" id="st-monthly" step="0.01" value="${st ? st.monthly_amount : ''}" required>
                </div>
                <div class="form-group">
                    <label>Fra alder</label>
                    <input type="number" id="st-start" min="0" max="110" value="${st ? st.start_age : 67}" required>
                </div>
                <div class="form-group">
                    <label>Til alder (tomt = livsvarig)</label>
                    <input type="number" id="st-end" min="0" max="110" value="${st && st.end_age !== null ? st.end_age : ''}">
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="st-inflation" ${!st || st.inflation_adjusted ? 'checked' : ''}>
                        Følger indeks (folketrygden ja, en fast livrente nei)</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="st-active" ${!st || st.is_active ? 'checked' : ''}> Aktiv</label>
                </div>
                <button type="submit" class="btn btn-primary">Lagre</button>
            </form>
        `);

        document.getElementById('fire-stream-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const end = document.getElementById('st-end').value;
            const payload = {
                name: document.getElementById('st-name').value,
                monthly_amount: parseFloat(document.getElementById('st-monthly').value) || 0,
                start_age: parseInt(document.getElementById('st-start').value, 10),
                end_age: end === '' ? null : parseInt(end, 10),
                inflation_adjusted: document.getElementById('st-inflation').checked,
                is_active: document.getElementById('st-active').checked,
            };
            try {
                if (st) await api.updateFireIncomeStream(st.id, payload);
                else await api.createFireIncomeStream(payload);
                closeModal();
                showSuccess('Pensjonen er lagret');
                await this.init();
            } catch (error) {
                showError(error.message);
            }
        });
    }

    async deleteStream(id) {
        const st = (this.settings.income_streams || []).find(x => x.id === id);
        if (!confirm(`Slette ${st ? st.name : 'pensjonen'}?`)) return;
        try {
            await api.deleteFireIncomeStream(id);
            showSuccess('Pensjonen er slettet');
            await this.init();
        } catch (error) {
            showError(error.message);
        }
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
