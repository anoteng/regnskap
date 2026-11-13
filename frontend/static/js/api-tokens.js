import api from './api.js?v=25';
import { showError, showSuccess, showModal } from './utils.js?v=25';

const escape = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

const formatDate = (value) => value
    ? new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleDateString('nb-NO')
    : null;

class ApiTokensManager {
    constructor() {
        this.bound = false;
    }

    async load() {
        const list = document.getElementById('api-tokens-list');
        if (!list) return;

        if (!this.bound) {
            document.getElementById('api-token-create').addEventListener('click', () => this.create());
            this.bound = true;
        }

        try {
            const ledgers = await api.getLedgers();
            const select = document.getElementById('api-token-ledger');
            select.innerHTML = '<option value="">Alle regnskapene mine</option>' +
                ledgers.map((l) => `<option value="${l.id}">${escape(l.name)}</option>`).join('');
            this.render(await api.get('/api-tokens/'));
        } catch (error) {
            list.textContent = `Kunne ikke hente nøkler: ${error.message}`;
        }
    }

    render(tokens) {
        const list = document.getElementById('api-tokens-list');
        if (tokens.length === 0) {
            list.innerHTML = '<p class="subtitle">Ingen API-nøkler.</p>';
            return;
        }
        list.innerHTML = `
            <table class="table">
                <thead><tr><th>Navn</th><th>Regnskap</th><th>Tilgang</th><th>Sist brukt</th><th>Utløper</th><th></th></tr></thead>
                <tbody>
                    ${tokens.map((t) => `
                        <tr>
                            <td>${escape(t.name)}<br><small><code>${escape(t.token_prefix)}…</code></small></td>
                            <td>${t.ledger_name ? escape(t.ledger_name) : 'Alle'}</td>
                            <td>${t.can_write ? 'Lese og bokføre' : 'Kun lese'}</td>
                            <td>${formatDate(t.last_used_at) || 'Aldri'}</td>
                            <td>${formatDate(t.expires_at) || 'Aldri'}</td>
                            <td><button class="btn btn-sm btn-danger" data-revoke="${t.id}">Tilbakekall</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        list.querySelectorAll('[data-revoke]').forEach((button) => {
            button.addEventListener('click', () => this.revoke(Number(button.dataset.revoke)));
        });
    }

    async create() {
        const name = document.getElementById('api-token-name').value.trim();
        if (!name) {
            showError('Gi nøkkelen et navn, for eksempel programmet som skal bruke den');
            return;
        }
        const ledgerValue = document.getElementById('api-token-ledger').value;
        const expiresValue = document.getElementById('api-token-expires').value;
        const canWrite = document.getElementById('api-token-access').value === 'write';
        try {
            const created = await api.post('/api-tokens/', {
                name,
                ledger_id: ledgerValue ? Number(ledgerValue) : null,
                expires_in_days: expiresValue ? Number(expiresValue) : null,
                can_write: canWrite,
            });
            document.getElementById('api-token-name').value = '';
            showModal('Ny API-nøkkel', `
                <p>Kopier nøkkelen nå. Den vises ikke igjen.</p>
                <input type="text" id="api-token-new" readonly value="${escape(created.token)}"
                       style="width: 100%; font-family: monospace;" onclick="this.select()">
                <button class="btn btn-primary" id="api-token-copy" style="margin-top: 1rem;">Kopier</button>
                <p class="subtitle" style="margin-top: 1rem;">Bruk den som <code>Authorization: Bearer &lt;nøkkel&gt;</code>
                mot <code>${escape(location.origin)}/api/v1/</code>. ${canWrite
                    ? 'Den kan lese, og bokføre i regnskap der du selv kan føre.'
                    : 'Den kan bare lese.'}</p>
            `);
            document.getElementById('api-token-copy').addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(created.token);
                    showSuccess('Kopiert');
                } catch {
                    document.getElementById('api-token-new').select();
                }
            });
            this.render(await api.get('/api-tokens/'));
        } catch (error) {
            showError(error.message);
        }
    }

    async revoke(id) {
        if (!confirm('Tilbakekalle nøkkelen? Programmer som bruker den, mister tilgangen med en gang.')) return;
        try {
            await api.delete(`/api-tokens/${id}`);
            showSuccess('Nøkkelen er tilbakekalt');
            this.render(await api.get('/api-tokens/'));
        } catch (error) {
            showError(error.message);
        }
    }
}

const apiTokensManager = new ApiTokensManager();
window.apiTokensManager = apiTokensManager;
export default apiTokensManager;
