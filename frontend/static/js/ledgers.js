import api from './api.js';

class LedgerManager {
    constructor() {
        this.ledgers = [];
        this.currentLedger = null;
    }

    async init() {
        const success = await this.loadLedgers();
        if (success) {
            this.setupLedgerSelector();
        }
        return success;
    }

    async loadLedgers() {
        try {
            this.ledgers = await api.getLedgers();

            // If no ledgers, show onboarding
            if (this.ledgers.length === 0) {
                this.showOnboarding();
                return false;
            }

            // Set current ledger from localStorage or first ledger
            const savedLedgerId = api.getCurrentLedger();
            if (savedLedgerId) {
                this.currentLedger = this.ledgers.find(l => l.id === parseInt(savedLedgerId));
            }

            if (!this.currentLedger && this.ledgers.length > 0) {
                this.currentLedger = this.ledgers[0];
                api.setCurrentLedger(this.currentLedger.id);
            }

            return true;
        } catch (error) {
            console.error('Failed to load ledgers:', error);
            return false;
        }
    }

    setupLedgerSelector() {
        const selector = document.getElementById('ledger-selector');
        if (!selector) return;

        // Clear existing options
        selector.innerHTML = '';

        // Populate with ledgers
        this.ledgers.forEach(ledger => {
            const option = document.createElement('option');
            option.value = ledger.id;
            option.textContent = ledger.name;
            if (this.currentLedger && ledger.id === this.currentLedger.id) {
                option.selected = true;
            }
            selector.appendChild(option);
        });

        // Add event listener for ledger switching
        selector.addEventListener('change', async (e) => {
            await this.switchLedger(parseInt(e.target.value));
        });
    }

    async switchLedger(ledgerId) {
        try {
            await api.switchLedger(ledgerId);
            api.setCurrentLedger(ledgerId);

            // Reload the page to refresh all data
            window.location.reload();
        } catch (error) {
            console.error('Failed to switch ledger:', error);
            alert('Kunne ikke bytte regnskap: ' + error.message);
        }
    }

