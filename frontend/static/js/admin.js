import api from './api.js';
import { showModal, closeModal, showError, showSuccess, formatDate } from './utils.js';

class AdminManager {
    constructor() {
        this.users = [];
        this.plans = [];
        this.aiConfigs = [];
        this.aiUsageStats = [];
    }

    async init() {
        await this.loadStats();
        await this.loadPlans();
        await this.loadAIConfigs();
        await this.loadAIUsageStats();
        await this.loadUsers();
        this.renderPlans();
        this.renderAIConfigs();
        this.renderAIUsageStats();
        this.setupEventListeners();
    }

    setupEventListeners() {
        const searchInput = document.getElementById('admin-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterUsers(e.target.value);
            });
        }
    }

    async loadStats() {
        try {
            const stats = await api.request('/admin/stats');

            document.getElementById('admin-total-users').textContent = stats.total_users;
            document.getElementById('admin-active-users').textContent = stats.active_users;
            document.getElementById('admin-total-ledgers').textContent = stats.total_ledgers;
            document.getElementById('admin-active-subscriptions').textContent = stats.active_subscriptions;
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadPlans() {
        try {
            this.plans = await api.request('/admin/subscription-plans');
        } catch (error) {
            console.error('Error loading plans:', error);
        }
    }

    renderPlans() {
        const container = document.getElementById('admin-plans-list');
        if (!container) return;

        if (this.plans.length === 0) {
            container.innerHTML = '<p>Ingen abonnementsplaner funnet.</p>';
            return;
        }

        const html = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Navn</th>
                            <th>Tier</th>
                            <th>Pris (kr/mnd)</th>
                            <th>AI</th>
                            <th>Maks bilag</th>
                            <th>Maks opplastinger/mnd</th>
                            <th>Status</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.plans.map(plan => this.renderPlanRow(plan)).join('')}
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    }

    renderPlanRow(plan) {
        const statusBadge = plan.is_active
            ? '<span class="status-badge status-posted">Aktiv</span>'
            : '<span class="status-badge status-draft">Inaktiv</span>';

        const aiBadge = plan.ai_enabled
            ? '<span class="status-badge status-posted">✓</span>'
            : '<span class="status-badge status-draft">✗</span>';

        const maxDocs = plan.max_documents ? plan.max_documents : 'Ubegrenset';
        const maxUploads = plan.max_monthly_uploads ? plan.max_monthly_uploads : 'Ubegrenset';

        return `
            <tr>
                <td>${plan.name}</td>
                <td>${plan.tier}</td>
                <td>${plan.price_monthly}</td>
                <td>${aiBadge}</td>
                <td>${maxDocs}</td>
                <td>${maxUploads}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="adminManager.showPlanModal(${plan.id})">
                        Rediger
                    </button>
                </td>
            </tr>
        `;
    }

    async loadUsers(search = '') {
        try {
            const params = new URLSearchParams();
            if (search) params.append('search', search);

            this.users = await api.request(`/admin/users?${params}`);
            this.renderUsers(this.users);
        } catch (error) {
            console.error('Error loading users:', error);
            showError('Kunne ikke laste brukere: ' + error.message);
        }
    }

    filterUsers(search) {
        if (!search) {
            this.renderUsers(this.users);
            return;
        }

        const filtered = this.users.filter(user =>
            user.email.toLowerCase().includes(search.toLowerCase()) ||
            user.full_name.toLowerCase().includes(search.toLowerCase())
        );
        this.renderUsers(filtered);
    }

    renderUsers(users) {
        const container = document.getElementById('admin-users-list');

        if (users.length === 0) {
            container.innerHTML = '<p>Ingen brukere funnet.</p>';
            return;
        }

        const html = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Navn</th>
                            <th>E-post</th>
                            <th>Abonnement</th>
                            <th>Regnskap</th>
                            <th>Status</th>
                            <th>Opprettet</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${users.map(user => this.renderUserRow(user)).join('')}
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    }

    renderUserRow(user) {
        const statusBadge = user.is_active
            ? '<span class="status-badge status-posted">Aktiv</span>'
            : '<span class="status-badge status-draft">Inaktiv</span>';

        const adminBadge = user.is_admin
            ? '<span class="status-badge" style="background: #dbeafe; color: #1e40af;">Admin</span>'
            : '';

        const subscriptionText = user.has_subscription
            ? `${user.subscription_tier}${user.subscription_expires ? ' (utløper ' + formatDate(user.subscription_expires) + ')' : ''}`
            : 'Ingen';

        return `
            <tr>
                <td>${user.id}</td>
                <td>${user.full_name} ${adminBadge}</td>
                <td>${user.email}</td>
                <td>${subscriptionText}</td>
                <td>${user.ledger_count}</td>
                <td>${statusBadge}</td>
                <td>${formatDate(user.created_at)}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="adminManager.showUserModal(${user.id})">
                        Rediger
                    </button>
                </td>
            </tr>
        `;
    }

    async showUserModal(userId) {
        try {
            const user = await api.request(`/admin/users/${userId}`);

            const planOptions = this.plans.map(plan =>
                `<option value="${plan.id}" ${user.subscription && user.subscription.plan_id === plan.id ? 'selected' : ''}>
                    ${plan.name} - ${plan.price_monthly} kr/mnd
                </option>`
            ).join('');

            const content = `
                <h2>Rediger bruker: ${user.full_name}</h2>

                <div class="form-group">
                    <label>E-post</label>
                    <input type="email" id="edit-user-email" value="${user.email}">
                </div>

                <div class="form-group">
                    <label>Fullt navn</label>
                    <input type="text" id="edit-user-name" value="${user.full_name}">
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-user-active" ${user.is_active ? 'checked' : ''}>
                        Aktiv bruker
                    </label>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-user-admin" ${user.is_admin ? 'checked' : ''}>
                        Administrator
                    </label>
                </div>

                <hr style="margin: 2rem 0;">

                <h3>Abonnement</h3>

                ${user.subscription ? `
                    <div class="card" style="background: var(--background); margin-bottom: 1rem;">
                        <strong>Nåværende abonnement:</strong> ${user.subscription.plan_name} (${user.subscription.plan_tier})<br>
                        <strong>Status:</strong> ${user.subscription.status}<br>
                        <strong>Startet:</strong> ${formatDate(user.subscription.started_at)}<br>
                        ${user.subscription.expires_at ? `<strong>Utløper:</strong> ${formatDate(user.subscription.expires_at)}<br>` : ''}
                        ${user.subscription.is_free_forever ? '<strong style="color: var(--success-color);">✓ Gratis for alltid</strong><br>' : ''}
                        ${user.subscription.discount_percentage > 0 ? `<strong>Rabatt:</strong> ${user.subscription.discount_percentage}%<br>` : ''}
                        ${user.subscription.custom_price ? `<strong>Spesialpris:</strong> ${user.subscription.custom_price} kr/mnd<br>` : ''}
                    </div>
                ` : '<p>Ingen aktivt abonnement</p>'}

                <div class="form-group">
                    <label>Abonnementsplan</label>
                    <select id="edit-user-plan">
                        <option value="">Ingen abonnement</option>
                        ${planOptions}
                    </select>
                </div>

                <div class="form-group">
                    <label>Utløpsdato (blank = ingen utløp)</label>
                    <input type="date" id="edit-subscription-expires"
                        value="${user.subscription && user.subscription.expires_at ? user.subscription.expires_at.split('T')[0] : ''}">
                </div>

                <div class="form-group">
                    <label>Rabatt (%)</label>
                    <input type="number" id="edit-subscription-discount" min="0" max="100" step="1"
                        value="${user.subscription ? user.subscription.discount_percentage : 0}">
                    <small>0-100%. Sett til 100% for gratis tilgang.</small>
                </div>

                <div class="form-group">
                    <label>Spesialpris (kr/mnd)</label>
                    <input type="number" id="edit-subscription-custom-price" min="0" step="0.01"
                        value="${user.subscription && user.subscription.custom_price ? user.subscription.custom_price : ''}">
                    <small>Overstyrer standard pris hvis satt.</small>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-subscription-free-forever"
                            ${user.subscription && user.subscription.is_free_forever ? 'checked' : ''}>
                        Gratis for alltid
                    </label>
                </div>

                <div class="form-group">
                    <label>Admin-notater</label>
                    <textarea id="edit-subscription-notes" rows="3">${user.subscription ? user.subscription.admin_notes || '' : ''}</textarea>
                </div>

                <hr style="margin: 2rem 0;">

                <h3>Endre passord</h3>
                <div class="form-group">
                    <label>Nytt passord</label>
                    <input type="password" id="edit-user-password" placeholder="La stå tom for å beholde">
                </div>

                <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                    <button class="btn btn-primary" onclick="adminManager.saveUser(${userId})">Lagre endringer</button>
                    <button class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
                </div>
            `;

            showModal('Rediger bruker', content);
        } catch (error) {
            showError('Kunne ikke laste brukerdetaljer: ' + error.message);
        }
    }

    async saveUser(userId) {
        try {
            // Update user details
            const email = document.getElementById('edit-user-email').value;
            const full_name = document.getElementById('edit-user-name').value;
            const is_active = document.getElementById('edit-user-active').checked;
            const is_admin = document.getElementById('edit-user-admin').checked;

            await api.request(`/admin/users/${userId}`, {
                method: 'PATCH',
                body: JSON.stringify({ email, full_name, is_active, is_admin })
            });

            // Update password if provided
            const password = document.getElementById('edit-user-password').value;
            if (password) {
                await api.request(`/admin/users/${userId}/password`, {
                    method: 'POST',
                    body: JSON.stringify({ new_password: password })
                });
            }

            // Update subscription
            const planId = document.getElementById('edit-user-plan').value;
            if (planId) {
                const expiresAt = document.getElementById('edit-subscription-expires').value || null;
                const discountPercentage = parseFloat(document.getElementById('edit-subscription-discount').value) || 0;
                const customPrice = document.getElementById('edit-subscription-custom-price').value || null;
                const isFreeForever = document.getElementById('edit-subscription-free-forever').checked;
                const adminNotes = document.getElementById('edit-subscription-notes').value || null;

                await api.request(`/admin/users/${userId}/subscription`, {
                    method: 'POST',
                    body: JSON.stringify({
                        plan_id: parseInt(planId),
                        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
                        discount_percentage: discountPercentage,
                        custom_price: customPrice ? parseFloat(customPrice) : null,
                        is_free_forever: isFreeForever,
                        admin_notes: adminNotes
                    })
                });
            }

            closeModal();
            showSuccess('Bruker oppdatert!');
            await this.loadStats();
            await this.loadUsers();
        } catch (error) {
            showError('Kunne ikke lagre endringer: ' + error.message);
        }
    }

    async showPlanModal(planId) {
        try {
            const plan = this.plans.find(p => p.id === planId);
            if (!plan) {
                showError('Kunne ikke finne abonnementsplan');
                return;
            }

            const content = `
                <h2>Rediger abonnementsplan: ${plan.name}</h2>

                <div class="form-group">
                    <label>Navn</label>
                    <input type="text" id="edit-plan-name" value="${plan.name}">
                </div>

                <div class="form-group">
                    <label>Tier (kan ikke endres)</label>
                    <input type="text" value="${plan.tier}" disabled>
                </div>

                <div class="form-group">
                    <label>Beskrivelse</label>
                    <textarea id="edit-plan-description" rows="3">${plan.description || ''}</textarea>
                </div>

                <div class="form-group">
                    <label>Pris per måned (kr)</label>
                    <input type="number" id="edit-plan-price" min="0" step="0.01" value="${plan.price_monthly}">
                </div>

                <div class="form-group">
                    <label>Funksjoner (JSON-array)</label>
                    <textarea id="edit-plan-features" rows="4">${plan.features || '[]'}</textarea>
                    <small>Format: ["Funksjon 1", "Funksjon 2", ...]</small>
                </div>

                <hr style="margin: 2rem 0;">

                <h3>AI-funksjoner</h3>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-plan-ai-enabled" ${plan.ai_enabled ? 'checked' : ''}>
                        AI-funksjoner aktivert
                    </label>
                    <small>Gir tilgang til AI-analyse av kvitteringer og posteringsforslag</small>
                </div>

                <div class="form-group">
                    <label>Maksimalt antall AI-operasjoner per måned</label>
                    <input type="number" id="edit-plan-max-ai-operations" min="0" step="1"
                        value="${plan.max_ai_operations_per_month || ''}">
                    <small>Antall AI-operasjoner per måned (0 eller blank = ubegrenset)</small>
                </div>

                <hr style="margin: 2rem 0;">

                <h3>Begrensninger</h3>
                <small>La stå tom eller 0 for ubegrenset</small>

                <div class="form-group">
                    <label>Maksimalt antall bilag totalt</label>
                    <input type="number" id="edit-plan-max-documents" min="0" step="1"
                        value="${plan.max_documents || ''}">
                    <small>Totalt antall bilag/kvitteringer som kan lagres (0 eller blank = ubegrenset)</small>
                </div>

                <div class="form-group">
                    <label>Maksimalt antall opplastinger per måned</label>
                    <input type="number" id="edit-plan-max-uploads" min="0" step="1"
                        value="${plan.max_monthly_uploads || ''}">
                    <small>Antall nye opplastinger per måned (0 eller blank = ubegrenset)</small>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-plan-active" ${plan.is_active ? 'checked' : ''}>
                        Aktiv plan
                    </label>
                </div>

                <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                    <button class="btn btn-primary" onclick="adminManager.savePlan(${planId})">Lagre endringer</button>
                    <button class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
                </div>
            `;

            showModal('Rediger abonnementsplan', content);
        } catch (error) {
            showError('Kunne ikke laste plandetaljer: ' + error.message);
        }
    }

    async savePlan(planId) {
        try {
            const name = document.getElementById('edit-plan-name').value;
            const description = document.getElementById('edit-plan-description').value;
            const price_monthly = parseFloat(document.getElementById('edit-plan-price').value);
            const features = document.getElementById('edit-plan-features').value;
            const ai_enabled = document.getElementById('edit-plan-ai-enabled').checked;
            const max_ai_operations = document.getElementById('edit-plan-max-ai-operations').value;
            const max_documents = document.getElementById('edit-plan-max-documents').value;
            const max_monthly_uploads = document.getElementById('edit-plan-max-uploads').value;
            const is_active = document.getElementById('edit-plan-active').checked;

            // Validate features JSON
            try {
                JSON.parse(features);
            } catch (e) {
                showError('Funksjoner må være gyldig JSON-format');
                return;
            }

            await api.request(`/admin/subscription-plans/${planId}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    name,
                    description,
                    price_monthly,
                    features,
                    ai_enabled,
                    max_ai_operations_per_month: max_ai_operations ? parseInt(max_ai_operations) : null,
                    max_documents: max_documents ? parseInt(max_documents) : null,
                    max_monthly_uploads: max_monthly_uploads ? parseInt(max_monthly_uploads) : null,
                    is_active
                })
            });

            closeModal();
            showSuccess('Abonnementsplan oppdatert!');
            await this.loadPlans();
            this.renderPlans();
        } catch (error) {
            showError('Kunne ikke lagre endringer: ' + error.message);
        }
    }

    async loadAIConfigs() {
        try {
            this.aiConfigs = await api.request('/admin/ai-config');
        } catch (error) {
            console.error('Error loading AI configs:', error);
        }
    }

    renderAIConfigs() {
        const container = document.getElementById('admin-ai-configs-list');
        if (!container) return;

        if (this.aiConfigs.length === 0) {
            container.innerHTML = `
                <p>Ingen AI-konfigurasjoner funnet.</p>
                <button class="btn btn-primary" onclick="adminManager.showNewAIConfigModal()">+ Legg til AI-konfigurasjon</button>
            `;
            return;
        }

        const html = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Provider</th>
                            <th>Modell</th>
                            <th>Max tokens</th>
                            <th>Temperature</th>
                            <th>Status</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.aiConfigs.map(config => this.renderAIConfigRow(config)).join('')}
                    </tbody>
                </table>
            </div>
            <button class="btn btn-primary" onclick="adminManager.showNewAIConfigModal()" style="margin-top: 1rem;">+ Legg til AI-konfigurasjon</button>
        `;

        container.innerHTML = html;
    }

    renderAIConfigRow(config) {
        const statusBadge = config.is_active
            ? '<span class="status-badge status-posted">Aktiv</span>'
            : '<span class="status-badge status-draft">Inaktiv</span>';

        const maskedKey = config.api_key ? '***' + config.api_key.slice(-4) : 'Ikke satt';

        return `
            <tr>
                <td>${config.provider}</td>
                <td>${config.model}</td>
                <td>${config.max_tokens}</td>
                <td>${config.temperature}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="adminManager.showEditAIConfigModal(${config.id})">
                        Rediger
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="adminManager.deleteAIConfig(${config.id})">
                        Slett
                    </button>
                </td>
            </tr>
        `;
    }

    async showNewAIConfigModal() {
        const content = `
            <h2>Ny AI-konfigurasjon</h2>

            <div class="form-group">
                <label>Provider</label>
                <select id="new-ai-provider">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                </select>
            </div>

            <div class="form-group">
                <label>API-nøkkel</label>
                <input type="password" id="new-ai-key" placeholder="sk-...">
            </div>

            <div class="form-group">
                <label>Modell</label>
                <input type="text" id="new-ai-model" placeholder="gpt-4o eller claude-3-5-sonnet-20241022">
                <small>Eksempler: gpt-4o, gpt-4o-mini, claude-3-5-sonnet-20241022, claude-3-haiku-20240307</small>
            </div>

            <div class="form-group">
                <label>Max tokens</label>
                <input type="number" id="new-ai-max-tokens" value="4000" min="100" step="100">
            </div>

            <div class="form-group">
                <label>Temperature</label>
                <input type="number" id="new-ai-temperature" value="0.3" min="0" max="2" step="0.1">
                <small>0 = deterministisk, 2 = veldig kreativ</small>
            </div>

            <div class="form-group">
                <label>Notater</label>
                <textarea id="new-ai-notes" rows="2" placeholder="Notater om denne konfigurasjonen..."></textarea>
            </div>

            <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                <button class="btn btn-primary" onclick="adminManager.saveNewAIConfig()">Opprett</button>
                <button class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
            </div>
        `;

        showModal('Ny AI-konfigurasjon', content);
    }

    async saveNewAIConfig() {
        try {
            const provider = document.getElementById('new-ai-provider').value;
            const api_key = document.getElementById('new-ai-key').value;
            const model = document.getElementById('new-ai-model').value;
            const max_tokens = parseInt(document.getElementById('new-ai-max-tokens').value);
            const temperature = parseFloat(document.getElementById('new-ai-temperature').value);
            const config_notes = document.getElementById('new-ai-notes').value;

            if (!api_key || !model) {
                showError('API-nøkkel og modell er påkrevd');
                return;
            }

            await api.request('/admin/ai-config', {
                method: 'POST',
                body: JSON.stringify({
                    provider,
                    api_key,
                    model,
                    max_tokens,
                    temperature,
                    config_notes
                })
            });

            closeModal();
            showSuccess('AI-konfigurasjon opprettet!');
            await this.loadAIConfigs();
            this.renderAIConfigs();
        } catch (error) {
            showError('Kunne ikke opprette AI-konfigurasjon: ' + error.message);
        }
    }

    async showEditAIConfigModal(configId) {
        try {
            const config = this.aiConfigs.find(c => c.id === configId);
            if (!config) {
                showError('Kunne ikke finne AI-konfigurasjon');
                return;
            }

            const content = `
                <h2>Rediger AI-konfigurasjon</h2>

                <div class="form-group">
                    <label>Provider (kan ikke endres)</label>
                    <input type="text" value="${config.provider}" disabled>
                </div>

                <div class="form-group">
                    <label>API-nøkkel</label>
                    <input type="password" id="edit-ai-key" placeholder="La stå tom for å beholde">
                    <small>Nåværende: ***${config.api_key ? config.api_key.slice(-4) : ''}</small>
                </div>

                <div class="form-group">
                    <label>Modell</label>
                    <input type="text" id="edit-ai-model" value="${config.model}">
                </div>

                <div class="form-group">
                    <label>Max tokens</label>
                    <input type="number" id="edit-ai-max-tokens" value="${config.max_tokens}" min="100" step="100">
                </div>

                <div class="form-group">
                    <label>Temperature</label>
                    <input type="number" id="edit-ai-temperature" value="${config.temperature}" min="0" max="2" step="0.1">
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="edit-ai-active" ${config.is_active ? 'checked' : ''}>
                        Aktiv konfigurasjon
                    </label>
                    <small>Kun én konfigurasjon kan være aktiv om gangen</small>
                </div>

                <div class="form-group">
                    <label>Notater</label>
                    <textarea id="edit-ai-notes" rows="2">${config.config_notes || ''}</textarea>
                </div>

                <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                    <button class="btn btn-primary" onclick="adminManager.saveAIConfig(${configId})">Lagre endringer</button>
                    <button class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
                </div>
            `;

            showModal('Rediger AI-konfigurasjon', content);
        } catch (error) {
            showError('Kunne ikke laste AI-konfigurasjon: ' + error.message);
        }
    }

    async saveAIConfig(configId) {
        try {
            const api_key = document.getElementById('edit-ai-key').value || null;
            const model = document.getElementById('edit-ai-model').value;
            const max_tokens = parseInt(document.getElementById('edit-ai-max-tokens').value);
            const temperature = parseFloat(document.getElementById('edit-ai-temperature').value);
            const is_active = document.getElementById('edit-ai-active').checked;
            const config_notes = document.getElementById('edit-ai-notes').value;

            const payload = {
                model,
                max_tokens,
                temperature,
                is_active,
                config_notes
            };

            if (api_key) {
                payload.api_key = api_key;
            }

            await api.request(`/admin/ai-config/${configId}`, {
                method: 'PATCH',
                body: JSON.stringify(payload)
            });

            closeModal();
            showSuccess('AI-konfigurasjon oppdatert!');
            await this.loadAIConfigs();
            this.renderAIConfigs();
        } catch (error) {
            showError('Kunne ikke lagre endringer: ' + error.message);
        }
    }

    async deleteAIConfig(configId) {
        if (!confirm('Er du sikker på at du vil slette denne AI-konfigurasjonen?')) {
            return;
        }

        try {
            await api.request(`/admin/ai-config/${configId}`, {
                method: 'DELETE'
            });

            showSuccess('AI-konfigurasjon slettet!');
            await this.loadAIConfigs();
            this.renderAIConfigs();
        } catch (error) {
            showError('Kunne ikke slette AI-konfigurasjon: ' + error.message);
        }
    }

    async loadAIUsageStats() {
        try {
            this.aiUsageStats = await api.request('/admin/ai-usage/users');
        } catch (error) {
            console.error('Error loading AI usage stats:', error);
        }
    }

    renderAIUsageStats() {
        const container = document.getElementById('admin-ai-usage-list');
        if (!container) return;

        if (this.aiUsageStats.length === 0) {
            container.innerHTML = '<p>Ingen AI-bruk registrert ennå.</p>';
            return;
        }

        const html = `
            <div class="table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Bruker</th>
                            <th>Operasjoner</th>
                            <th>Tokens brukt</th>
                            <th>Kostnad (USD)</th>
                            <th>Sist brukt</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.aiUsageStats.map(stat => this.renderAIUsageRow(stat)).join('')}
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    }

    renderAIUsageRow(stat) {
        return `
            <tr>
                <td>${stat.user_name}<br><small>${stat.user_email}</small></td>
                <td>${stat.total_operations}</td>
                <td>${stat.total_tokens.toLocaleString()}</td>
                <td>$${stat.total_cost_usd.toFixed(4)}</td>
                <td>${stat.last_used ? formatDate(stat.last_used) : 'Aldri'}</td>
            </tr>
        `;
    }
}

const adminManager = new AdminManager();
window.adminManager = adminManager;

export default adminManager;
