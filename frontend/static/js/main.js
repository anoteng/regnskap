import auth from './auth.js';
import api from './api.js';
import ledgerManager from './ledgers.js';
import transactionsManager from './transactions.js';
import bankAccountsManager from './bank-accounts.js';
import postingQueueManager from './posting-queue.js';
import receiptsManager from './receipts.js';
import reportsManager from './reports.js';
import adminManager from './admin.js';
import { formatCurrency, getTodayDate, getFirstDayOfMonth, getLastDayOfMonth, showModal, closeModal, showError, showSuccess } from './utils.js';

// Make auth available globally for passkey management
window.auth = auth;

class App {
    constructor() {
        this.currentView = 'dashboard';
        this.init();
    }

    async init() {
        // Always initialize passkey manager
        await auth.initPasskeyManager();

        if (auth.isAuthenticated()) {
            // Initialize ledger context first
            const hasLedgers = await ledgerManager.init();

            // If no ledger selected yet, don't show main view (onboarding will handle it)
            if (!hasLedgers || !api.getCurrentLedger()) {
                return;
            }

            this.showMainView();
        } else {
            this.showAuthView();
        }
    }

    showAuthView() {
        document.getElementById('auth-view').style.display = 'block';
        document.getElementById('main-view').style.display = 'none';
        auth.setupAuthUI();
    }

    async showMainView() {
        document.getElementById('auth-view').style.display = 'none';
        document.getElementById('main-view').style.display = 'block';
        this.setupNavigation();
        this.setupLogout();
        this.wrapTables();
        await this.checkAdminAccess();
        this.loadDashboard();
    }

    async checkAdminAccess() {
        try {
            // Try to access admin endpoint to see if user is admin
            await api.request('/admin/stats');
            // If successful, user is admin - show admin menu
            const adminMenuItem = document.getElementById('admin-menu-item');
            if (adminMenuItem) {
                adminMenuItem.style.display = 'block';
            }
        } catch (error) {
            // User is not admin, hide menu (already hidden by default)
            console.log('User is not admin');
        }
    }

    wrapTables() {
        // Wrap all tables in scrollable containers for mobile
        const observer = new MutationObserver(() => {
            document.querySelectorAll('.table').forEach(table => {
                if (!table.parentElement.classList.contains('table-wrapper')) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'table-wrapper';
                    table.parentNode.insertBefore(wrapper, table);
                    wrapper.appendChild(table);
                }
            });
        });

        // Observe the main container for changes
        const container = document.querySelector('.container');
        if (container) {
            observer.observe(container, {
                childList: true,
                subtree: true
            });
        }

        // Initial wrap
        document.querySelectorAll('.table').forEach(table => {
            if (!table.parentElement.classList.contains('table-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-wrapper';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
    }

    setupLogout() {
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn && !logoutBtn.dataset.listenerAttached) {
            logoutBtn.addEventListener('click', () => {
                auth.logout();
                window.location.reload();
            });
            logoutBtn.dataset.listenerAttached = 'true';
        }
    }

    setupNavigation() {
        // Setup view switching
        document.querySelectorAll('[data-view]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchView(e.target.dataset.view);

                // Close mobile menu on navigation
                this.closeMobileMenu();
            });
        });

        // Setup mobile menu toggle
        const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
        const navbarMenu = document.getElementById('navbar-menu');

        console.log('Mobile menu setup:', { mobileMenuToggle: !!mobileMenuToggle, navbarMenu: !!navbarMenu });

