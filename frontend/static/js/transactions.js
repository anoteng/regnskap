import api from './api.js';
import { formatCurrency, formatDate, showModal, closeModal, showError, showSuccess } from './utils.js';

class TransactionsManager {
    constructor() {
        this.accounts = [];
        this.categories = [];
        this.bankAccounts = [];
        this._listenersAttached = false;
    }

    async init() {
        await this.loadAccounts();
        await this.loadCategories();
        await this.loadBankAccounts();
        this.populateAccountFilter();
        this.populateMonthFilter();
        if (!this._listenersAttached) {
            this.setupEventListeners();
            this._listenersAttached = true;
        }
        await this.loadTransactions();
    }

    async loadAccounts() {
        this.accounts = await api.getAccounts();
    }

    async loadCategories() {
        this.categories = await api.getCategories();
    }

    async loadBankAccounts() {
        this.bankAccounts = await api.getBankAccounts();
    }

    populateAccountFilter() {
        const select = document.getElementById('filter-account');
        if (!select) return;

        // Find which account IDs are linked to bank accounts
        const bankAccountIds = new Set(this.bankAccounts.map(ba => ba.account_id));

        // Split into bank-linked and other accounts
        const bankLinked = this.accounts.filter(a => bankAccountIds.has(a.id));
        const others = this.accounts.filter(a => !bankAccountIds.has(a.id));

        // Sort each group by account number
        bankLinked.sort((a, b) => a.account_number.localeCompare(b.account_number));
        others.sort((a, b) => a.account_number.localeCompare(b.account_number));

        let html = '<option value="">Alle kontoer</option>';
        if (bankLinked.length > 0) {
            html += '<optgroup label="Bankkontoer">';
            for (const a of bankLinked) {
                html += `<option value="${a.id}">${a.account_number} ${a.account_name}</option>`;
            }
            html += '</optgroup>';
        }
        html += '<optgroup label="Alle kontoer">';
        for (const a of others) {
            html += `<option value="${a.id}">${a.account_number} ${a.account_name}</option>`;
        }
        html += '</optgroup>';

        select.innerHTML = html;
    }

    populateMonthFilter() {
        const select = document.getElementById('filter-month');
        if (!select) return;

        const monthNames = ['Januar', 'Februar', 'Mars', 'April', 'Mai', 'Juni',
                           'Juli', 'August', 'September', 'Oktober', 'November', 'Desember'];
        const now = new Date();

        let html = '<option value="">Velg periode...</option>';

        // Last 12 months including current
        for (let i = 0; i < 12; i++) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            const year = d.getFullYear();
            const month = d.getMonth(); // 0-indexed
            const lastDay = new Date(year, month + 1, 0).getDate();
            const startDate = `${year}-${String(month + 1).padStart(2, '0')}-01`;
            const endDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
            const label = `${monthNames[month]} ${year}`;
            html += `<option value="${startDate}|${endDate}">${label}</option>`;
        }

