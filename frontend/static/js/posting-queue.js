import api from './api.js';
import { showModal, closeModal, showError, showSuccess } from './utils.js';

class PostingQueueManager {
    constructor() {
        this.transactions = [];
        this.accounts = [];
        this.chainSuggestions = [];
        this.currentPage = 0;
        this.pageSize = 50;
        this.totalCount = 0;
    }

    init() {
        const postAllBtn = document.getElementById('post-all-btn');
        if (postAllBtn && !postAllBtn.dataset.listenerAdded) {
            postAllBtn.dataset.listenerAdded = 'true';
            postAllBtn.addEventListener('click', () => this.postAllTransactions());
        }
    }

    async loadQueue(page = 0) {
        try {
            this.currentPage = page;
            const skip = page * this.pageSize;
            const response = await api.getPostingQueue(skip, this.pageSize);
            this.transactions = response.transactions;
            this.totalCount = response.total;
            this.accounts = await api.getAccounts();

            // Fetch chain suggestions
            try {
                const chainResponse = await api.getChainSuggestions();
                this.chainSuggestions = chainResponse.suggestions || [];
            } catch (e) {
                console.error('Could not fetch chain suggestions:', e);
                this.chainSuggestions = [];
            }

            this.renderQueue();
        } catch (error) {
            console.error('Error loading posting queue:', error);
            showError('Kunne ikke laste posteringskø: ' + error.message);
        }
    }