        if (mobileMenuToggle && navbarMenu) {
            mobileMenuToggle.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                navbarMenu.classList.toggle('active');
                console.log('Menu toggled, active:', navbarMenu.classList.contains('active'));

                // Update icon
                if (navbarMenu.classList.contains('active')) {
                    mobileMenuToggle.textContent = '✕';
                } else {
                    mobileMenuToggle.textContent = '☰';
                }
            });

            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!navbarMenu.contains(e.target) && !mobileMenuToggle.contains(e.target)) {
                    this.closeMobileMenu();
                }
            });
        }
    }

    closeMobileMenu() {
        const navbarMenu = document.getElementById('navbar-menu');
        const mobileMenuToggle = document.getElementById('mobile-menu-toggle');

        if (navbarMenu && navbarMenu.classList.contains('active')) {
            navbarMenu.classList.remove('active');
            if (mobileMenuToggle) {
                mobileMenuToggle.textContent = '☰';
            }
        }
    }

    switchView(viewName) {
        document.querySelectorAll('.content-view').forEach(view => {
            view.style.display = 'none';
        });

        document.getElementById(`${viewName}-view`).style.display = 'block';
        this.currentView = viewName;

        switch (viewName) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'bank-accounts':
                bankAccountsManager.init();
                break;
            case 'transactions':
                transactionsManager.init();
                break;
            case 'posting-queue':
                postingQueueManager.init();
                postingQueueManager.loadQueue();
                break;
            case 'receipts':
                receiptsManager.init();
                break;
            case 'accounts':
                this.loadAccounts();
                break;
            case 'budgets':
                this.loadBudgets();
                this.setupBudgetHandlers();
                break;
            case 'reports':
                reportsManager.init();
                break;
            case 'ledger-settings':
                ledgerManager.showLedgerSettings();
                break;
            case 'admin':
                adminManager.init();
                break;
        }
    }

    async loadDashboard() {
        try {
            const balanceSheet = await api.getBalanceSheet();
            const today = getTodayDate();
            const firstDay = getFirstDayOfMonth();
            const incomeStatement = await api.getIncomeStatement(firstDay, today);
            const transactions = await api.getTransactions({ limit: 10 });

            document.getElementById('total-assets').textContent = formatCurrency(balanceSheet.total_assets);
            document.getElementById('total-liabilities').textContent = formatCurrency(balanceSheet.total_liabilities);
            document.getElementById('net-worth').textContent = formatCurrency(
                balanceSheet.total_assets - balanceSheet.total_liabilities
            );
            document.getElementById('month-income').textContent = formatCurrency(incomeStatement.net_income);

            this.renderRecentTransactions(transactions);
        } catch (error) {
            console.error('Error loading dashboard:', error);
        }
    }

    renderRecentTransactions(transactions) {
        const container = document.getElementById('recent-transactions');

        if (transactions.length === 0) {
            container.innerHTML = '<p>Ingen transaksjoner ennå.</p>';
            return;
        }

        const html = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Dato</th>
                        <th>Beskrivelse</th>
                        <th>Referanse</th>
                    </tr>
                </thead>
                <tbody>
                    ${transactions.slice(0, 5).map(t => `
                        <tr>
                            <td>${new Date(t.transaction_date).toLocaleDateString('nb-NO')}</td>
                            <td>${t.description}</td>
                            <td>${t.reference || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        container.innerHTML = html;
    }

    async loadAccounts() {
        try {
            const typeFilter = document.getElementById('account-type-filter').value;
            const showHidden = document.getElementById('show-hidden-accounts').checked;
            const accounts = await api.getAccounts(typeFilter || null, showHidden);

            const container = document.getElementById('accounts-list');

            const accountsByType = accounts.reduce((acc, account) => {
                if (!acc[account.account_type]) {
                    acc[account.account_type] = [];
                }
                acc[account.account_type].push(account);
                return acc;
            }, {});

            const typeNames = {
                'ASSET': 'Eiendeler',
                'LIABILITY': 'Gjeld',
                'EQUITY': 'Egenkapital',
                'REVENUE': 'Inntekter',
                'EXPENSE': 'Kostnader'
            };

            let html = '';
            for (const [type, accts] of Object.entries(accountsByType)) {
                html += `
                    <div class="card">
                        <h3>${typeNames[type]}</h3>
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Kontonummer</th>
                                    <th>Kontonavn</th>
                                    <th>Beskrivelse</th>
                                    <th>Handlinger</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${accts.map(a => `
                                    <tr>
                                        <td>${a.account_number}</td>
                                        <td>${a.account_name}</td>
                                        <td>${a.description || '-'}</td>
                                        <td>
                                            ${a.is_system ? `
                                                <button class="btn btn-sm btn-secondary" onclick="app.toggleAccountVisibility(${a.id})">
                                                    Skjul konto
                                                </button>
                                            ` : `
                                                <button class="btn btn-sm btn-secondary" onclick="app.showEditAccountModal(${a.id}, '${a.account_number}', '${a.account_name.replace(/'/g, "\\'")}', '${a.account_type}', '${a.description || ''}')">
                                                    Rediger
                                                </button>
                                                <button class="btn btn-sm btn-danger" onclick="app.deleteAccount(${a.id})">
                                                    Slett
                                                </button>
                                            `}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }

            container.innerHTML = html;

            const typeFilterEl = document.getElementById('account-type-filter');
            const showHiddenEl = document.getElementById('show-hidden-accounts');
            const newAccountBtn = document.getElementById('new-account-btn');

            // Remove old listeners to avoid duplicates
            const newTypeFilter = typeFilterEl.cloneNode(true);
            typeFilterEl.parentNode.replaceChild(newTypeFilter, typeFilterEl);

            const newShowHidden = showHiddenEl.cloneNode(true);
            showHiddenEl.parentNode.replaceChild(newShowHidden, showHiddenEl);

            newTypeFilter.addEventListener('change', () => {
                this.loadAccounts();
            });

            newShowHidden.addEventListener('change', () => {
                this.loadAccounts();
            });

            if (newAccountBtn && !newAccountBtn.dataset.listenerAdded) {
                newAccountBtn.dataset.listenerAdded = 'true';
                newAccountBtn.addEventListener('click', () => {
                    this.showNewAccountModal();
                });
            }
        } catch (error) {
            console.error('Error loading accounts:', error);
        }
    }

    showNewAccountModal() {
        const content = `
            <form id="new-account-form">
                <div class="form-group">
                    <label>Kontonummer</label>
                    <input type="text" id="acc-number" placeholder="9999" required>
                    <small style="color: var(--text-secondary);">
                        Bruk et ledig nummer, f.eks. 9xxx for egendefinerte kontoer
                    </small>
                </div>
                <div class="form-group">
                    <label>Kontonavn</label>
                    <input type="text" id="acc-name" placeholder="Min egendefinerte konto" required>
                </div>
                <div class="form-group">
                    <label>Kontotype</label>
                    <select id="acc-type" required>
                        <option value="ASSET">Eiendel</option>
                        <option value="LIABILITY">Gjeld</option>
                        <option value="EQUITY">Egenkapital</option>
                        <option value="REVENUE">Inntekt</option>
                        <option value="EXPENSE">Kostnad</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Beskrivelse (valgfri)</label>
                    <textarea id="acc-description" rows="3"></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Opprett konto</button>
            </form>
        `;

        showModal('Ny konto', content);

        document.getElementById('new-account-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.createAccount();
        });
    }

    async createAccount() {
        const number = document.getElementById('acc-number').value;
        const name = document.getElementById('acc-name').value;
        const type = document.getElementById('acc-type').value;
        const description = document.getElementById('acc-description').value;

        try {
            await api.createAccount({
                account_number: number,
                account_name: name,
                account_type: type,
                description: description || null
            });

            closeModal();
            showSuccess('Konto opprettet');
            await this.loadAccounts();
        } catch (error) {
            showError(error.message);
        }
    }

    showEditAccountModal(id, accountNumber, accountName, accountType, description) {
        const content = `
            <form id="edit-account-form">
                <div class="form-group">
                    <label>Kontonummer</label>
                    <input type="text" id="edit-acc-number" value="${accountNumber}" required>
                </div>
                <div class="form-group">
                    <label>Kontonavn</label>
                    <input type="text" id="edit-acc-name" value="${accountName}" required>
                </div>
                <div class="form-group">
                    <label>Kontotype</label>
                    <select id="edit-acc-type" required>
                        <option value="ASSET" ${accountType === 'ASSET' ? 'selected' : ''}>Eiendel</option>
                        <option value="LIABILITY" ${accountType === 'LIABILITY' ? 'selected' : ''}>Gjeld</option>
                        <option value="EQUITY" ${accountType === 'EQUITY' ? 'selected' : ''}>Egenkapital</option>
                        <option value="REVENUE" ${accountType === 'REVENUE' ? 'selected' : ''}>Inntekt</option>
                        <option value="EXPENSE" ${accountType === 'EXPENSE' ? 'selected' : ''}>Kostnad</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Beskrivelse (valgfri)</label>
                    <textarea id="edit-acc-description" rows="3">${description}</textarea>
                </div>
                <button type="submit" class="btn btn-primary">Lagre endringer</button>
            </form>
        `;

        showModal('Rediger konto', content);

        document.getElementById('edit-account-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.updateAccount(id);
        });
    }

    async updateAccount(id) {
        const number = document.getElementById('edit-acc-number').value;
        const name = document.getElementById('edit-acc-name').value;
        const type = document.getElementById('edit-acc-type').value;
        const description = document.getElementById('edit-acc-description').value;

        try {
            await api.updateAccount(id, {
                account_number: number,
                account_name: name,
                account_type: type,
                description: description || null
            });

            closeModal();
            showSuccess('Konto oppdatert');
            await this.loadAccounts();
        } catch (error) {
            showError(error.message);
        }
    }

    async deleteAccount(id) {
        if (!confirm('Er du sikker på at du vil slette denne kontoen? Dette kan ikke angres.')) {
            return;
        }

        try {
            await api.deleteAccount(id);
            showSuccess('Konto slettet');
            await this.loadAccounts();
        } catch (error) {
            showError(error.message);
        }
    }

    async toggleAccountVisibility(id) {
        try {
            const result = await api.toggleAccountVisibility(id);
            showSuccess(result.message);
            await this.loadAccounts();
        } catch (error) {
            showError(error.message);
        }
    }

    setupBudgetHandlers() {
        const newBudgetBtn = document.getElementById('new-budget-btn');
        if (newBudgetBtn) {
            newBudgetBtn.onclick = () => this.showNewBudgetModal();
        }
    }

    showNewBudgetModal() {
        const currentYear = new Date().getFullYear();
        const content = `
            <form id="new-budget-form">
                <div class="form-group">
                    <label for="budget-name">Navn</label>
                    <input type="text" id="budget-name" required placeholder="F.eks. 'Budsjett 2026'">
                </div>
                <div class="form-group">
                    <label for="budget-year">År</label>
                    <input type="number" id="budget-year" required value="${currentYear}" min="2020" max="2100">
                </div>
                <button type="submit" class="btn btn-primary">Opprett budsjett</button>
            </form>
        `;

        showModal('Nytt budsjett', content);

        document.getElementById('new-budget-form').onsubmit = async (e) => {
            e.preventDefault();
            try {
                const data = {
                    name: document.getElementById('budget-name').value,
                    year: parseInt(document.getElementById('budget-year').value)
                };

                const budget = await api.createBudget(data);
                closeModal();
                showSuccess('Budsjett opprettet!');
                this.showBudgetEditor(budget.id);
            } catch (error) {
                showError('Kunne ikke opprette budsjett: ' + error.message);
            }
        };
    }

    async showBudgetEditor(budgetId) {
        try {
            const budget = await api.getBudget(budgetId);
            const accounts = await api.getAccounts();

            // Filter to only income and expense accounts, and sort by account number
            const budgetAccounts = accounts
                .filter(acc => acc.account_type === 'REVENUE' || acc.account_type === 'EXPENSE')
                .sort((a, b) => a.account_number.localeCompare(b.account_number));

            let html = `
                <div class="card">
                    <h2>${budget.name} (${budget.year})</h2>
                    <p>Sett budsjettbeløp per konto. Du kan velge hvordan beløpet fordeles på månedene.</p>

                    <div id="budget-editor-container">
                        <table class="data-table" style="width: 100%;">
                            <thead>
                                <tr>
                                    <th>Konto</th>
                                    <th>Fordeling</th>
                                    <th>Beløp</th>
                                </tr>
                            </thead>
                            <tbody id="budget-accounts-list">
            `;

            for (const account of budgetAccounts) {
                const existingLine = budget.lines?.find(l => l.account_number === account.account_number);
                const totalAmount = existingLine ?
                    budget.lines.filter(l => l.account_number === account.account_number)
                        .reduce((sum, l) => sum + parseFloat(l.amount), 0) : 0;

                html += `
                    <tr data-account="${account.account_number}">
                        <td><strong>${account.account_number}</strong> ${account.account_name}</td>
                        <td>
                            <select class="distribution-type" data-account="${account.account_number}">
                                <option value="">Ikke satt</option>
                                <option value="same">Samme beløp alle måneder</option>
                                <option value="total">Totalsum fordelt på 12 måneder</option>
                            </select>
                        </td>
                        <td>
                            <input type="number" step="0.01" class="budget-amount"
                                data-account="${account.account_number}"
                                placeholder="0.00" value="${totalAmount || ''}">
                        </td>
                    </tr>
                `;
            }

            html += `
                            </tbody>
                        </table>
                    </div>

                    <div style="margin-top: 1rem; display: flex; gap: 1rem;">
                        <button class="btn btn-primary" onclick="app.saveBudgetLines(${budgetId})">Lagre budsjett</button>
                        <button class="btn btn-secondary" onclick="app.showBudgetReport(${budgetId})">Se rapport</button>
                        <button class="btn btn-secondary" onclick="app.loadBudgets()">Tilbake</button>
                    </div>
                </div>
            `;

            document.getElementById('budgets-list').innerHTML = html;

        } catch (error) {
            console.error('Error loading budget editor:', error);
            showError('Kunne ikke laste budsjett');
        }
    }

    async saveBudgetLines(budgetId) {
        try {
            const rows = document.querySelectorAll('#budget-accounts-list tr');
            const lines = [];

            for (const row of rows) {
                const accountNumber = row.dataset.account;
                const distType = row.querySelector('.distribution-type').value;
                const amount = parseFloat(row.querySelector('.budget-amount').value) || 0;

                if (distType && amount !== 0) {
                    lines.push({
                        account_number: accountNumber,
                        distribution_type: distType,
                        amount: amount
                    });
                }
            }

            if (lines.length === 0) {
                showError('Ingen budsjettlinjer å lagre');
                return;
            }

            await api.setBudgetLines(budgetId, lines);
            showSuccess('Budsjett lagret!');

        } catch (error) {
            console.error('Error saving budget lines:', error);
            showError('Kunne ikke lagre budsjett: ' + error.message);
        }
    }

    async showBudgetReport(budgetId) {
        try {
            const report = await api.getBudgetReport(budgetId);
            const budget = report.budget;
            const lines = report.lines;

            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Des'];

            let html = `
                <div class="card">
                    <h2>${budget.name} - Budsjett vs Faktisk</h2>

                    <div style="overflow-x: auto;">
                        <table class="data-table" style="width: 100%; font-size: 0.85rem;">
                            <thead>
                                <tr>
                                    <th style="position: sticky; left: 0; background: white;">Konto</th>
            `;

            for (const month of months) {
                html += `<th style="text-align: right;">${month}</th>`;
            }
            html += `<th style="text-align: right;">Totalt</th></tr></thead><tbody>`;

            for (const line of lines) {
                html += `
                    <tr>
                        <td style="position: sticky; left: 0; background: white;">
                            <strong>${line.account_number}</strong> ${line.account_name}
                        </td>
                `;

                for (const monthData of line.months) {
                    const budget = monthData.budget;
                    const actual = monthData.actual;
                    const variance = monthData.variance;
                    const color = variance > 0 ? 'green' : variance < 0 ? 'red' : 'black';

                    html += `
                        <td style="text-align: right; font-size: 0.8rem;">
                            <div>${formatCurrency(budget)}</div>
                            <div style="color: gray;">${formatCurrency(actual)}</div>
                            <div style="color: ${color}; font-weight: bold;">${variance >= 0 ? '+' : ''}${formatCurrency(variance)}</div>
                        </td>
                    `;
                }

                const totalColor = line.total_variance > 0 ? 'green' : line.total_variance < 0 ? 'red' : 'black';
                html += `
                    <td style="text-align: right; font-weight: bold;">
                        <div>${formatCurrency(line.total_budget)}</div>
                        <div style="color: gray;">${formatCurrency(line.total_actual)}</div>
                        <div style="color: ${totalColor};">${line.total_variance >= 0 ? '+' : ''}${formatCurrency(line.total_variance)}</div>
                    </td>
                </tr>`;
            }

            html += `
                            </tbody>
                        </table>
                    </div>

                    <div style="margin-top: 1rem; padding: 1rem; background: #f0f0f0; border-radius: 4px;">
                        <p><strong>Forklaring:</strong></p>
                        <p>Første linje: Budsjett | Andre linje: Faktisk | Tredje linje: Avvik (grønn = bedre enn budsjett, rød = dårligere)</p>
                    </div>

                    <div style="margin-top: 1rem;">
                        <button class="btn btn-secondary" onclick="app.showBudgetEditor(${budgetId})">Rediger budsjett</button>
                        <button class="btn btn-secondary" onclick="app.loadBudgets()">Tilbake</button>
                    </div>
                </div>
            `;

            document.getElementById('budgets-list').innerHTML = html;

        } catch (error) {
            console.error('Error loading budget report:', error);
            showError('Kunne ikke laste rapport');
        }
    }

    async loadBudgets() {
        try {
            const budgets = await api.getBudgets();
            const container = document.getElementById('budgets-list');

            if (budgets.length === 0) {
                container.innerHTML = '<p>Ingen budsjetter opprettet ennå. Klikk "Nytt budsjett" for å komme i gang.</p>';
                return;
            }

            let html = '<div class="card-grid">';
            for (const budget of budgets) {
                html += `
                    <div class="card">
                        <h3>${budget.name}</h3>
                        <p>År: ${budget.year}</p>
                        <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                            <button class="btn btn-primary" onclick="app.showBudgetReport(${budget.id})">
                                Se rapport
                            </button>
                            <button class="btn btn-secondary" onclick="app.showBudgetEditor(${budget.id})">
                                Rediger
                            </button>
                        </div>
                    </div>
                `;
            }
            html += '</div>';

            container.innerHTML = html;
        } catch (error) {
            console.error('Error loading budgets:', error);
            showError('Kunne ikke laste budsjetter');
        }
    }
}

const app = new App();
window.app = app; // Make app globally accessible for onclick handlers