    showOnboarding() {
        // Create onboarding modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-content">
                <h2>Velkommen til Regnskap</h2>
                <p>Opprett ditt første regnskap for å komme i gang.</p>
                <form id="onboarding-form">
                    <div class="form-group">
                        <label for="ledger-name">Navn på regnskap</label>
                        <input type="text" id="ledger-name" name="name" required
                               placeholder="Mitt regnskap">
                    </div>
                    <div class="form-actions">
                        <button type="submit" class="btn btn-primary">Opprett regnskap</button>
                    </div>
                </form>
            </div>
        `;

        document.body.appendChild(modal);

        // Handle form submission
        const form = modal.querySelector('#onboarding-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = form.querySelector('#ledger-name').value;

            try {
                const ledger = await api.createLedger(name);
                api.setCurrentLedger(ledger.id);

                // Remove modal and reload
                modal.remove();
                window.location.reload();
            } catch (error) {
                console.error('Failed to create ledger:', error);
                alert('Kunne ikke opprette regnskap: ' + error.message);
            }
        });
    }

    showLedgerSettings() {
        if (!this.currentLedger) {
            alert('Ingen regnskap valgt');
            return;
        }

        // Hide other views
        document.querySelectorAll('.content-view').forEach(view => {
            view.style.display = 'none';
        });

        // Show ledger settings view
        const settingsView = document.getElementById('ledger-settings-view');
        if (settingsView) {
            settingsView.style.display = 'block';
            this.loadLedgerSettings();
        }
    }

    async loadLedgerSettings() {
        const ledger = await api.getLedger(this.currentLedger.id);

        // Populate form
        document.getElementById('ledger-name').value = ledger.name;
        document.getElementById('ledger-role').textContent = ledger.user_role;

        // Load passkeys
        await this.loadPasskeys();

        // Load members
        await this.loadLedgerMembers();

        // Setup event listeners
        this.setupLedgerSettingsHandlers(ledger);
    }

    async loadPasskeys() {
        const passkeyManager = window.auth?.passkeyManager;

        if (!passkeyManager) {
            return;
        }

        if (!passkeyManager.isSupported()) {
            document.getElementById('passkey-support-warning').style.display = 'block';
            document.getElementById('add-passkey-btn').disabled = true;
            return;
        }

        try {
            const credentials = await passkeyManager.list();
            const listContainer = document.getElementById('passkeys-list');

            if (credentials.length === 0) {
                listContainer.innerHTML = '<p style="color: #666;">Ingen passkeys registrert ennå.</p>';
                return;
            }

            listContainer.innerHTML = credentials.map(cred => `
                <div class="passkey-item" style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 0.5rem;">
                    <div>
                        <strong>${cred.credential_name || 'Passkey'}</strong>
                        <div style="font-size: 0.875rem; color: #666;">
                            Opprettet: ${new Date(cred.created_at).toLocaleDateString('nb-NO')}
                            ${cred.last_used_at ? `• Sist brukt: ${new Date(cred.last_used_at).toLocaleDateString('nb-NO')}` : ''}
                        </div>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-secondary" onclick="ledgerManager.renamePasskey(${cred.id})">
                            ✏️ Gi nytt navn
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="ledgerManager.deletePasskey(${cred.id})">
                            🗑️ Slett
                        </button>
                    </div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Failed to load passkeys:', error);
        }
    }

    async addPasskey() {
        console.log('addPasskey called');
        console.log('window.auth:', window.auth);
        console.log('window.auth?.passkeyManager:', window.auth?.passkeyManager);

        const passkeyManager = window.auth?.passkeyManager;
        if (!passkeyManager) {
            console.error('PasskeyManager not available');
            alert('PasskeyManager ikke tilgjengelig. Prøv å refresh siden.');
            return;
        }

        const name = prompt('Gi passkeyen et navn (f.eks. "Min iPhone", "MacBook")');
        if (name === null) return; // User cancelled

        try {
            console.log('Calling passkeyManager.register...');
            await passkeyManager.register(name || null);
            alert('Passkey lagt til!');
            await this.loadPasskeys();
        } catch (error) {
            console.error('Failed to add passkey:', error);
            alert('Kunne ikke legge til passkey: ' + error.message);
        }
    }

    async deletePasskey(credentialId) {
        const passkeyManager = window.auth?.passkeyManager;
        if (!passkeyManager) return;

        if (!confirm('Er du sikker på at du vil slette denne passkeyen?')) {
            return;
        }

        try {
            await passkeyManager.delete(credentialId);
            alert('Passkey slettet');
            await this.loadPasskeys();
        } catch (error) {
            console.error('Failed to delete passkey:', error);
            alert('Kunne ikke slette passkey: ' + error.message);
        }
    }

    async renamePasskey(credentialId) {
        const passkeyManager = window.auth?.passkeyManager;
        if (!passkeyManager) return;

        const newName = prompt('Nytt navn:');
        if (!newName) return;

        try {
            await passkeyManager.rename(credentialId, newName);
            await this.loadPasskeys();
        } catch (error) {
            console.error('Failed to rename passkey:', error);
            alert('Kunne ikke gi nytt navn: ' + error.message);
        }
    }

    async loadLedgerMembers() {
        const members = await api.getLedgerMembers(this.currentLedger.id);
        const tbody = document.querySelector('#members-table tbody');
        tbody.innerHTML = '';

        members.forEach(member => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${member.user.full_name}</td>
                <td>${member.user.email}</td>
                <td>${member.role}</td>
                <td>
                    ${member.role !== 'OWNER' && this.currentLedger.user_role === 'OWNER' ? `
                        <button class="btn btn-sm btn-secondary" onclick="ledgerManager.changeMemberRole(${member.user_id}, '${member.role}')">
                            Endre rolle
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="ledgerManager.removeMember(${member.user_id})">
                            Fjern
                        </button>
                    ` : ''}
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    setupLedgerSettingsHandlers(ledger) {
        // Save ledger name
        const saveBtn = document.getElementById('save-ledger-btn');
        if (saveBtn) {
            saveBtn.onclick = async () => {
                const newName = document.getElementById('ledger-name').value;
                try {
                    await api.updateLedger(ledger.id, newName);
                    alert('Regnskap oppdatert');
                    await this.loadLedgers();
                    this.setupLedgerSelector();
                } catch (error) {
                    alert('Kunne ikke oppdatere regnskap: ' + error.message);
                }
            };
        }

        // Add passkey
        const addPasskeyBtn = document.getElementById('add-passkey-btn');
        console.log('Setting up passkey button, element:', addPasskeyBtn);
        if (addPasskeyBtn) {
            console.log('Adding onclick handler to passkey button');
            addPasskeyBtn.onclick = () => this.addPasskey();
        } else {
            console.error('add-passkey-btn element not found!');
        }

        // Invite member
        const inviteBtn = document.getElementById('invite-member-btn');
        if (inviteBtn) {
            inviteBtn.onclick = () => this.showInviteMemberModal();
        }

        // Leave ledger
        const leaveBtn = document.getElementById('leave-ledger-btn');
        if (leaveBtn) {
            if (ledger.user_role === 'OWNER') {
                leaveBtn.style.display = 'none';
            } else {
                leaveBtn.onclick = async () => {
                    if (confirm('Er du sikker på at du vil forlate dette regnskapet?')) {
                        try {
                            await api.leaveLedger(ledger.id);
                            api.clearCurrentLedger();
                            window.location.reload();
                        } catch (error) {
                            alert('Kunne ikke forlate regnskap: ' + error.message);
                        }
                    }
                };
            }
        }

        // Delete ledger
        const deleteBtn = document.getElementById('delete-ledger-btn');
        if (deleteBtn) {
            if (ledger.user_role !== 'OWNER') {
                deleteBtn.style.display = 'none';
            } else {
                deleteBtn.onclick = async () => {
                    if (confirm('Er du sikker på at du vil slette dette regnskapet? Dette kan ikke angres.')) {
                        try {
                            await api.deleteLedger(ledger.id);
                            api.clearCurrentLedger();
                            window.location.reload();
                        } catch (error) {
                            alert('Kunne ikke slette regnskap: ' + error.message);
                        }
                    }
                };
            }
        }
    }

    showInviteMemberModal() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h2>Inviter medlem</h2>
                <form id="invite-member-form">
                    <div class="form-group">
                        <label for="member-email">E-postadresse</label>
                        <input type="email" id="member-email" name="email" required>
                    </div>
                    <div class="form-group">
                        <label for="member-role">Rolle</label>
                        <select id="member-role" name="role" required>
                            <option value="VIEWER">Viewer (kun se)</option>
                            <option value="MEMBER" selected>Member (kan redigere)</option>
                            <option value="OWNER">Owner (full tilgang)</option>
                        </select>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            Avbryt
                        </button>
                        <button type="submit" class="btn btn-primary">Inviter</button>
                    </div>
                </form>
            </div>
        `;

        document.body.appendChild(modal);

        // Close button
        modal.querySelector('.close').onclick = () => modal.remove();

        // Form submission
        const form = modal.querySelector('#invite-member-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = form.querySelector('#member-email').value;
            const role = form.querySelector('#member-role').value;

            try {
                await api.inviteMember(this.currentLedger.id, email, role);
                alert('Medlem invitert');
                modal.remove();
                await this.loadLedgerMembers();
            } catch (error) {
                alert('Kunne ikke invitere medlem: ' + error.message);
            }
        });
    }

    async changeMemberRole(userId, currentRole) {
        const newRole = prompt('Ny rolle (VIEWER, MEMBER, OWNER):', currentRole);
        if (newRole && ['VIEWER', 'MEMBER', 'OWNER'].includes(newRole.toUpperCase())) {
            try {
                await api.updateMemberRole(this.currentLedger.id, userId, newRole.toUpperCase());
                alert('Rolle oppdatert');
                await this.loadLedgerMembers();
            } catch (error) {
                alert('Kunne ikke oppdatere rolle: ' + error.message);
            }
        }
    }

    async removeMember(userId) {
        if (confirm('Er du sikker på at du vil fjerne dette medlemmet?')) {
            try {
                await api.removeMember(this.currentLedger.id, userId);
                alert('Medlem fjernet');
                await this.loadLedgerMembers();
            } catch (error) {
                alert('Kunne ikke fjerne medlem: ' + error.message);
            }
        }
    }

    showCreateLedgerModal() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h2>Opprett nytt regnskap</h2>
                <form id="create-ledger-form">
                    <div class="form-group">
                        <label for="new-ledger-name">Navn på regnskap</label>
                        <input type="text" id="new-ledger-name" name="name" required
                               placeholder="Familie regnskap">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            Avbryt
                        </button>
                        <button type="submit" class="btn btn-primary">Opprett</button>
                    </div>
                </form>
            </div>
        `;

        document.body.appendChild(modal);

        // Close button
        modal.querySelector('.close').onclick = () => modal.remove();

        // Form submission
        const form = modal.querySelector('#create-ledger-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = form.querySelector('#new-ledger-name').value;

            try {
                const ledger = await api.createLedger(name);
                modal.remove();

                // Switch to new ledger
                await this.switchLedger(ledger.id);
            } catch (error) {
                alert('Kunne ikke opprette regnskap: ' + error.message);
            }
        });
    }
}

const ledgerManager = new LedgerManager();
window.ledgerManager = ledgerManager; // Make it globally accessible
export default ledgerManager;
