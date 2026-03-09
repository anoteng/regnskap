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
        this._showLedgerWizard(true);
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

        // Export Excel
        const exportExcelBtn = document.getElementById('export-excel-btn');
        if (exportExcelBtn) {
            exportExcelBtn.onclick = async () => {
                const statusEl = document.getElementById('export-status');
                try {
                    exportExcelBtn.disabled = true;
                    exportExcelBtn.textContent = 'Laster ned...';
                    if (statusEl) { statusEl.style.display = 'block'; statusEl.textContent = 'Genererer Excel-fil...'; }
                    await api.downloadFile('/exports/excel');
                    if (statusEl) { statusEl.textContent = 'Nedlasting fullført!'; setTimeout(() => { statusEl.style.display = 'none'; }, 3000); }
                } catch (error) {
                    alert('Kunne ikke eksportere: ' + error.message);
                    if (statusEl) statusEl.style.display = 'none';
                } finally {
                    exportExcelBtn.disabled = false;
                    exportExcelBtn.textContent = 'Last ned Excel';
                }
            };
        }

        // Export receipts ZIP
        const exportReceiptsBtn = document.getElementById('export-receipts-btn');
        if (exportReceiptsBtn) {
            exportReceiptsBtn.onclick = async () => {
                const statusEl = document.getElementById('export-status');
                try {
                    exportReceiptsBtn.disabled = true;
                    exportReceiptsBtn.textContent = 'Laster ned...';
                    if (statusEl) { statusEl.style.display = 'block'; statusEl.textContent = 'Pakker bilag...'; }
                    await api.downloadFile('/exports/receipts');
                    if (statusEl) { statusEl.textContent = 'Nedlasting fullført!'; setTimeout(() => { statusEl.style.display = 'none'; }, 3000); }
                } catch (error) {
                    alert('Kunne ikke eksportere bilag: ' + error.message);
                    if (statusEl) statusEl.style.display = 'none';
                } finally {
                    exportReceiptsBtn.disabled = false;
                    exportReceiptsBtn.textContent = 'Last ned bilag (ZIP)';
                }
            };
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
        this._showLedgerWizard(false);
    }

    async _showLedgerWizard(isOnboarding) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';

        // Template icons/defaults
        const templateMeta = {
            'personal_accounting': { icon: '👤', defaultName: 'Mitt regnskap' },
            'family_accounting': { icon: '👨\u200D👩\u200D👧\u200D👦', defaultName: 'Familieregnskap' },
            'business_accounting': { icon: '🏢', defaultName: 'Mitt firma' },
        };

        // Load templates
        let templates = [];
        try {
            templates = await api.getChartTemplates();
        } catch (e) {
            console.error('Could not load templates:', e);
        }

        // State
        let selectedTemplateId = null;
        let bankAccountCount = 0;

        const renderStep1 = () => {
            modal.innerHTML = `
                <div class="modal-content" style="max-width: 600px;">
                    ${!isOnboarding ? '<span class="close">&times;</span>' : ''}
                    <h2>${isOnboarding ? 'Velkommen til Privatregnskap.eu' : 'Opprett nytt regnskap'}</h2>
                    <p>${isOnboarding ? 'Velg en kontoplan for å komme i gang.' : 'Velg kontoplan for det nye regnskapet.'}</p>

                    <div id="template-cards" style="display: flex; flex-direction: column; gap: 0.75rem; margin: 1.5rem 0;">
                        ${templates.map(t => {
                            const meta = templateMeta[t.name] || { icon: '📋', defaultName: 'Nytt regnskap' };
                            return `
                                <div class="template-card" data-id="${t.id}" data-name="${t.name}"
                                     style="border: 2px solid #e5e7eb; border-radius: 8px; padding: 1rem; cursor: pointer; transition: border-color 0.2s;">
                                    <div style="display: flex; align-items: center; gap: 1rem;">
                                        <span style="font-size: 2rem;">${meta.icon}</span>
                                        <div>
                                            <strong style="font-size: 1.1rem;">${t.display_name}</strong>
                                            <p style="margin: 0.25rem 0 0; color: #6b7280; font-size: 0.9rem;">${t.description || ''}</p>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;

            if (!isOnboarding) {
                modal.querySelector('.close').onclick = () => modal.remove();
            }

            // Card selection
            modal.querySelectorAll('.template-card').forEach(card => {
                card.addEventListener('click', () => {
                    selectedTemplateId = parseInt(card.dataset.id);
                    const templateName = card.dataset.name;
                    renderStep2(templateName);
                });

                card.addEventListener('mouseenter', () => {
                    card.style.borderColor = '#3b82f6';
                    card.style.background = '#f0f7ff';
                });
                card.addEventListener('mouseleave', () => {
                    card.style.borderColor = '#e5e7eb';
                    card.style.background = '';
                });
            });
        };

        const renderStep2 = (templateName) => {
            const meta = templateMeta[templateName] || { icon: '📋', defaultName: 'Nytt regnskap' };
            bankAccountCount = 0;

            modal.innerHTML = `
                <div class="modal-content" style="max-width: 600px;">
                    ${!isOnboarding ? '<span class="close">&times;</span>' : ''}
                    <h2>${meta.icon} ${isOnboarding ? 'Sett opp regnskapet' : 'Nytt regnskap'}</h2>

                    <form id="wizard-form">
                        <div class="form-group">
                            <label>Navn på regnskap</label>
                            <input type="text" id="wizard-name" required value="${meta.defaultName}">
                        </div>

                        <hr style="margin: 1.5rem 0;">

                        <h3>Bankkontoer <small style="color: #6b7280; font-weight: normal;">(valgfritt)</small></h3>
                        <p style="color: #6b7280; font-size: 0.9rem; margin-bottom: 1rem;">
                            Du kan legge til bankkontoer nå eller senere fra Bankkontoer-menyen.
                        </p>

                        <div id="bank-accounts-list"></div>

                        <button type="button" id="add-bank-btn" class="btn btn-secondary" style="margin-bottom: 1.5rem;">
                            + Legg til bankkonto
                        </button>

                        <div style="display: flex; gap: 1rem; justify-content: space-between;">
                            <button type="button" id="wizard-back" class="btn btn-secondary">← Tilbake</button>
                            <button type="submit" class="btn btn-primary">Opprett regnskap</button>
                        </div>
                    </form>
                </div>
            `;

            if (!isOnboarding) {
                modal.querySelector('.close').onclick = () => modal.remove();
            }

            modal.querySelector('#wizard-back').onclick = () => renderStep1();

            modal.querySelector('#add-bank-btn').onclick = () => {
                addBankAccountRow();
            };

            const addBankAccountRow = () => {
                const idx = bankAccountCount++;
                const container = modal.querySelector('#bank-accounts-list');
                const row = document.createElement('div');
                row.className = 'bank-account-row';
                row.style.cssText = 'border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.75rem; margin-bottom: 0.75rem; background: #f9fafb;';
                row.innerHTML = `
                    <div style="display: flex; gap: 0.5rem; align-items: end; flex-wrap: wrap;">
                        <div class="form-group" style="flex: 2; min-width: 150px; margin-bottom: 0;">
                            <label style="font-size: 0.85rem;">Navn</label>
                            <input type="text" class="ba-name" placeholder="F.eks. DNB Brukskonto" required>
                        </div>
                        <div class="form-group" style="flex: 1; min-width: 120px; margin-bottom: 0;">
                            <label style="font-size: 0.85rem;">Type</label>
                            <select class="ba-type">
                                <option value="CHECKING">Brukskonto</option>
                                <option value="SAVINGS">Sparekonto</option>
                                <option value="CREDIT_CARD">Kredittkort</option>
                            </select>
                        </div>
                        <div class="form-group" style="flex: 1; min-width: 120px; margin-bottom: 0;">
                            <label style="font-size: 0.85rem;">Kontonr (valgfritt)</label>
                            <input type="text" class="ba-number" placeholder="1234.56.78901">
                        </div>
                        <button type="button" class="btn btn-sm btn-danger ba-remove" style="margin-bottom: 0.25rem;">✕</button>
                    </div>
                `;
                container.appendChild(row);

                row.querySelector('.ba-remove').onclick = () => row.remove();
            };

            // Form submission
            modal.querySelector('#wizard-form').addEventListener('submit', async (e) => {
                e.preventDefault();

                const name = modal.querySelector('#wizard-name').value;

                // Collect bank accounts
                const bankAccounts = [];
                modal.querySelectorAll('.bank-account-row').forEach(row => {
                    const baName = row.querySelector('.ba-name').value;
                    const baType = row.querySelector('.ba-type').value;
                    const baNumber = row.querySelector('.ba-number').value;
                    if (baName) {
                        bankAccounts.push({
                            name: baName,
                            account_type: baType,
                            account_number: baNumber || null
                        });
                    }
                });

                try {
                    const submitBtn = modal.querySelector('button[type="submit"]');
                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Oppretter...';

                    const ledger = await api.createLedger(name, selectedTemplateId, bankAccounts);

                    if (isOnboarding) {
                        api.setCurrentLedger(ledger.id);
                        modal.remove();
                        window.location.reload();
                    } else {
                        modal.remove();
                        await this.switchLedger(ledger.id);
                    }
                } catch (error) {
                    console.error('Failed to create ledger:', error);
                    alert('Kunne ikke opprette regnskap: ' + error.message);
                    const submitBtn = modal.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Opprett regnskap';
                    }
                }
            });
        };

        document.body.appendChild(modal);
        renderStep1();
    }
}

const ledgerManager = new LedgerManager();
window.ledgerManager = ledgerManager; // Make it globally accessible
export default ledgerManager;
