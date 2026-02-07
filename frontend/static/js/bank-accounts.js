import api from './api.js';
import { showModal, closeModal, showError, showSuccess } from './utils.js';

class BankAccountsManager {
    constructor() {
        this.accounts = [];
    }

    async init() {
        await this.loadAccounts();
        this.setupEventListeners();
        await this.loadBankAccounts();
    }

    async loadAccounts() {
        this.accounts = await api.getAccounts();
    }

    setupEventListeners() {
        document.getElementById('new-bank-account-btn').addEventListener('click', () => {
            this.showNewBankAccountModal();
        });
    }

    async loadBankAccounts() {
        const bankAccounts = await api.getBankAccounts();
        this.renderBankAccounts(bankAccounts);
    }

    renderBankAccounts(bankAccounts) {
        const list = document.getElementById('bank-accounts-list');

        if (bankAccounts.length === 0) {
            list.innerHTML = `
                <div class="card">
                    <p>Ingen bankkontoer opprettet ennå.</p>
                    <p>Opprett en bankkonto for å kunne importere transaksjoner fra CSV.</p>
                </div>
            `;
            return;
        }

        const typeNames = {
            'CHECKING': 'Brukskonto',
            'SAVINGS': 'Sparekonto',
            'CREDIT_CARD': 'Kredittkort'
        };

        const html = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Navn</th>
                        <th>Type</th>
                        <th>Kontonummer</th>
                        <th>Kontoplan-konto</th>
                        <th>Saldo</th>
                    </tr>
                </thead>
                <tbody>
                    ${bankAccounts.map(ba => {
                        const account = this.accounts.find(a => a.id === ba.account_id);
                        return `
                            <tr>
                                <td>${ba.name}</td>
                                <td>${typeNames[ba.account_type]}</td>
                                <td>${ba.account_number || '-'}</td>
                                <td>${account ? `${account.account_number} - ${account.account_name}` : '-'}</td>
                                <td>${ba.balance} kr</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;

        list.innerHTML = html;
    }

    showNewBankAccountModal() {
        const content = `
            <form id="new-bank-account-form">
                <div class="form-group">
                    <label>Navn</label>
                    <input type="text" id="ba-name" placeholder="Min brukskonto" required>
                </div>
                <div class="form-group">
                    <label>Type</label>
                    <select id="ba-type" required>
                        <option value="CHECKING">Brukskonto</option>
                        <option value="SAVINGS">Sparekonto</option>
                        <option value="CREDIT_CARD">Kredittkort</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Kontonummer (valgfri)</label>
                    <input type="text" id="ba-number" placeholder="1234.56.78900">
                </div>
                <div class="form-group">
                    <label>Koble til konto i kontoplan</label>
                    <select id="ba-account-mode" required>
                        <option value="">Velg...</option>
                        <option value="existing">Bruk eksisterende konto</option>
                        <option value="new">Opprett ny konto</option>
                    </select>
                </div>

                <div id="existing-account-section" style="display: none;">
                    <div class="form-group">
                        <label>Velg konto</label>
                        <select id="ba-account">
                            <option value="">Velg konto...</option>
                        </select>
                        <small id="account-hint" style="color: var(--text-secondary);">
                            Velg konto fra kontoplanen
                        </small>
                    </div>
                </div>

                <div id="new-account-section" style="display: none;">
                    <div class="form-group">
                        <label>Kontonummer</label>
                        <input type="text" id="new-acc-number" placeholder="1202">
                        <small id="number-hint" style="color: var(--text-secondary);">
                            Bruk et ledig nummer
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Kontonavn</label>
                        <input type="text" id="new-acc-name" placeholder="Sparekonto bank">
                    </div>
                    <div class="form-group">
                        <label>Beskrivelse (valgfri)</label>
                        <textarea id="new-acc-description" rows="2"></textarea>
                    </div>
                </div>

                <button type="submit" class="btn btn-primary">Opprett bankkonto</button>
            </form>
        `;

        showModal('Ny bankkonto', content);

        // Setup event listener for bank account type change
        const baTypeSelect = document.getElementById('ba-type');
        baTypeSelect.addEventListener('change', () => {
            this.updateAccountOptions();
        });

        // Setup event listener for account mode selection
        const accountModeSelect = document.getElementById('ba-account-mode');
        const existingSection = document.getElementById('existing-account-section');
        const newSection = document.getElementById('new-account-section');

        accountModeSelect.addEventListener('change', (e) => {
            if (e.target.value === 'existing') {
                existingSection.style.display = 'block';
                newSection.style.display = 'none';
                document.getElementById('ba-account').required = true;
                document.getElementById('new-acc-number').required = false;
                document.getElementById('new-acc-name').required = false;
                this.updateAccountOptions();
            } else if (e.target.value === 'new') {
                existingSection.style.display = 'none';
                newSection.style.display = 'block';
                document.getElementById('ba-account').required = false;
                document.getElementById('new-acc-number').required = true;
                document.getElementById('new-acc-name').required = true;
                this.updateAccountHints();
            } else {
                existingSection.style.display = 'none';
                newSection.style.display = 'none';
            }
        });

        document.getElementById('new-bank-account-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.createBankAccount();
        });
    }

    updateAccountOptions() {
        const baType = document.getElementById('ba-type').value;
        const accountSelect = document.getElementById('ba-account');
        const accountHint = document.getElementById('account-hint');

        // CREDIT_CARD should use LIABILITY accounts, others use ASSET
        const accountType = baType === 'CREDIT_CARD' ? 'LIABILITY' : 'ASSET';

        const filteredAccounts = this.accounts.filter(a => a.account_type === accountType);

        accountSelect.innerHTML = '<option value="">Velg konto...</option>' +
            filteredAccounts.map(a => `<option value="${a.id}">${a.account_number} - ${a.account_name}</option>`).join('');

        if (baType === 'CREDIT_CARD') {
            accountHint.textContent = 'Velg en gjeldskonto, f.eks. 2401 (Kredittkort)';
        } else {
            accountHint.textContent = 'Velg f.eks. konto 1201 (Brukskonto bank) eller 1202 (Sparekonto bank)';
        }
    }

    updateAccountHints() {
        const baType = document.getElementById('ba-type').value;
        const numberHint = document.getElementById('number-hint');

        if (baType === 'CREDIT_CARD') {
            numberHint.textContent = 'Bruk et ledig nummer, f.eks. 2401-2409 for kredittkort';
            document.getElementById('new-acc-number').placeholder = '2401';
            document.getElementById('new-acc-name').placeholder = 'Visa kredittkort';
        } else {
            numberHint.textContent = 'Bruk et ledig nummer, f.eks. 1202-1209 for bankkontoer';
            document.getElementById('new-acc-number').placeholder = '1202';
            document.getElementById('new-acc-name').placeholder = 'Sparekonto bank';
        }
    }

    async createBankAccount() {
        const name = document.getElementById('ba-name').value;
        const type = document.getElementById('ba-type').value;
        const number = document.getElementById('ba-number').value;
        const accountMode = document.getElementById('ba-account-mode').value;

        if (!accountMode) {
            showError('Vennligst velg om du vil bruke eksisterende konto eller opprette ny');
            return;
        }

        try {
            let accountId;

            if (accountMode === 'existing') {
                accountId = document.getElementById('ba-account').value;
                if (!accountId) {
                    showError('Vennligst velg en konto fra kontoplanen');
                    return;
                }
                accountId = parseInt(accountId);
            } else if (accountMode === 'new') {
                // Create new account first
                const newAccNumber = document.getElementById('new-acc-number').value;
                const newAccName = document.getElementById('new-acc-name').value;
                const newAccDescription = document.getElementById('new-acc-description').value;

                if (!newAccNumber || !newAccName) {
                    showError('Vennligst fyll ut kontonummer og kontonavn');
                    return;
                }

                // CREDIT_CARD should create LIABILITY account, others create ASSET
                const accountType = type === 'CREDIT_CARD' ? 'LIABILITY' : 'ASSET';

                const newAccount = await api.createAccount({
                    account_number: newAccNumber,
                    account_name: newAccName,
                    account_type: accountType,
                    description: newAccDescription || null
                });

                accountId = newAccount.id;
            }

            // Create bank account
            await api.createBankAccount({
                name,
                account_type: type,
                account_number: number || null,
                account_id: accountId
            });

            closeModal();
            showSuccess('Bankkonto opprettet');

            // Reload both accounts and bank accounts
            await this.loadAccounts();
            await this.loadBankAccounts();
        } catch (error) {
            showError(error.message);
        }
    }
}

const bankAccountsManager = new BankAccountsManager();

export default bankAccountsManager;