    renderQueue() {
        const container = document.getElementById('posting-queue-list');

        if (this.totalCount === 0) {
            container.innerHTML = `
                <div class="card">
                    <p>Ingen transaksjoner i posteringskøen.</p>
                    <p>Importer CSV-filer fra Transaksjoner-siden for å se dem her.</p>
                </div>
            `;
            return;
        }

        // Count balanced transactions on current page
        const balancedCount = this.transactions.filter(t => {
            const totalDebit = t.journal_entries.reduce((sum, e) => sum + parseFloat(e.debit), 0);
            const totalCredit = t.journal_entries.reduce((sum, e) => sum + parseFloat(e.credit), 0);
            return Math.abs(totalDebit - totalCredit) < 0.01 && t.journal_entries.length >= 2;
        }).length;

        const unbalancedCount = this.transactions.length - balancedCount;

        // Calculate pagination
        const totalPages = Math.ceil(this.totalCount / this.pageSize);
        const startItem = this.currentPage * this.pageSize + 1;
        const endItem = Math.min((this.currentPage + 1) * this.pageSize, this.totalCount);

        const chainBannerHtml = this.renderChainSuggestionsBanner();

        const html = `
            ${chainBannerHtml}
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <div>
                        <strong>${this.totalCount}</strong> transaksjon(er) totalt i kø
                        ${unbalancedCount > 0 ? `<br><small style="color: var(--danger-color);">⚠ ${unbalancedCount} transaksjon(er) på denne siden må redigeres</small>` : ''}
                    </div>
                    ${totalPages > 1 ? `
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <button class="btn btn-sm"
                                    ${this.currentPage === 0 ? 'disabled' : ''}
                                    onclick="postingQueueManager.loadQueue(${this.currentPage - 1})">
                                ← Forrige
                            </button>
                            <span>Side ${this.currentPage + 1} av ${totalPages} (${startItem}-${endItem})</span>
                            <button class="btn btn-sm"
                                    ${this.currentPage >= totalPages - 1 ? 'disabled' : ''}
                                    onclick="postingQueueManager.loadQueue(${this.currentPage + 1})">
                                Neste →
                            </button>
                        </div>
                    ` : ''}
                </div>
                <div id="chain-action-bar" style="display: none; background: #f0f9ff; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem; align-items: center; gap: 0.5rem;"></div>
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width: 30px;"></th>
                            <th style="width: 30px;"></th>
                            <th>Dato</th>
                            <th>Beskrivelse</th>
                            <th>Referanse</th>
                            <th>Kilde</th>
                            <th>Debet</th>
                            <th>Kredit</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.transactions.map(t => this.renderTransactionRow(t)).join('')}
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    }

    renderTransactionRow(transaction) {
        const totalDebit = transaction.journal_entries.reduce((sum, e) => sum + parseFloat(e.debit), 0);
        const totalCredit = transaction.journal_entries.reduce((sum, e) => sum + parseFloat(e.credit), 0);
        const balanced = Math.abs(totalDebit - totalCredit) < 0.01;
        const hasEnoughEntries = transaction.journal_entries.length >= 2;
        const canPost = balanced && hasEnoughEntries;
        const isChainable = transaction.status === 'DRAFT' && transaction.journal_entries.length === 1;

        return `
            <tr class="transaction-row ${!canPost ? 'transaction-unbalanced' : ''}">
                <td>
                    <button class="btn btn-sm" onclick="postingQueueManager.toggleDetails(${transaction.id})"
                            id="toggle-btn-${transaction.id}" style="padding: 0.25rem 0.5rem;">
                        ▶
                    </button>
                </td>
                <td style="text-align: center;">
                    ${isChainable ? `
                        <input type="checkbox" class="chain-checkbox"
                               data-id="${transaction.id}"
                               onchange="postingQueueManager.updateChainSelection()"
                               title="Velg for kjeding">
                    ` : ''}
                </td>
                <td>${transaction.transaction_date}</td>
                <td>
                    ${transaction.description}
                    ${!canPost ? `<br><small style="color: var(--danger-color);">⚠ ${!balanced ? 'Ikke balansert' : 'Mangler posteringer'}</small>` : ''}
                </td>
                <td>${transaction.reference || '-'}</td>
                <td>${this.getSourceBadge(transaction.source)}</td>
                <td class="amount">${totalDebit.toFixed(2)} kr</td>
                <td class="amount">${totalCredit.toFixed(2)} kr</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="postingQueueManager.editTransaction(${transaction.id})">
                        Rediger
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="postingQueueManager.postTransaction(${transaction.id})" ${!canPost ? 'disabled' : ''}>
                        Poster
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="postingQueueManager.deleteTransaction(${transaction.id})">
                        Slett
                    </button>
                </td>
            </tr>
            <tr id="details-${transaction.id}" class="transaction-details" style="display: none;">
                <td></td>
                <td colspan="8">
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
                                ${transaction.journal_entries.map(entry => `
                                    <tr>
                                        <td>${entry.account ? entry.account.account_number : entry.account_id}</td>
                                        <td>${entry.account ? entry.account.account_name : 'Ukjent konto'}</td>
                                        <td class="amount">${parseFloat(entry.debit).toFixed(2)} kr</td>
                                        <td class="amount">${parseFloat(entry.credit).toFixed(2)} kr</td>
                                    </tr>
                                `).join('')}
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

    getSourceBadge(source) {
        const badges = {
            'MANUAL': '<span class="badge" style="background: #e5e7eb; color: #374151;">📝 Manuell</span>',
            'CSV_IMPORT': '<span class="badge" style="background: #dbeafe; color: #1e40af;">📄 CSV</span>',
            'BANK_SYNC': '<span class="badge" style="background: #d1fae5; color: #065f46;">🏦 Bank</span>'
        };
        return badges[source] || badges['MANUAL'];
    }

    getBookkeepingTip(transaction) {
        if (transaction.journal_entries.length === 0) return 'Legg til minst to posteringer for å balansere transaksjonen.';

        const firstEntry = transaction.journal_entries[0];
        const account = firstEntry.account;

        if (!account) return 'Velg kontoer for posteringene.';

        // Check if it's a LIABILITY account (credit card)
        if (account.account_type === 'LIABILITY') {
            if (parseFloat(firstEntry.credit) > 0) {
                return `Dette er en utgift betalt med kredittkort. Legg til <strong>DEBET</strong> på en utgiftskonto (6xxx) for samme beløp (${parseFloat(firstEntry.credit).toFixed(2)} kr).`;
            } else if (parseFloat(firstEntry.debit) > 0) {
                return `Dette er en refusjon på kredittkort. Legg til <strong>KREDIT</strong> på en utgiftskonto (6xxx) for samme beløp (${parseFloat(firstEntry.debit).toFixed(2)} kr).`;
            }
        }

        // Check if it's an ASSET account (bank)
        if (account.account_type === 'ASSET') {
            if (parseFloat(firstEntry.credit) > 0) {
                return `Dette er en utgift betalt fra bankkonto. Legg til <strong>DEBET</strong> på en utgiftskonto (6xxx) for samme beløp (${parseFloat(firstEntry.credit).toFixed(2)} kr).`;
            } else if (parseFloat(firstEntry.debit) > 0) {
                return `Dette er en inntekt til bankkonto. Legg til <strong>KREDIT</strong> på en inntektskonto (3xxx) for samme beløp (${parseFloat(firstEntry.debit).toFixed(2)} kr).`;
            }
        }

        return 'Legg til motposter slik at debet = kredit.';
    }

    editTransaction(id) {
        const transaction = this.transactions.find(t => t.id === id);
        if (!transaction) {
            showError('Transaksjon ikke funnet');
            return;
        }

        const content = `
            <form id="edit-transaction-form">
                <div class="form-group">
                    <label>Dato</label>
                    <input type="date" id="trans-date" value="${transaction.transaction_date}" required>
                </div>
                <div class="form-group">
                    <label>Beskrivelse</label>
                    <input type="text" id="trans-description" value="${transaction.description}" required>
                </div>
                <div class="form-group">
                    <label>Referanse</label>
                    <input type="text" id="trans-reference" value="${transaction.reference || ''}">
                </div>

                <h4>Posteringer</h4>

                <div id="journal-entries-container">
                    ${transaction.journal_entries.map((entry, idx) => this.renderJournalEntryEdit(entry, idx)).join('')}
                </div>

                <div style="margin: 1rem 0; padding: 1rem; background: #e3f2fd; border-left: 4px solid var(--primary-color); border-radius: 4px;">
                    <strong>💡 Tips:</strong>
                    <p style="margin: 0.5rem 0 0 0;">
                        ${this.getBookkeepingTip(transaction)}
                    </p>
                </div>

                <button type="button" class="btn btn-secondary" onclick="postingQueueManager.addJournalEntry()">
                    + Legg til postering
                </button>

                <div style="margin-top: 1rem; padding: 1rem; background: var(--background); border-radius: 4px;">
                    <strong>Balanse:</strong>
                    <div id="balance-info"></div>
                </div>

                <div style="margin-top: 1rem;">
                    <button type="submit" class="btn btn-primary">Lagre endringer</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Avbryt</button>
                </div>
            </form>
        `;

        showModal('Rediger transaksjon', content);

        this.currentEditingTransaction = transaction;
        this.updateBalance();

        document.getElementById('edit-transaction-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveTransaction(id);
        });
    }

