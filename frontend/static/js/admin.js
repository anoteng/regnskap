import api from './api.js';
import { showModal, closeModal, showError, showSuccess, formatDate } from './utils.js';

class AdminManager {
    constructor() {
        this.users = [];
        this.plans = [];
    }

    async init() {
        await this.loadStats();
        await this.loadPlans();
        await this.loadUsers();
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
}

const adminManager = new AdminManager();
window.adminManager = adminManager;

export default adminManager;
