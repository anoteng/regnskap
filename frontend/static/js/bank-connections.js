import api from './api.js';
import { showModal, closeModal, showError, showSuccess, formatDate } from './utils.js';

class BankConnectionsManager {
    constructor() {
        this.connections = [];
        this.providers = [];
        this.bankAccounts = [];
        this.initialized = false;
    }

    async init() {
        try {
            // Check subscription - bank integration requires Premium
            const sub = await api.request('/auth/me/subscription');
            if (!sub || sub.tier !== 'PREMIUM') {
                this.showUpgradeInfo();
                return;
            }

            // Load data
            await this.loadBankAccounts();
            await this.loadProviders();
            await this.loadConnections();

            if (!this.initialized) {
                this.setupEventListeners();
                this.initialized = true;
            }

            // Check for OAuth callback status
            this.checkOAuthCallback();
        } catch (error) {
            console.error('Bank connections init error:', error);
            showError(`Kunne ikke laste data: ${error.message}`);
        }
    }

    showUpgradeInfo() {
        // Hide the connect button and subtitle
        const connectBtn = document.getElementById('connect-bank-btn');
        if (connectBtn) connectBtn.style.display = 'none';
        const subtitle = document.querySelector('#bank-connections-view .subtitle');
        if (subtitle) subtitle.style.display = 'none';
        const syncProgress = document.getElementById('sync-progress');
        if (syncProgress) syncProgress.style.display = 'none';
        const helpBox = document.getElementById('connection-help');
        if (helpBox) helpBox.style.display = 'none';

        const container = document.getElementById('connections-list');
        container.innerHTML = `
            <div class="card" style="max-width: 600px; margin: 2rem auto; text-align: center; padding: 2rem;">
                <h2 style="margin-bottom: 1rem;">Automatisk banksynkronisering</h2>
                <p style="margin-bottom: 1.5rem; color: #666;">
                    Med Premium-abonnementet kan du koble bankkontoen din direkte til regnskapet
                    og f\u00e5 transaksjoner importert automatisk.
                </p>

                <div style="background: #f0f9ff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; text-align: left;">
                    <h3 style="margin-bottom: 0.75rem;">Premium inkluderer:</h3>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        <li style="padding: 0.4rem 0;">&#10003; Alt i Basic (vedlegg, CSV-import)</li>
                        <li style="padding: 0.4rem 0;">&#10003; Automatisk banksynkronisering</li>
                        <li style="padding: 0.4rem 0;">&#10003; St\u00f8tte for flere bankkontoer</li>
                        <li style="padding: 0.4rem 0;">&#10003; Duplikatdeteksjon ved import</li>
                    </ul>
                </div>

                <div style="background: #fffbeb; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
                    <p style="margin: 0; color: #92400e; font-size: 0.9rem;">
                        Bankintegrasjon er under utvikling og er forel\u00f8pig ikke tilgjengelig for nye abonnenter.
                        Vi jobber med \u00e5 f\u00e5 dette klart \u2013 f\u00f8lg med!
                    </p>
                </div>

                <p style="color: #666; font-size: 0.875rem;">
                    Kontakt administrator for mer informasjon.
                </p>
            </div>
        `;
    }

    setupEventListeners() {
        const connectBtn = document.getElementById('connect-bank-btn');
        if (connectBtn) {
            connectBtn.addEventListener('click', () => {
                this.showConnectBankModal();
            });
        }
    }

    async loadBankAccounts() {
        try {
            this.bankAccounts = await api.getBankAccounts();
        } catch (error) {
            console.error('Error loading bank accounts:', error);
        }
    }

    async loadProviders() {
        try {
            this.providers = await api.request('/bank-connections/providers');
        } catch (error) {
            console.error('Error loading providers:', error);
        }
    }

    async loadConnections() {
        try {
            this.connections = await api.request('/bank-connections/');
            this.renderConnections();
        } catch (error) {
            console.error('Error loading connections:', error);
            showError('Kunne ikke laste bankkoblinger');
        }
    }