    getAccountHint(accountType) {
        switch (accountType) {
            case 'ASSET':
                return 'Debet: inn / øker &nbsp;·&nbsp; Kredit: ut / reduserer';
            case 'LIABILITY':
                return 'Debet: reduserer gjeld &nbsp;·&nbsp; Kredit: øker gjeld';
            case 'EQUITY':
                return 'Debet: reduserer egenkapital &nbsp;·&nbsp; Kredit: øker egenkapital';
            case 'REVENUE':
                return 'Debet: reduserer inntekt &nbsp;·&nbsp; Kredit: øker inntekt (normalt)';
            case 'EXPENSE':
                return 'Debet: øker kostnad (normalt) &nbsp;·&nbsp; Kredit: reduserer kostnad';
            default:
                return '';
        }
    }

    renderJournalEntryEdit(entry, idx) {
        const currentAccount = entry.account_id ? this.accounts.find(a => a.id === entry.account_id) : null;
        const accountValue = currentAccount ? currentAccount.account_number : '';
        const hint = currentAccount ? this.getAccountHint(currentAccount.account_type) : '';

        return `
            <div class="journal-entry" id="entry-${idx}">
                <div class="form-group">
                    <label>Konto (nummer eller navn)</label>
                    <input type="text"
                           class="entry-account-input"
                           data-idx="${idx}"
                           value="${accountValue}"
                           placeholder="Søk kontonummer eller navn..."
                           list="accounts-datalist-${idx}"
                           required
                           onchange="postingQueueManager.validateAccount(${idx})"
                           oninput="postingQueueManager.filterAccounts(${idx})">
                    <datalist id="accounts-datalist-${idx}">
                        ${this.accounts.map(a => `
                            <option value="${a.account_number}" data-id="${a.id}">
                                ${a.account_number} - ${a.account_name}
                            </option>
                        `).join('')}
                    </datalist>
                    <input type="hidden" class="entry-account" data-idx="${idx}" value="${entry.account_id || ''}">
                    <small class="account-name-display" id="account-name-${idx}" style="color: var(--text-secondary);">
                        ${currentAccount ? currentAccount.account_name : ''}
                    </small>
                    <small class="account-hint" id="account-hint-${idx}">${hint}</small>
                </div>
                <div class="form-group">
                    <label>Debet</label>
                    <input type="number" step="0.01" class="entry-debit" data-idx="${idx}"
                           value="${entry.debit}" onchange="postingQueueManager.updateBalance()">
                </div>
                <div class="form-group">
                    <label>Kredit</label>
                    <input type="number" step="0.01" class="entry-credit" data-idx="${idx}"
                           value="${entry.credit}" onchange="postingQueueManager.updateBalance()">
                </div>
                ${idx > 0 ? `
                    <button type="button" class="btn btn-sm btn-danger" onclick="postingQueueManager.removeJournalEntry(${idx})">
                        Fjern
                    </button>
                ` : '<div></div>'}
            </div>
        `;
    }

