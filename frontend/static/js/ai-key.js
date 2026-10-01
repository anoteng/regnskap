import api from './api.js?v=10';
import { showError, showSuccess } from './utils.js?v=10';

class AiKeyManager {
    constructor() {
        this.bound = false;
    }

    async load() {
        const statusEl = document.getElementById('ai-key-status');
        if (!statusEl) return;

        if (!this.bound) {
            document.getElementById('ai-key-save').addEventListener('click', () => this.save());
            document.getElementById('ai-key-delete').addEventListener('click', () => this.remove());
            this.bound = true;
        }

        try {
            this.render(await api.getAiKeyStatus());
        } catch (error) {
            statusEl.textContent = `Kunne ikke hente status: ${error.message}`;
        }
    }

    render(status) {
        const statusEl = document.getElementById('ai-key-status');
        const deleteBtn = document.getElementById('ai-key-delete');
        if (status.configured) {
            statusEl.textContent = `Egen nøkkel er lagret (slutter på ${status.hint}). AI-gjenkjenning kjører på din konto.`;
            deleteBtn.style.display = '';
        } else {
            statusEl.textContent = 'Ingen egen nøkkel. AI-gjenkjenning krever Premium-abonnement.';
            deleteBtn.style.display = 'none';
        }
        document.getElementById('ai-key-input').value = '';
    }

    async save() {
        const input = document.getElementById('ai-key-input');
        const value = input.value.trim();
        if (!value) {
            showError('Lim inn en API-nøkkel først');
            return;
        }
        try {
            // The backend verifies the key against Anthropic before storing it
            this.render(await api.setAiKey(value));
            showSuccess('API-nøkkel lagret');
        } catch (error) {
            showError(error.message);
        }
    }

    async remove() {
        try {
            this.render(await api.deleteAiKey());
            showSuccess('API-nøkkel fjernet');
        } catch (error) {
            showError(error.message);
        }
    }
}

const aiKeyManager = new AiKeyManager();
window.aiKeyManager = aiKeyManager;
export default aiKeyManager;