        select.innerHTML = html;
    }

    setupEventListeners() {
        document.getElementById('new-transaction-btn').addEventListener('click', () => {
            this.showNewTransactionModal();
        });

        document.getElementById('filter-btn').addEventListener('click', () => {
            this.loadTransactions();
        });

        document.getElementById('filter-account')?.addEventListener('change', () => {
            // Reset month filter when account changes
            const monthSelect = document.getElementById('filter-month');
            if (monthSelect) monthSelect.value = '';
            this.loadTransactions();
        });

        document.getElementById('filter-month')?.addEventListener('change', (e) => {
            if (e.target.value) {
                const [start, end] = e.target.value.split('|');
                document.getElementById('filter-start-date').value = start;
                document.getElementById('filter-end-date').value = end;
            } else {
                document.getElementById('filter-start-date').value = '';
                document.getElementById('filter-end-date').value = '';
            }
            this.loadTransactions();
        });

        document.getElementById('import-csv-btn').addEventListener('click', () => {
            this.showImportCSVModal();
        });
    }

    async loadTransactions() {
        const startDate = document.getElementById('filter-start-date').value;
        const endDate = document.getElementById('filter-end-date').value;
        const accountId = document.getElementById('filter-account')?.value;

        const filters = {};
        if (startDate) filters.start_date = startDate;
        if (endDate) filters.end_date = endDate;
        if (accountId) filters.account_id = accountId;

        const transactions = await api.getTransactions(filters);
        this.renderTransactions(transactions);
    }

    renderTransactions(transactions) {
        const list = document.getElementById('transactions-list');

        if (transactions.length === 0) {
            list.innerHTML = '<p>Ingen transaksjoner funnet.</p>';
            return;
        }

        const html = `
            <table class="table">
                <thead>
                    <tr>
                        <th style="width: 30px;"></th>
                        <th>Dato</th>
                        <th>Beskrivelse</th>
                        <th>Referanse</th>
                        <th>Status</th>
                        <th>Debet</th>
                        <th>Kredit</th>
                        <th>Handlinger</th>
                    </tr>
                </thead>
                <tbody>
                    ${transactions.map(t => this.renderTransactionRow(t)).join('')}
                </tbody>
            </table>
        `;

        list.innerHTML = html;
    }

    renderTransactionRow(transaction) {
        const totalDebit = transaction.journal_entries?.reduce((sum, e) => sum + parseFloat(e.debit), 0) || 0;
        const totalCredit = transaction.journal_entries?.reduce((sum, e) => sum + parseFloat(e.credit), 0) || 0;

        return `
            <tr class="transaction-row">
                <td>
                    <button class="btn btn-sm" onclick="window.transactionsManager.toggleDetails(${transaction.id})"
                            id="toggle-btn-${transaction.id}" style="padding: 0.25rem 0.5rem;">
                        ▶
                    </button>
                </td>
                <td>${formatDate(transaction.transaction_date)}</td>
                <td>${transaction.description}</td>
                <td>${transaction.reference || '-'}</td>
                <td><span class="status-badge status-${transaction.status?.toLowerCase() || 'posted'}">${transaction.status || 'POSTED'}</span></td>
                <td class="amount">${totalDebit.toFixed(2)} kr</td>
                <td class="amount">${totalCredit.toFixed(2)} kr</td>
                <td>
                    ${transaction.status !== 'DRAFT' ? `
                        <button class="btn btn-sm btn-secondary" onclick="window.transactionsManager.reverseTransaction(${transaction.id})">
                            Reverser
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-danger" onclick="window.transactionsManager.deleteTransaction(${transaction.id})">Slett</button>
                </td>
            </tr>
            <tr id="details-${transaction.id}" class="transaction-details" style="display: none;">
                <td></td>
                <td colspan="7">
                    <div style="padding: 1rem; background: var(--bg-secondary); border-radius: 4px;">
                        <h4 style="margin-top: 0;">Posteringer</h4>
                        <table class="table" style="margin-bottom: 0;">
                            <thead>
                                <tr>
                                    <th>Konto</th>
                                    <th>Kontonavn</th>
                                    <th>Debet</th>
                                    <th>Kredit</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${transaction.journal_entries?.map(entry => `
                                    <tr>
                                        <td>${entry.account ? entry.account.account_number : entry.account_id}</td>
                                        <td>${entry.account ? entry.account.account_name : 'Ukjent konto'}</td>
                                        <td class="amount">${parseFloat(entry.debit).toFixed(2)} kr</td>
                                        <td class="amount">${parseFloat(entry.credit).toFixed(2)} kr</td>
                                    </tr>
                                `).join('') || '<tr><td colspan="4">Ingen posteringer</td></tr>'}
                                <tr style="font-weight: bold; border-top: 2px solid var(--border-color);">
                                    <td colspan="2">Sum</td>
                                    <td class="amount">${totalDebit.toFixed(2)} kr</td>
                                    <td class="amount">${totalCredit.toFixed(2)} kr</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </td>
            </tr>
        `;
    }

    toggleDetails(id) {
        const detailsRow = document.getElementById(`details-${id}`);
        const toggleBtn = document.getElementById(`toggle-btn-${id}`);

        if (detailsRow.style.display === 'none') {
            detailsRow.style.display = 'table-row';
            toggleBtn.textContent = '▼';
        } else {
            detailsRow.style.display = 'none';
            toggleBtn.textContent = '▶';
        }
    }

    showNewTransactionModal() {
        const accountOptions = this.accounts
            .map(a => `<option value="${a.id}">${a.account_number} - ${a.account_name}</option>`)
            .join('');

        const content = `
            <form id="new-transaction-form">
                <div class="form-group">
                    <label>Dato</label>
                    <input type="date" id="trans-date" required>
                </div>
                <div class="form-group">
                    <label>Beskrivelse</label>
                    <input type="text" id="trans-description" required>
                </div>
                <div class="form-group">
                    <label>Referanse</label>
                    <input type="text" id="trans-reference">
                </div>

                <h3>Posteringer (dobbelt bokføring)</h3>
                <div id="journal-entries">
                    <div class="journal-entry">
                        <div class="form-group">
                            <label>Konto</label>
                            <select class="entry-account" required>${accountOptions}</select>
                        </div>
                        <div class="form-group">
                            <label>Debet</label>
                            <input type="number" step="0.01" class="entry-debit" value="0">
                        </div>
                        <div class="form-group">
                            <label>Kredit</label>
                            <input type="number" step="0.01" class="entry-credit" value="0">
                        </div>
                        <div class="form-group">
                            <label>Beskrivelse</label>
                            <input type="text" class="entry-description">
                        </div>
                    </div>
                </div>

                <button type="button" id="add-entry-btn" class="btn btn-secondary">Legg til postering</button>
                <div style="margin-top: 1rem;">
                    <button type="submit" class="btn btn-primary">Lagre transaksjon</button>
                </div>
            </form>
        `;

        showModal('Ny transaksjon', content);

        document.getElementById('add-entry-btn').addEventListener('click', () => {
            const container = document.getElementById('journal-entries');
            const entry = document.createElement('div');
            entry.className = 'journal-entry';
            entry.innerHTML = `
                <div class="form-group">
                    <select class="entry-account" required>${accountOptions}</select>
                </div>
                <div class="form-group">
                    <input type="number" step="0.01" class="entry-debit" value="0">
                </div>
                <div class="form-group">
                    <input type="number" step="0.01" class="entry-credit" value="0">
                </div>
                <div class="form-group">
                    <input type="text" class="entry-description">
                </div>
                <button type="button" class="btn btn-danger" onclick="this.parentElement.remove()">X</button>
            `;
            container.appendChild(entry);
        });

        document.getElementById('new-transaction-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.createTransaction();
        });
    }

    async createTransaction() {
        const date = document.getElementById('trans-date').value;
        const description = document.getElementById('trans-description').value;
        const reference = document.getElementById('trans-reference').value;

        const entries = Array.from(document.querySelectorAll('.journal-entry')).map(entry => ({
            account_id: parseInt(entry.querySelector('.entry-account').value),
            debit: parseFloat(entry.querySelector('.entry-debit').value) || 0,
            credit: parseFloat(entry.querySelector('.entry-credit').value) || 0,
            description: entry.querySelector('.entry-description').value,
        }));

        const totalDebit = entries.reduce((sum, e) => sum + e.debit, 0);
        const totalCredit = entries.reduce((sum, e) => sum + e.credit, 0);

        if (Math.abs(totalDebit - totalCredit) > 0.01) {
            showError(`Transaksjonen er ikke balansert. Debet: ${totalDebit}, Kredit: ${totalCredit}`);
            return;
        }

        try {
            await api.createTransaction({
                transaction_date: date,
                description,
                reference: reference || null,
                journal_entries: entries,
                category_ids: [],
            });

            closeModal();
            showSuccess('Transaksjon opprettet');
            await this.loadTransactions();
        } catch (error) {
            showError(error.message);
        }
    }

    async deleteTransaction(id) {
        if (!confirm('Er du sikker på at du vil slette denne transaksjonen?')) {
            return;
        }

        try {
            await api.deleteTransaction(id);
            showSuccess('Transaksjon slettet');
            await this.loadTransactions();
        } catch (error) {
            showError(error.message);
        }
    }

    async reverseTransaction(id) {
        if (!confirm('Dette vil opprette en reverseringspostering som nullstiller denne transaksjonen. Fortsette?')) {
            return;
        }

        try {
            const result = await api.reverseTransaction(id);
            showSuccess(`Transaksjon reversert. Reverseringsbilag ID: ${result.reversing_id}`);
            await this.loadTransactions();
        } catch (error) {
            showError(error.message);
        }
    }

    async showImportCSVModal() {
        this.csvMappings = await api.getCSVMappings();

        const bankAccountOptions = this.bankAccounts
            .map(ba => `<option value="${ba.id}">${ba.name}</option>`)
            .join('');

        const mappingOptions = this.csvMappings
            .map(m => `<option value="${m.id}">${m.name}</option>`)
            .join('');

        const content = `
            <div id="csv-wizard">
                <!-- Step 1: Select file and bank account -->
                <div id="step1" class="wizard-step">
                    <h3>Steg 1: Velg fil og bankkonto</h3>
                    <div class="form-group">
                        <label>Bankkonto</label>
                        <select id="import-bank-account" required>
                            ${bankAccountOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>CSV-fil</label>
                        <input type="file" id="import-file" accept=".csv" required>
                    </div>
                    <div class="form-group">
                        <label>Skilletegn</label>
                        <select id="csv-delimiter">
                            <option value=",">Komma (,)</option>
                            <option value=";" selected>Semikolon (;)</option>
                            <option value="\t">Tab</option>
                        </select>
                        <small style="color: var(--text-secondary);">
                            Norske banker bruker vanligvis semikolon (;)
                        </small>
                    </div>
                    <div class="form-group" ${this.csvMappings.length === 0 ? 'style="display:none;"' : ''}>
                        <label>Bruk eksisterende mapping (valgfri)</label>
                        <select id="existing-mapping">
                            <option value="">Lag ny mapping...</option>
                            ${mappingOptions}
                        </select>
                    </div>
                    <button id="preview-btn" class="btn btn-primary">Neste</button>
                </div>

                <!-- Step 2: Map columns -->
                <div id="step2" class="wizard-step" style="display: none;">
                    <h3>Steg 2: Match kolonner</h3>
                    <div id="preview-container"></div>
                    <div id="mapping-form"></div>
                    <div style="margin-top: 1rem;">
                        <button id="back-btn" class="btn btn-secondary">Tilbake</button>
                        <button id="import-btn" class="btn btn-primary">Importer</button>
                    </div>
                </div>
            </div>
        `;

        showModal('Importer CSV', content);

        document.getElementById('preview-btn').addEventListener('click', async () => {
            await this.handleCSVPreview();
        });

        document.getElementById('existing-mapping')?.addEventListener('change', (e) => {
            this.selectedMappingId = e.target.value ? parseInt(e.target.value) : null;

            // Pre-fill delimiter if mapping is selected
            if (this.selectedMappingId) {
                const mapping = this.csvMappings.find(m => m.id === this.selectedMappingId);
                if (mapping && mapping.delimiter) {
                    document.getElementById('csv-delimiter').value = mapping.delimiter;
                }
            }
        });
    }

    async handleCSVPreview() {
        const file = document.getElementById('import-file').files[0];
        if (!file) {
            showError('Vennligst velg en fil');
            return;
        }

        const delimiter = document.getElementById('csv-delimiter').value;

        try {
            const preview = await api.previewCSV(file, delimiter);
            this.csvPreview = preview;
            this.csvFile = file;
            this.csvDelimiter = delimiter;

            // Check if we have a selected mapping
            if (this.selectedMappingId) {
                const mapping = this.csvMappings.find(m => m.id === this.selectedMappingId);
                if (mapping) {
                    this.currentMapping = mapping;
                }
            }

            this.showMappingStep(preview);
        } catch (error) {
            showError(error.message);
        }
    }

    showMappingStep(preview) {
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';

        // Show preview
        const previewHtml = `
            <div style="margin-bottom: 1rem;">
                <p><strong>Antall rader:</strong> ${preview.total_rows}</p>
                <div style="overflow-x: auto;">
                    <table class="table">
                        <thead>
                            <tr>${preview.columns.map(col => `<th>${col}</th>`).join('')}</tr>
                        </thead>
                        <tbody>
                            ${preview.preview.map(row =>
                                `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`
                            ).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        document.getElementById('preview-container').innerHTML = previewHtml;

        // Show mapping form
        const columnOptions = preview.columns.map(col => `<option value="${col}">${col}</option>`).join('');

        const mappingFormHtml = `
            <h4>Match CSV-kolonner til felter</h4>
            <div class="form-group">
                <label>Dato-kolonne</label>
                <select id="map-date" required>${columnOptions}</select>
            </div>
            <div class="form-group">
                <label>Datoformat</label>
                <select id="map-date-format">
                    <option value="YYYY-MM-DD">YYYY-MM-DD (2025-01-26)</option>
                    <option value="DD.MM.YYYY">DD.MM.YYYY (26.01.2025)</option>
                    <option value="DD/MM/YYYY">DD/MM/YYYY (26/01/2025)</option>
                    <option value="MM/DD/YYYY">MM/DD/YYYY (01/26/2025)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Beskrivelse-kolonne</label>
                <select id="map-description" required>${columnOptions}</select>
            </div>
            <div class="form-group">
                <label>Beløp-kolonne</label>
                <select id="map-amount" required>${columnOptions}</select>
            </div>
            <div class="form-group">
                <label>Desimalskilletegn</label>
                <select id="map-decimal">
                    <option value=".">Punktum (.)</option>
                    <option value=",">Komma (,)</option>
                </select>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="map-invert-amount">
                    Inverter fortegn (negativ = utgift, positiv = inntekt)
                </label>
                <small style="display: block; color: var(--text-secondary); margin-top: 0.25rem;">
                    Kryss av her hvis banken din bruker negativt fortegn for utgifter
                </small>
            </div>
            <div class="form-group">
                <label>Referanse-kolonne (valgfri)</label>
                <select id="map-reference">
                    <option value="">Ingen</option>
                    ${columnOptions}
                </select>
            </div>
            <div class="form-group">
                <label>Hopp over første N rader</label>
                <input type="number" id="map-skip" value="0" min="0">
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="save-mapping">
                    Lagre denne mappingen for gjenbruk
                </label>
            </div>
            <div class="form-group" id="mapping-name-group" style="display: none;">
                <label>Navn på mapping (f.eks. "DNB", "Nordea")</label>
                <input type="text" id="mapping-name" placeholder="Min Bank">
            </div>
        `;
        document.getElementById('mapping-form').innerHTML = mappingFormHtml;

        // Pre-fill if we have a mapping
        if (this.currentMapping) {
            document.getElementById('map-date').value = this.currentMapping.date_column;
            document.getElementById('map-date-format').value = this.currentMapping.date_format;
            document.getElementById('map-description').value = this.currentMapping.description_column;
            document.getElementById('map-amount').value = this.currentMapping.amount_column;
            document.getElementById('map-decimal').value = this.currentMapping.decimal_separator;
            document.getElementById('map-invert-amount').checked = this.currentMapping.invert_amount || false;
            if (this.currentMapping.reference_column) {
                document.getElementById('map-reference').value = this.currentMapping.reference_column;
            }
            document.getElementById('map-skip').value = this.currentMapping.skip_rows;
        }

        // Toggle mapping name field
        document.getElementById('save-mapping').addEventListener('change', (e) => {
            document.getElementById('mapping-name-group').style.display = e.target.checked ? 'block' : 'none';
        });

        document.getElementById('back-btn').addEventListener('click', () => {
            document.getElementById('step2').style.display = 'none';
            document.getElementById('step1').style.display = 'block';
        });

        document.getElementById('import-btn').addEventListener('click', async () => {
            await this.performImport();
        });
    }

    async performImport() {
        const bankAccountId = document.getElementById('import-bank-account').value;

        const mappingConfig = {
            date_column: document.getElementById('map-date').value,
            date_format: document.getElementById('map-date-format').value,
            description_column: document.getElementById('map-description').value,
            amount_column: document.getElementById('map-amount').value,
            decimal_separator: document.getElementById('map-decimal').value,
            invert_amount: document.getElementById('map-invert-amount').checked,
            delimiter: this.csvDelimiter,
            reference_column: document.getElementById('map-reference').value || null,
            skip_rows: parseInt(document.getElementById('map-skip').value) || 0
        };

        try {
            // Save mapping if requested
            let csvMappingId = this.selectedMappingId;
            if (document.getElementById('save-mapping').checked) {
                const mappingName = document.getElementById('mapping-name').value.trim();
                if (!mappingName) {
                    showError('Vennligst gi mappingen et navn');
                    return;
                }

                const savedMapping = await api.createCSVMapping({
                    name: mappingName,
                    ...mappingConfig
                });
                csvMappingId = savedMapping.id;
            }

            // Perform import
            const result = await api.importCSV(bankAccountId, this.csvFile, mappingConfig, csvMappingId);

            closeModal();

            let message = `Import fullført!\nImportert: ${result.imported}\nFeilet: ${result.failed}`;
            if (result.errors && result.errors.length > 0) {
                message += `\n\nFørste feil:\n${result.errors.slice(0, 3).join('\n')}`;
            }

            showSuccess(message);
            await this.loadTransactions();
        } catch (error) {
            showError(error.message);
        }
    }
}

const transactionsManager = new TransactionsManager();
window.transactionsManager = transactionsManager;

export default transactionsManager;