    filterAccounts(idx) {
        const input = document.querySelector(`.entry-account-input[data-idx="${idx}"]`);
        const searchTerm = input.value.toLowerCase();

        // Update datalist with filtered options
        const datalist = document.getElementById(`accounts-datalist-${idx}`);
        datalist.innerHTML = this.accounts
            .filter(a =>
                a.account_number.includes(searchTerm) ||
                a.account_name.toLowerCase().includes(searchTerm)
            )
            .slice(0, 50) // Limit to 50 results for performance
            .map(a => `
                <option value="${a.account_number}" data-id="${a.id}">
                    ${a.account_number} - ${a.account_name}
                </option>
            `).join('');
    }

    validateAccount(idx) {
        const input = document.querySelector(`.entry-account-input[data-idx="${idx}"]`);
        const hiddenInput = document.querySelector(`.entry-account[data-idx="${idx}"]`);
        const nameDisplay = document.getElementById(`account-name-${idx}`);

        const searchTerm = input.value.trim();

        // Try to find account by number or partial name
        let account = this.accounts.find(a => a.account_number === searchTerm);

        if (!account) {
            // Try partial match on name
            const matches = this.accounts.filter(a =>
                a.account_name.toLowerCase().includes(searchTerm.toLowerCase())
            );
            if (matches.length === 1) {
                account = matches[0];
            }
        }

        const hintEl = document.getElementById(`account-hint-${idx}`);
        if (account) {
            hiddenInput.value = account.id;
            input.value = account.account_number;
            nameDisplay.textContent = account.account_name;
            nameDisplay.style.color = 'var(--text-secondary)';
            input.style.borderColor = 'var(--border-color)';
            if (hintEl) hintEl.innerHTML = this.getAccountHint(account.account_type);
        } else if (searchTerm) {
            hiddenInput.value = '';
            nameDisplay.textContent = 'Ugyldig konto';
            nameDisplay.style.color = 'var(--danger-color)';
            input.style.borderColor = 'var(--danger-color)';
            if (hintEl) hintEl.innerHTML = '';
        } else {
            hiddenInput.value = '';
            nameDisplay.textContent = '';
            input.style.borderColor = 'var(--border-color)';
            if (hintEl) hintEl.innerHTML = '';
        }
    }

