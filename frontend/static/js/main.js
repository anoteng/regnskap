import auth from './auth.js';
import api from './api.js';
import ledgerManager from './ledgers.js';
import transactionsManager from './transactions.js';
import bankAccountsManager from './bank-accounts.js';
import postingQueueManager from './posting-queue.js';
import receiptsManager from './receipts.js';
import reportsManager from './reports.js';
import adminManager from './admin.js';
import { formatCurrency, formatDate, getTodayDate, getFirstDayOfMonth, getLastDayOfMonth, showModal, closeModal, showError, showSuccess } from './utils.js';

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

            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Des'];

            for (const account of budgetAccounts) {
                const accountLines = budget.lines?.filter(l => l.account_id === account.id) || [];
                const totalAmount = accountLines.reduce((sum, l) => sum + parseFloat(l.amount), 0);

                // Detect existing distribution type
                let existingDistType = '';
                let monthlyAmounts = [0,0,0,0,0,0,0,0,0,0,0,0];
                if (accountLines.length === 12) {
                    for (const l of accountLines) {
                        monthlyAmounts[l.period - 1] = parseFloat(l.amount);
                    }
                    const allSame = monthlyAmounts.every(a => Math.abs(a - monthlyAmounts[0]) < 0.01);
                    if (allSame && monthlyAmounts[0] !== 0) {
                        existingDistType = 'same';
                    } else if (totalAmount !== 0) {
                        existingDistType = 'manual';
                    }
                }

                html += `
                    <tr data-account-id="${account.id}">
                        <td><strong>${account.account_number}</strong> ${account.account_name}</td>
                        <td>
                            <select class="distribution-type" onchange="app.onDistributionTypeChanged(this)">
                                <option value="">Ikke satt</option>
                                <option value="same" ${existingDistType === 'same' ? 'selected' : ''}>Samme beløp alle måneder</option>
                                <option value="total">Totalsum fordelt på 12 måneder</option>
                                <option value="manual" ${existingDistType === 'manual' ? 'selected' : ''}>Spesifiser per måned</option>
                            </select>
                        </td>
                        <td class="budget-amount-cell">
                            <input type="number" step="0.01" class="budget-amount"
                                placeholder="0.00" value="${existingDistType === 'same' ? monthlyAmounts[0] : (existingDistType === 'manual' ? '' : (totalAmount || ''))}"
                                style="${existingDistType === 'manual' ? 'display:none' : ''}">
                            <div class="monthly-amounts" style="${existingDistType === 'manual' ? '' : 'display:none'}">
                                <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
                                    ${monthNames.map((m, i) => `
                                        <div>
                                            <label style="font-size: 0.75rem; color: #666;">${m}</label>
                                            <input type="number" step="0.01" class="month-amount" data-month="${i}"
                                                style="width: 100%; padding: 2px 4px; font-size: 0.85rem;"
                                                placeholder="0" value="${existingDistType === 'manual' ? (monthlyAmounts[i] || '') : ''}">
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
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

    onDistributionTypeChanged(select) {
        const row = select.closest('tr');
        const amountInput = row.querySelector('.budget-amount');
        const monthlyDiv = row.querySelector('.monthly-amounts');

        if (select.value === 'manual') {
            amountInput.style.display = 'none';
            monthlyDiv.style.display = '';
        } else {
            amountInput.style.display = '';
            monthlyDiv.style.display = 'none';
        }
    }

    async saveBudgetLines(budgetId) {
        try {
            const rows = document.querySelectorAll('#budget-accounts-list tr');
            const lines = [];

            for (const row of rows) {
                const accountId = parseInt(row.dataset.accountId);
                const distType = row.querySelector('.distribution-type').value;

                if (!distType) continue;

                if (distType === 'manual') {
                    const monthInputs = row.querySelectorAll('.month-amount');
                    const monthlyAmounts = Array.from(monthInputs).map(inp => parseFloat(inp.value) || 0);
                    const hasAny = monthlyAmounts.some(a => a !== 0);
                    if (hasAny) {
                        lines.push({
                            account_id: accountId,
                            distribution_type: 'manual',
                            monthly_amounts: monthlyAmounts
                        });
                    }
                } else {
                    const amount = parseFloat(row.querySelector('.budget-amount').value) || 0;
                    if (amount !== 0) {
                        lines.push({
                            account_id: accountId,
                            distribution_type: distType,
                            amount: amount
                        });
                    }
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
            this._currentBudgetId = budgetId;

            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Des'];
            const now = new Date();
            const currentMonth = now.getMonth(); // 0-indexed
            const prevMonth = currentMonth === 0 ? 11 : currentMonth - 1;

            // Default visible months: previous, current, and total
            const defaultVisibleMonths = new Set([prevMonth, currentMonth]);

            // Split lines by type
            const expenseLines = lines.filter(l => l.account_type === 'EXPENSE');
            const revenueLines = lines.filter(l => l.account_type === 'REVENUE');
            const otherLines = lines.filter(l => l.account_type !== 'EXPENSE' && l.account_type !== 'REVENUE');

            // Positive variance = over budget = red, negative = under budget = green
            const varianceColor = (variance) => {
                if (variance === 0) return 'inherit';
                return variance > 0 ? '#c0392b' : '#27ae60';
            };

            const renderSection = (title, sectionLines, sectionId, defaultShow) => {
                if (sectionLines.length === 0) return '';
                let s = `
                    <div style="margin-bottom: 1.5rem;">
                        <h3 style="cursor: pointer; user-select: none; margin-bottom: 0.5rem;"
                            onclick="app.toggleBudgetSection('${sectionId}')">
                            <span id="${sectionId}-arrow">${defaultShow ? '▼' : '▶'}</span> ${title}
                        </h3>
                        <div id="${sectionId}" style="display: ${defaultShow ? 'block' : 'none'}; overflow-x: auto;">
                            <table class="data-table" style="width: 100%; font-size: 0.85rem;">
                                <thead>
                                    <tr>
                                        <th style="position: sticky; left: 0; background: var(--bg-primary, white); z-index: 1; min-width: 200px;">Konto</th>
                `;
                for (let i = 0; i < 12; i++) {
                    const visible = defaultVisibleMonths.has(i);
                    s += `<th class="budget-month-col budget-month-${i}" style="text-align: right;${visible ? '' : ' display: none;'}">${monthNames[i]}</th>`;
                }
                s += `<th style="text-align: right; background: var(--bg-secondary, #f5f5f5);">Hittil i år</th>`;
                s += `<th style="text-align: right;">Totalt</th></tr></thead><tbody>`;

                // Sum row
                const totals = { months: Array(12).fill(null).map(() => ({budget: 0, actual: 0, variance: 0})), budget: 0, actual: 0, variance: 0, ytdBudget: 0, ytdActual: 0, ytdVariance: 0 };

                for (const line of sectionLines) {
                    s += `<tr>
                        <td style="position: sticky; left: 0; background: var(--bg-primary, white); z-index: 1;">
                            <strong>${line.account_number}</strong> ${line.account_name}
                        </td>`;

                    let ytdBudget = 0, ytdActual = 0;
                    for (let i = 0; i < 12; i++) {
                        const md = line.months[i];
                        const visible = defaultVisibleMonths.has(i);
                        const color = varianceColor(md.variance);
                        totals.months[i].budget += md.budget;
                        totals.months[i].actual += md.actual;
                        totals.months[i].variance += md.variance;

                        // YTD: include months up to and including current month
                        if (i <= currentMonth) {
                            ytdBudget += md.budget;
                            ytdActual += md.actual;
                        }

                        const drilldown = md.actual !== 0 ? `<a href="#" onclick="app.showBudgetDrilldown(${line.account_id}, ${i + 1}, '${line.account_number} ${line.account_name}', '${monthNames[i]}'); return false;" style="color: gray; text-decoration: none; border-bottom: 1px dashed gray;">${formatCurrency(md.actual)}</a>` : `<span style="color: gray;">${formatCurrency(md.actual)}</span>`;

                        s += `<td class="budget-month-col budget-month-${i}" style="text-align: right; font-size: 0.8rem;${visible ? '' : ' display: none;'}">
                            <div>${formatCurrency(md.budget)}</div>
                            <div>${drilldown}</div>
                            <div style="color: ${color}; font-weight: bold;">${md.variance >= 0 ? '+' : ''}${formatCurrency(md.variance)}</div>
                        </td>`;
                    }

                    const ytdVariance = ytdActual - ytdBudget;
                    totals.ytdBudget += ytdBudget;
                    totals.ytdActual += ytdActual;
                    totals.ytdVariance += ytdVariance;

                    totals.budget += line.total_budget;
                    totals.actual += line.total_actual;
                    totals.variance += line.total_variance;

                    const ytdDrilldown = ytdActual !== 0 ? `<a href="#" onclick="app.showBudgetDrilldown(${line.account_id}, null, '${line.account_number} ${line.account_name}', 'Hittil i år'); return false;" style="color: gray; text-decoration: none; border-bottom: 1px dashed gray;">${formatCurrency(ytdActual)}</a>` : `<span style="color: gray;">${formatCurrency(ytdActual)}</span>`;

                    s += `<td style="text-align: right; font-weight: bold; background: var(--bg-secondary, #f5f5f5); font-size: 0.8rem;">
                        <div>${formatCurrency(ytdBudget)}</div>
                        <div>${ytdDrilldown}</div>
                        <div style="color: ${varianceColor(ytdVariance)};">${ytdVariance >= 0 ? '+' : ''}${formatCurrency(ytdVariance)}</div>
                    </td>`;

                    const totalDrilldown = line.total_actual !== 0 ? `<a href="#" onclick="app.showBudgetDrilldown(${line.account_id}, null, '${line.account_number} ${line.account_name}', 'Hele året'); return false;" style="color: gray; text-decoration: none; border-bottom: 1px dashed gray;">${formatCurrency(line.total_actual)}</a>` : `<span style="color: gray;">${formatCurrency(line.total_actual)}</span>`;

                    const tc = varianceColor(line.total_variance);
                    s += `<td style="text-align: right; font-weight: bold;">
                        <div>${formatCurrency(line.total_budget)}</div>
                        <div>${totalDrilldown}</div>
                        <div style="color: ${tc};">${line.total_variance >= 0 ? '+' : ''}${formatCurrency(line.total_variance)}</div>
                    </td></tr>`;
                }

                // Sum row
                if (sectionLines.length > 1) {
                    s += `<tr style="border-top: 2px solid var(--border-color, #ccc); font-weight: bold;">
                        <td style="position: sticky; left: 0; background: var(--bg-primary, white); z-index: 1;">Sum ${title.toLowerCase()}</td>`;
                    for (let i = 0; i < 12; i++) {
                        const mt = totals.months[i];
                        const visible = defaultVisibleMonths.has(i);
                        const color = varianceColor(mt.variance);
                        s += `<td class="budget-month-col budget-month-${i}" style="text-align: right; font-size: 0.8rem;${visible ? '' : ' display: none;'}">
                            <div>${formatCurrency(mt.budget)}</div>
                            <div style="color: gray;">${formatCurrency(mt.actual)}</div>
                            <div style="color: ${color}; font-weight: bold;">${mt.variance >= 0 ? '+' : ''}${formatCurrency(mt.variance)}</div>
                        </td>`;
                    }
                    s += `<td style="text-align: right; background: var(--bg-secondary, #f5f5f5);">
                        <div>${formatCurrency(totals.ytdBudget)}</div>
                        <div style="color: gray;">${formatCurrency(totals.ytdActual)}</div>
                        <div style="color: ${varianceColor(totals.ytdVariance)};">${totals.ytdVariance >= 0 ? '+' : ''}${formatCurrency(totals.ytdVariance)}</div>
                    </td>`;
                    s += `<td style="text-align: right;">
                        <div>${formatCurrency(totals.budget)}</div>
                        <div style="color: gray;">${formatCurrency(totals.actual)}</div>
                        <div style="color: ${varianceColor(totals.variance)};">${totals.variance >= 0 ? '+' : ''}${formatCurrency(totals.variance)}</div>
                    </td></tr>`;
                }

                s += `</tbody></table></div></div>`;
                return s;
            };

            // Month toggle buttons
            let monthToggles = '<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 1rem;">';
            monthToggles += '<span style="margin-right: 0.5rem; font-weight: bold; align-self: center;">Måneder:</span>';
            for (let i = 0; i < 12; i++) {
                const active = defaultVisibleMonths.has(i);
                monthToggles += `<button class="btn btn-sm budget-month-toggle" data-month="${i}"
                    style="padding: 0.25rem 0.5rem; font-size: 0.8rem; ${active ? 'background: var(--primary-color, #007bff); color: white;' : ''}"
                    onclick="app.toggleBudgetMonth(${i}, this)">${monthNames[i]}</button>`;
            }
            monthToggles += `<button class="btn btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.8rem; margin-left: 0.5rem;"
                onclick="app.toggleAllBudgetMonths(true)">Vis alle</button>`;
            monthToggles += `<button class="btn btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;"
                onclick="app.toggleAllBudgetMonths(false)">Skjul alle</button>`;
            monthToggles += '</div>';

            let html = `
                <div class="card">
                    <h2>${budget.name} - Budsjett vs Faktisk</h2>
                    ${monthToggles}
                    ${renderSection('Utgifter', expenseLines, 'budget-expenses', true)}
                    ${renderSection('Inntekter', revenueLines, 'budget-revenue', false)}
                    ${renderSection('Andre', otherLines, 'budget-other', false)}

                    <div style="margin-top: 1rem; padding: 0.75rem; background: var(--bg-secondary, #f0f0f0); border-radius: 4px; font-size: 0.85rem;">
                        <strong>Forklaring:</strong>
                        Linje 1: Budsjett | Linje 2: <span style="color: gray;">Faktisk</span> |
                        Linje 3: Avvik (<span style="color: #c0392b;">rød = over budsjett</span>, <span style="color: #27ae60;">grønn = under budsjett</span>)
                    </div>

                    <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
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

    toggleBudgetSection(sectionId) {
        const section = document.getElementById(sectionId);
        const arrow = document.getElementById(sectionId + '-arrow');
        if (section.style.display === 'none') {
            section.style.display = 'block';
            arrow.textContent = '▼';
        } else {
            section.style.display = 'none';
            arrow.textContent = '▶';
        }
    }

    toggleBudgetMonth(monthIndex, btn) {
        const cols = document.querySelectorAll(`.budget-month-${monthIndex}`);
        const isVisible = cols.length > 0 && cols[0].style.display !== 'none';
        for (const col of cols) {
            col.style.display = isVisible ? 'none' : '';
        }
        if (isVisible) {
            btn.style.background = '';
            btn.style.color = '';
        } else {
            btn.style.background = 'var(--primary-color, #007bff)';
            btn.style.color = 'white';
        }
    }

    toggleAllBudgetMonths(show) {
        for (let i = 0; i < 12; i++) {
            const cols = document.querySelectorAll(`.budget-month-${i}`);
            for (const col of cols) {
                col.style.display = show ? '' : 'none';
            }
        }
        const btns = document.querySelectorAll('.budget-month-toggle');
        for (const btn of btns) {
            if (show) {
                btn.style.background = 'var(--primary-color, #007bff)';
                btn.style.color = 'white';
            } else {
                btn.style.background = '';
                btn.style.color = '';
            }
        }
    }

    async showBudgetDrilldown(accountId, month, accountLabel, periodLabel) {
        try {
            const transactions = await api.getBudgetDrilldown(this._currentBudgetId, accountId, month);

            let totalDebit = 0, totalCredit = 0;
            const rows = transactions.map(t => {
                totalDebit += t.debit;
                totalCredit += t.credit;
                return `<tr>
                    <td style="white-space: nowrap;">${formatDate(t.date)}</td>
                    <td>${t.description}</td>
                    <td style="text-align: right;">${t.debit ? formatCurrency(t.debit) : ''}</td>
                    <td style="text-align: right;">${t.credit ? formatCurrency(t.credit) : ''}</td>
                    <td style="text-align: right; font-weight: bold;">${formatCurrency(t.amount)}</td>
                </tr>`;
            }).join('');

            const netAmount = totalDebit - totalCredit;
            const content = `
                <div style="max-height: 70vh; overflow-y: auto;">
                    <p style="color: gray; margin-bottom: 1rem;">${transactions.length} transaksjoner</p>
                    <table class="data-table" style="width: 100%; font-size: 0.85rem;">
                        <thead>
                            <tr>
                                <th>Dato</th>
                                <th>Beskrivelse</th>
                                <th style="text-align: right;">Debet</th>
                                <th style="text-align: right;">Kredit</th>
                                <th style="text-align: right;">Netto</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows || '<tr><td colspan="5">Ingen transaksjoner</td></tr>'}
                            <tr style="border-top: 2px solid var(--border-color, #ccc); font-weight: bold;">
                                <td colspan="2">Sum</td>
                                <td style="text-align: right;">${formatCurrency(totalDebit)}</td>
                                <td style="text-align: right;">${formatCurrency(totalCredit)}</td>
                                <td style="text-align: right;">${formatCurrency(netAmount)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            `;

            showModal(`${accountLabel} — ${periodLabel}`, content);
        } catch (error) {
            console.error('Error loading drilldown:', error);
            showError('Kunne ikke laste transaksjoner');
        }
    }

    async deleteBudget(budgetId, budgetName) {
        if (!confirm(`Er du sikker på at du vil slette budsjettet "${budgetName}"?`)) {
            return;
        }
        try {
            await api.deleteBudget(budgetId);
            showSuccess('Budsjett slettet');
            this.loadBudgets();
        } catch (error) {
            console.error('Error deleting budget:', error);
            showError('Kunne ikke slette budsjett: ' + error.message);
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
                            <button class="btn btn-danger" onclick="app.deleteBudget(${budget.id}, '${budget.name.replace(/'/g, "\\'")}')">
                                Slett
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