    renderConnections() {
        const container = document.getElementById('connections-list');

        if (this.connections.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #666;">
                    <h3>Ingen bankkoblinger</h3>
                    <p>Koble til banken din for automatisk synkronisering av transaksjoner</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.connections.map(conn => this.renderConnectionCard(conn)).join('');
    }

    renderConnectionCard(connection) {
        const bankAccount = this.bankAccounts.find(ba => ba.id === connection.bank_account_id);
        const provider = this.providers.find(p => p.id === connection.provider_id);

        const statusClass = {
            'ACTIVE': 'status-active',
            'ERROR': 'status-error',
            'EXPIRED': 'status-expired',
            'DISCONNECTED': 'status-error'
        }[connection.status] || 'status-error';

        const statusText = {
            'ACTIVE': 'Aktiv',
            'ERROR': 'Feil',
            'EXPIRED': 'Utl\u00f8pt',
            'DISCONNECTED': 'Frakoblet'
        }[connection.status] || connection.status;

        const lastSync = connection.last_sync_at
            ? `Sist synkronisert: ${this.formatRelativeTime(connection.last_sync_at)}`
            : 'Aldri synkronisert';

        return `
            <div class="connection-card">
                <div class="connection-info">
                    <h3>${provider?.display_name || 'Ukjent bank'}</h3>
                    <p><strong>Konto:</strong> ${bankAccount?.name || 'Ukjent'}</p>
                    <p><strong>IBAN:</strong> ${connection.external_account_iban || 'N/A'}</p>
                    <p><small>${lastSync}</small></p>
                </div>
                <div class="connection-status">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                    <div class="connection-actions">
                        ${connection.status !== 'DISCONNECTED' ? `
                            <button class="btn btn-sm btn-primary" onclick="bankConnectionsManager.syncConnection(${connection.id})">
                                Synkroniser
                            </button>
                            <button class="btn btn-sm btn-warning" onclick="bankConnectionsManager.reauthorizeConnection(${connection.id})" title="Fornye tilkobling">
                                Re-autoriser
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-secondary" onclick="bankConnectionsManager.showConnectionDetails(${connection.id})">
                            Detaljer
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="bankConnectionsManager.disconnectBank(${connection.id})">
                            Koble fra
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    async showConnectBankModal() {
        if (this.bankAccounts.length === 0) {
            showError('Du m\u00e5 f\u00f8rst opprette en bankkonto i systemet f\u00f8r du kan koble til bank-API');
            return;
        }

        if (this.providers.length === 0) {
            showError('Ingen bank-providers tilgjengelig. Kontakt administrator.');
            return;
        }

        const content = `
            <h2>Koble til bank</h2>

            <div class="form-group">
                <label for="connect-bank-account">Velg bankkonto i regnskapet</label>
                <select id="connect-bank-account" class="form-control">
                    <option value="">-- Velg konto --</option>
                    ${this.bankAccounts.map(ba => `
                        <option value="${ba.id}">${ba.name} (${ba.account_number || 'Ingen kontonr.'})</option>
                    `).join('')}
                </select>
            </div>

            <div class="form-group">
                <label for="connect-provider">Bank-provider</label>
                <select id="connect-provider" class="form-control">
                    ${this.providers.map((p, i) => `
                        <option value="${p.id}" ${i === 0 ? 'selected' : ''}>${p.display_name} ${p.environment === 'SANDBOX' ? '(Test)' : ''}</option>
                    `).join('')}
                </select>
            </div>

            <div class="form-group">
                <label for="connect-country">Land</label>
                <select id="connect-country" class="form-control" onchange="bankConnectionsManager.onCountryChanged()">
                    <option value="">Laster land...</option>
                </select>
            </div>

            <div class="form-group">
                <label for="connect-bank">Bank</label>
                <select id="connect-bank" class="form-control" disabled>
                    <option value="">-- Velg land f\u00f8rst --</option>
                </select>
            </div>

            <div class="form-group">
                <label for="connect-initial-sync-date">Hent transaksjoner fra dato (valgfritt)</label>
                <input type="date" id="connect-initial-sync-date" class="form-control"
                       value="2026-01-01"
                       max="${new Date().toISOString().split('T')[0]}">
                <small>Begrenser historikken som hentes ved f\u00f8rste synkronisering.</small>
            </div>

            <div style="margin-top: 1.5rem; padding: 1rem; background: #f0f9ff; border-radius: 4px;">
                <p style="margin: 0; font-size: 0.9rem;">
                    <strong>Merk:</strong> Du vil bli omdirigert til bankens p\u00e5loggingsside for \u00e5 autorisere tilgang.
                    Vi lagrer aldri bankens p\u00e5loggingsinformasjon.
                </p>
            </div>

            <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
                <button class="btn btn-primary" id="connect-submit-btn" onclick="bankConnectionsManager.initiateConnection()">
                    Koble til
                </button>
                <button class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
            </div>
        `;

        showModal('Koble til bank', content);

        // Load ASPSPs
        await this.loadAspsps();
    }

    async loadAspsps() {
        const countrySelect = document.getElementById('connect-country');
        const bankSelect = document.getElementById('connect-bank');

        try {
            countrySelect.innerHTML = '<option value="">Laster...</option>';
            const data = await api.getAspsps();
            this.allAspsps = data.aspsps || [];

            const countryNames = {
                'NO': 'Norge', 'SE': 'Sverige', 'DK': 'Danmark', 'FI': 'Finland',
                'DE': 'Tyskland', 'GB': 'Storbritannia', 'FR': 'Frankrike',
                'NL': 'Nederland', 'ES': 'Spania', 'IT': 'Italia',
                'AT': '\u00d8sterrike', 'BE': 'Belgia', 'PT': 'Portugal',
                'PL': 'Polen', 'IE': 'Irland', 'EE': 'Estland',
                'LV': 'Latvia', 'LT': 'Litauen', 'CZ': 'Tsjekkia',
                'SK': 'Slovakia', 'HU': 'Ungarn', 'RO': 'Romania',
                'BG': 'Bulgaria', 'HR': 'Kroatia', 'SI': 'Slovenia',
                'LU': 'Luxembourg', 'MT': 'Malta', 'CY': 'Kypros',
                'GR': 'Hellas', 'IS': 'Island', 'CH': 'Sveits'
            };

            const countries = data.countries || [];
            countrySelect.innerHTML = '<option value="">-- Velg land --</option>' +
                countries.map(c =>
                    `<option value="${c}" ${c === 'NO' ? 'selected' : ''}>${countryNames[c] || c} (${c})</option>`
                ).join('');

            if (countries.includes('NO')) {
                countrySelect.value = 'NO';
                this.onCountryChanged();
            }

        } catch (error) {
            console.error('Error loading ASPSPs:', error);
            countrySelect.innerHTML = '<option value="">Kunne ikke laste land</option>';
            bankSelect.innerHTML = '<option value="">Feil ved lasting</option>';
        }
    }

    onCountryChanged() {
        const country = document.getElementById('connect-country').value;
        const bankSelect = document.getElementById('connect-bank');

        if (!country || !this.allAspsps) {
            bankSelect.innerHTML = '<option value="">-- Velg land f\u00f8rst --</option>';
            bankSelect.disabled = true;
            return;
        }

        const banksInCountry = this.allAspsps.filter(a => a.country === country);
        banksInCountry.sort((a, b) => a.name.localeCompare(b.name));

        bankSelect.innerHTML = '<option value="">-- Velg bank --</option>' +
            banksInCountry.map(b =>
                `<option value="${b.country}_${b.name}">${b.name}${b.beta ? ' (beta)' : ''}</option>`
            ).join('');
        bankSelect.disabled = false;
    }

    async initiateConnection() {
        const bankAccountId = document.getElementById('connect-bank-account').value;
        const providerId = document.getElementById('connect-provider').value;
        const bankValue = document.getElementById('connect-bank').value;
        const initialSyncDate = document.getElementById('connect-initial-sync-date').value;

        if (!bankAccountId) { showError('Velg en bankkonto'); return; }
        if (!providerId) { showError('Velg en provider'); return; }
        if (!bankValue) { showError('Velg en bank'); return; }

        try {
            const submitBtn = document.getElementById('connect-submit-btn');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Kobler til...';

            const requestBody = {
                bank_account_id: parseInt(bankAccountId),
                provider_id: parseInt(providerId),
                external_bank_id: bankValue
            };

            if (initialSyncDate) {
                requestBody.initial_sync_from_date = initialSyncDate;
            }

            const response = await api.request('/bank-connections/connect', {
                method: 'POST',
                body: JSON.stringify(requestBody)
            });

            window.location.href = response.authorization_url;

        } catch (error) {
            console.error('Connection error:', error);
            showError('Kunne ikke starte tilkobling: ' + error.message);

            const submitBtn = document.getElementById('connect-submit-btn');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Koble til';
            }
        }
    }

    checkOAuthCallback() {
        const params = new URLSearchParams(window.location.search);
        const success = params.get('success');
        const error = params.get('error');
        const connectionId = params.get('connection_id');

        if (success === 'true' && connectionId) {
            showSuccess('Bank koblet til! Starter f\u00f8rste synkronisering...');
            // Clear URL params
            window.history.replaceState({}, document.title, window.location.pathname);
            // Trigger initial sync
            setTimeout(() => {
                this.syncConnection(parseInt(connectionId));
            }, 1000);
        } else if (error) {
            const message = params.get('message') || 'Ukjent feil';
            showError('Kunne ikke koble til bank: ' + message);
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }

    async syncConnection(connectionId) {
        const progressDiv = document.getElementById('sync-progress');
        const statusText = document.getElementById('sync-status-text');
        const resultDiv = document.getElementById('sync-result');

        progressDiv.classList.add('active');
        statusText.textContent = 'Synkroniserer transaksjoner...';
        resultDiv.style.display = 'none';

        try {
            const result = await api.request(`/bank-connections/${connectionId}/sync`, {
                method: 'POST'
            });

            statusText.textContent = 'Synkronisering fullf\u00f8rt!';
            resultDiv.innerHTML = `
                <div style="color: #065f46;">
                    Hentet ${result.transactions_fetched} transaksjoner<br>
                    Importert ${result.imported} nye<br>
                    ${result.duplicates} duplikater
                </div>
            `;
            resultDiv.style.display = 'block';

            await this.loadConnections();

            setTimeout(() => {
                progressDiv.classList.remove('active');
            }, 5000);

            if (result.imported > 0) {
                showSuccess(`${result.imported} nye transaksjoner lagt i posteringsk\u00f8en`);
            }

        } catch (error) {
            console.error('Sync error:', error);
            statusText.textContent = 'Synkronisering feilet';
            resultDiv.innerHTML = `<div style="color: #991b1b;">${error.message}</div>`;
            resultDiv.style.display = 'block';
        }
    }

    async reauthorizeConnection(connectionId) {
        const connection = this.connections.find(c => c.id === connectionId);
        if (!connection) { showError('Tilkobling ikke funnet'); return; }

        const bankAccount = this.bankAccounts.find(ba => ba.id === connection.bank_account_id);
        const provider = this.providers.find(p => p.id === connection.provider_id);

        if (!confirm(
            `Re-autorisere tilkobling?\n\nBank: ${provider?.display_name || 'Ukjent'}\nKonto: ${bankAccount?.name || 'Ukjent'}\n\nDu vil bli omdirigert til bankens p\u00e5loggingsside.`
        )) return;

        try {
            const result = await api.request(`/bank-connections/${connectionId}/reauthorize`, {
                method: 'POST'
            });
            window.location.href = result.authorization_url;
        } catch (error) {
            console.error('Reauthorization error:', error);
            showError(`Kunne ikke starte re-autorisering: ${error.message}`);
        }
    }

    async showConnectionDetails(connectionId) {
        try {
            const logs = await api.request(`/bank-connections/${connectionId}/logs?limit=10`);

            const content = `
                <h2>Synkroniseringshistorikk</h2>

                ${logs.length === 0 ? '<p>Ingen synkroniseringer enn\u00e5.</p>' : `
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Tidspunkt</th>
                                <th>Type</th>
                                <th>Status</th>
                                <th>Hentet</th>
                                <th>Importert</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${logs.map(log => `
                                <tr>
                                    <td>${formatDate(log.started_at)}</td>
                                    <td>${log.sync_type}</td>
                                    <td>
                                        <span class="badge ${log.sync_status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">
                                            ${log.sync_status}
                                        </span>
                                    </td>
                                    <td>${log.transactions_fetched}</td>
                                    <td>${log.transactions_imported}</td>
                                </tr>
                                ${log.error_message ? `
                                    <tr>
                                        <td colspan="5" style="background: #fee2e2; padding: 0.5rem;">
                                            <small>Feil: ${log.error_message}</small>
                                        </td>
                                    </tr>
                                ` : ''}
                            `).join('')}
                        </tbody>
                    </table>
                `}

                <button class="btn btn-secondary" onclick="closeModal()" style="margin-top: 1rem;">Lukk</button>
            `;

            showModal('Koblings-detaljer', content);

        } catch (error) {
            console.error('Error loading logs:', error);
            showError('Kunne ikke laste historikk');
        }
    }

    async disconnectBank(connectionId) {
        if (!confirm('Er du sikker p\u00e5 at du vil koble fra denne banken? Du kan koble til igjen senere.')) {
            return;
        }

        try {
            await api.request(`/bank-connections/${connectionId}`, {
                method: 'DELETE'
            });
            showSuccess('Bank frakoblet');
            await this.loadConnections();
        } catch (error) {
            console.error('Disconnect error:', error);
            showError('Kunne ikke koble fra bank: ' + error.message);
        }
    }

    formatRelativeTime(dateString) {
        let isoString = dateString.replace(' ', 'T');
        if (!isoString.endsWith('Z') && !isoString.includes('+')) {
            isoString += 'Z';
        }
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Akkurat n\u00e5';
        if (diffMins < 60) return `${diffMins} min siden`;
        if (diffHours < 24) return `${diffHours} timer siden`;
        if (diffDays < 7) return `${diffDays} dager siden`;
        return formatDate(dateString);
    }
}

const bankConnectionsManager = new BankConnectionsManager();
window.bankConnectionsManager = bankConnectionsManager;

export default bankConnectionsManager;