    addJournalEntry() {
        const container = document.getElementById('journal-entries-container');
        const idx = container.children.length;

        // Calculate current balance to pre-fill amount
        let totalDebit = 0;
        let totalCredit = 0;

        document.querySelectorAll('.entry-debit').forEach(input => {
            totalDebit += parseFloat(input.value) || 0;
        });

        document.querySelectorAll('.entry-credit').forEach(input => {
            totalCredit += parseFloat(input.value) || 0;
        });

        // Pre-fill the amount needed to balance
        const difference = totalDebit - totalCredit;
        let prefilledDebit = '0.00';
        let prefilledCredit = '0.00';

        if (difference > 0.01) {
            // More debit than credit, need credit
            prefilledCredit = difference.toFixed(2);
        } else if (difference < -0.01) {
            // More credit than debit, need debit
            prefilledDebit = Math.abs(difference).toFixed(2);
        }

        const newEntry = {
            account_id: null,
            debit: prefilledDebit,
            credit: prefilledCredit,
            account: null
        };

        const entryHtml = this.renderJournalEntryEdit(newEntry, idx);
        container.insertAdjacentHTML('beforeend', entryHtml);
        this.updateBalance();
    }

    removeJournalEntry(idx) {
        const entry = document.getElementById(`entry-${idx}`);
        if (entry) {
            entry.remove();
            this.updateBalance();
        }
    }

    updateBalance() {
        let totalDebit = 0;
        let totalCredit = 0;

        document.querySelectorAll('.entry-debit').forEach(input => {
            totalDebit += parseFloat(input.value) || 0;
        });

        document.querySelectorAll('.entry-credit').forEach(input => {
            totalCredit += parseFloat(input.value) || 0;
        });

        const balanced = Math.abs(totalDebit - totalCredit) < 0.01;
        const balanceInfo = document.getElementById('balance-info');

        if (balanceInfo) {
            balanceInfo.innerHTML = `
                <div>Debet: ${totalDebit.toFixed(2)} kr</div>
                <div>Kredit: ${totalCredit.toFixed(2)} kr</div>
                <div style="color: ${balanced ? 'var(--success-color)' : 'var(--danger-color)'}; font-weight: bold;">
                    ${balanced ? '✓ Balansert' : '✗ Ikke balansert - differanse: ' + Math.abs(totalDebit - totalCredit).toFixed(2) + ' kr'}
                </div>
            `;
        }

        return balanced;
    }

    async saveTransaction(id) {
        if (!this.updateBalance()) {
            showError('Transaksjonen må være balansert før lagring');
            return;
        }

        const date = document.getElementById('trans-date').value;
        const description = document.getElementById('trans-description').value;
        const reference = document.getElementById('trans-reference').value;

        const journalEntries = [];
        let hasInvalidAccounts = false;

        document.querySelectorAll('.journal-entry').forEach(entryDiv => {
            const idx = entryDiv.querySelector('.entry-account').dataset.idx;
            const accountId = parseInt(entryDiv.querySelector('.entry-account').value);
            const debit = parseFloat(entryDiv.querySelector('.entry-debit').value) || 0;
            const credit = parseFloat(entryDiv.querySelector('.entry-credit').value) || 0;

            if (!accountId && (debit > 0 || credit > 0)) {
                hasInvalidAccounts = true;
            }

            if (accountId && (debit > 0 || credit > 0)) {
                journalEntries.push({
                    account_id: accountId,
                    debit: debit.toFixed(2),
                    credit: credit.toFixed(2)
                });
            }
        });

        if (hasInvalidAccounts) {
            showError('Alle posteringer må ha en gyldig konto');
            return;
        }

        if (journalEntries.length < 2) {
            showError('Transaksjonen må ha minst to posteringer');
            return;
        }

        try {
            await api.updateTransaction(id, {
                transaction_date: date,
                description: description,
                reference: reference || null,
                journal_entries: journalEntries
            });

            closeModal();
            showSuccess('Transaksjon oppdatert');
            await this.loadQueue();
        } catch (error) {
            showError(error.message);
        }
    }

    async postTransaction(id) {
        // Validate balance before posting
        const transaction = this.transactions.find(t => t.id === id);
        if (!transaction) {
            showError('Transaksjon ikke funnet');
            return;
        }

        const totalDebit = transaction.journal_entries.reduce((sum, e) => sum + parseFloat(e.debit), 0);
        const totalCredit = transaction.journal_entries.reduce((sum, e) => sum + parseFloat(e.credit), 0);

        if (Math.abs(totalDebit - totalCredit) > 0.01) {
            showError(`Transaksjonen balanserer ikke. Debet: ${totalDebit.toFixed(2)} kr, Kredit: ${totalCredit.toFixed(2)} kr. Vennligst rediger transaksjonen først.`);
            return;
        }

        if (transaction.journal_entries.length < 2) {
            showError('Transaksjonen må ha minst to posteringer. Vennligst rediger transaksjonen først.');
            return;
        }

        try {
            await api.postTransaction(id);
            showSuccess('Transaksjon postert');
            await this.loadQueue();
        } catch (error) {
            console.error('Error posting transaction:', error);
            showError('Kunne ikke postere transaksjon: ' + error.message);
        }
    }

    async deleteTransaction(id) {
        if (!confirm('Slette denne transaksjonen? Dette kan ikke angres.')) {
            return;
        }

        try {
            await api.deleteTransaction(id);
            showSuccess('Transaksjon slettet');
            await this.loadQueue();
        } catch (error) {
            console.error('Error deleting transaction:', error);
            showError('Kunne ikke slette transaksjon: ' + error.message);
        }
    }

    async postAllTransactions() {
        if (this.transactions.length === 0) {
            showError('Ingen transaksjoner å postere');
            return;
        }

        // Count how many can be posted
        const balancedTransactions = this.transactions.filter(t => {
            const totalDebit = t.journal_entries.reduce((sum, e) => sum + parseFloat(e.debit), 0);
            const totalCredit = t.journal_entries.reduce((sum, e) => sum + parseFloat(e.credit), 0);
            return Math.abs(totalDebit - totalCredit) < 0.01 && t.journal_entries.length >= 2;
        });

        if (balancedTransactions.length === 0) {
            showError('Ingen transaksjoner kan posteres. Alle må være balansert og ha minst 2 posteringer.');
            return;
        }

        const unbalancedCount = this.transactions.length - balancedTransactions.length;
        let message = `Poster ${balancedTransactions.length} transaksjon(er)?`;
        if (unbalancedCount > 0) {
            message += `\n\n(${unbalancedCount} ubalanserte transaksjon(er) vil bli hoppet over)`;
        }

        if (!confirm(message)) {
            return;
        }

        try {
            // Post each balanced transaction individually
            let posted = 0;
            let failed = 0;

            for (const transaction of balancedTransactions) {
                try {
                    await api.postTransaction(transaction.id);
                    posted++;
                } catch (error) {
                    console.error(`Failed to post transaction ${transaction.id}:`, error);
                    failed++;
                }
            }

            if (posted > 0) {
                showSuccess(`${posted} transaksjon(er) ble postert${failed > 0 ? `, ${failed} feilet` : ''}`);
            } else {
                showError('Ingen transaksjoner ble postert');
            }

            await this.loadQueue();
        } catch (error) {
            console.error('Error posting all transactions:', error);
            showError('Kunne ikke postere transaksjoner: ' + error.message);
        }
    }

    // --- Transaction Chaining ---

    renderChainSuggestionsBanner() {
        if (!this.chainSuggestions || this.chainSuggestions.length === 0) {
            return '';
        }

        const suggestionsHtml = this.chainSuggestions.map(s => {
            const confidenceBadge = s.confidence === 'HIGH'
                ? '<span class="badge" style="background: #d1fae5; color: #065f46; font-size: 0.75rem;">Sikker match</span>'
                : '<span class="badge" style="background: #fef3c7; color: #92400e; font-size: 0.75rem;">Sannsynlig match</span>';

            const dateInfo = s.primary_date === s.secondary_date
                ? s.primary_date
                : `${s.primary_date} / ${s.secondary_date}`;

            return `
                <div style="background: white; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="flex: 1; min-width: 200px;">
                        ${confidenceBadge}
                        <strong>${dateInfo}</strong> - ${parseFloat(s.amount).toFixed(2)} kr
                        <br>
                        <small style="color: #374151;">${s.primary_account_name} &harr; ${s.secondary_account_name}</small>
                        <br>
                        <small style="color: #6b7280;">"${s.primary_description}" / "${s.secondary_description}"</small>
                    </div>
                    <div style="display: flex; gap: 0.25rem;">
                        <button class="btn btn-sm btn-primary" onclick="postingQueueManager.chainTransactions(${s.primary_transaction_id}, ${s.secondary_transaction_id}, false)">
                            Kjed
                        </button>
                        <button class="btn btn-sm" style="background: #059669; color: white;" onclick="postingQueueManager.chainTransactions(${s.primary_transaction_id}, ${s.secondary_transaction_id}, true)">
                            Kjed + poster
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="card" style="border-left: 4px solid #3b82f6; margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div>
                        <strong>Mulige kontooverforinger funnet</strong>
                        <p style="margin: 0.25rem 0 0 0; color: #6b7280; font-size: 0.875rem;">
                            ${this.chainSuggestions.length} transaksjonspar kan slås sammen til balanserte transaksjoner.
                        </p>
                    </div>
                    ${this.chainSuggestions.length > 1 ? `
                        <button class="btn btn-sm" style="background: #059669; color: white;" onclick="postingQueueManager.chainAllSuggestions()">
                            Kjed alle (${this.chainSuggestions.length})
                        </button>
                    ` : ''}
                </div>
                ${suggestionsHtml}
            </div>
        `;
    }

    updateChainSelection() {
        const checked = document.querySelectorAll('.chain-checkbox:checked');
        const chainBar = document.getElementById('chain-action-bar');

        if (!chainBar) return;

        if (checked.length === 2) {
            const id1 = parseInt(checked[0].dataset.id);
            const id2 = parseInt(checked[1].dataset.id);
            chainBar.style.display = 'flex';
            chainBar.innerHTML = `
                <span>2 transaksjoner valgt for kjeding</span>
                <button class="btn btn-sm btn-primary" onclick="postingQueueManager.chainTransactions(${id1}, ${id2}, false)">
                    Kjed transaksjoner
                </button>
                <button class="btn btn-sm" style="background: #059669; color: white;" onclick="postingQueueManager.chainTransactions(${id1}, ${id2}, true)">
                    Kjed + poster
                </button>
            `;
        } else {
            chainBar.style.display = 'none';
        }
    }

    async chainTransactions(primaryId, secondaryId, autoPost = false) {
        try {
            await api.chainTransactions(primaryId, secondaryId, autoPost);
            showSuccess(autoPost
                ? 'Transaksjoner kjedet og postert'
                : 'Transaksjoner kjedet sammen');
            await this.loadQueue(this.currentPage);
        } catch (error) {
            showError('Kunne ikke kjede transaksjoner: ' + error.message);
        }
    }

    async chainAllSuggestions() {
        if (!confirm(`Kjed og poster alle ${this.chainSuggestions.length} foreslåtte par?`)) return;

        let chained = 0;
        let failed = 0;

        for (const suggestion of this.chainSuggestions) {
            try {
                await api.chainTransactions(
                    suggestion.primary_transaction_id,
                    suggestion.secondary_transaction_id,
                    true
                );
                chained++;
            } catch (error) {
                console.error('Chain failed:', error);
                failed++;
            }
        }

        showSuccess(`${chained} par kjedet og postert${failed > 0 ? `, ${failed} feilet` : ''}`);
        await this.loadQueue(this.currentPage);
    }
}

const postingQueueManager = new PostingQueueManager();
window.postingQueueManager = postingQueueManager;

export default postingQueueManager;
