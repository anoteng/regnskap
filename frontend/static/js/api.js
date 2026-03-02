const API_BASE = '/api';

class API {
    constructor() {
        this.token = localStorage.getItem('token');
        this.currentLedgerId = localStorage.getItem('currentLedgerId');
        this.tokenRefreshInterval = null;

        // Start token refresh if we have a token
        if (this.token) {
            this.startTokenRefresh();
        }
    }

    get baseURL() {
        return API_BASE;
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('token', token);

        // Start token refresh when token is set
        this.startTokenRefresh();
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('token');

        // Stop token refresh when logged out
        this.stopTokenRefresh();
    }

    startTokenRefresh() {
        // Stop any existing interval
        this.stopTokenRefresh();

        // Refresh token every 4 hours (token expires after 8 hours)
        this.tokenRefreshInterval = setInterval(() => {
            this.refreshToken().catch(err => {
                console.error('Token refresh failed:', err);
                // If refresh fails, user will be logged out on next API call
            });
        }, 4 * 60 * 60 * 1000); // 4 hours in milliseconds
    }

    stopTokenRefresh() {
        if (this.tokenRefreshInterval) {
            clearInterval(this.tokenRefreshInterval);
            this.tokenRefreshInterval = null;
        }
    }

    async refreshToken() {
        if (!this.token) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.setToken(data.access_token);
                console.log('Token refreshed successfully');
            } else {
                console.error('Token refresh failed:', response.status);
            }
        } catch (error) {
            console.error('Token refresh error:', error);
        }
    }

    setCurrentLedger(ledgerId) {
        this.currentLedgerId = ledgerId;
        localStorage.setItem('currentLedgerId', ledgerId);
    }

    getCurrentLedger() {
        return this.currentLedgerId;
    }

    clearCurrentLedger() {
        this.currentLedgerId = null;
        localStorage.removeItem('currentLedgerId');
    }

    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        // Add auth token to all requests except login/register endpoints
        const isLoginOrRegister = endpoint.includes('/auth/login') || endpoint.includes('/auth/register');
        if (this.token && !isLoginOrRegister) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        // Add ledger context to all requests (except auth and ledger list/create)
        if (this.currentLedgerId &&
            !endpoint.includes('/auth/') &&
            !endpoint.match(/^\/ledgers\/?$/)) {
            headers['X-Ledger-ID'] = this.currentLedgerId;
        }

        const config = {
            ...options,
            headers,
        };

        const response = await fetch(`${API_BASE}${endpoint}`, config);

        if (response.status === 401) {
            this.clearToken();
            window.location.reload();
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }

        return response.json();
    }

    async get(endpoint) {
        return this.request(endpoint);
    }

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE',
        });
    }

    async login(email, password) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Login failed');
        }

        const data = await response.json();
        this.setToken(data.access_token);
        return data;
    }

    async register(fullName, email, password) {
        return this.post('/auth/register', {
            full_name: fullName,
            email,
            password,
        });
    }

    async getAccounts(accountType = null, showHidden = false) {
        const params = new URLSearchParams();
        if (accountType) params.append('account_type', accountType);
        if (showHidden) params.append('show_hidden', 'true');
        const queryString = params.toString();
        return this.get(`/accounts/${queryString ? '?' + queryString : ''}`);
    }

    async createAccount(data) {
        return this.post('/accounts/', data);
    }

    async updateAccount(id, data) {
        return this.put(`/accounts/${id}`, data);
    }

    async deleteAccount(id) {
        return this.delete(`/accounts/${id}`);
    }

    async toggleAccountVisibility(id) {
        return this.post(`/accounts/${id}/toggle-visibility`, {});
    }

    async getBankAccounts() {
        return this.get('/bank-accounts/');
    }

    async createBankAccount(data) {
        return this.post('/bank-accounts/', data);
    }

    async getBankAccount(id) {
        return this.get(`/bank-accounts/${id}`);
    }

    async updateBankAccount(id, data) {
        return this.put(`/bank-accounts/${id}`, data);
    }

    async deleteBankAccount(id) {
        return this.delete(`/bank-accounts/${id}`);
    }

    async getTransactions(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return this.get(`/transactions/?${params}`);
    }

    async createTransaction(data) {
        return this.post('/transactions/', data);
    }

    async updateTransaction(id, data) {
        return this.put(`/transactions/${id}`, data);
    }

    async deleteTransaction(id) {
        return this.delete(`/transactions/${id}`);
    }

    async getPostingQueue(skip = 0, limit = 50) {
        return this.get(`/transactions/queue?skip=${skip}&limit=${limit}`);
    }

    async getAspsps(country = null) {
        const params = country ? `?country=${country}` : '';
        return this.get(`/bank-connections/aspsps${params}`);
    }

    async getChainSuggestions() {
        return this.get('/transactions/chain-suggestions');
    }

    async chainTransactions(primaryId, secondaryId, autoPost = false) {
        return this.post('/transactions/chain', {
            primary_transaction_id: primaryId,
            secondary_transaction_id: secondaryId,
            auto_post: autoPost
        });
    }

    async postTransaction(id) {
        return this.post(`/transactions/${id}/post`, {});
    }

    async reconcileTransaction(id) {
        return this.post(`/transactions/${id}/reconcile`, {});
    }

    async postAllDrafts() {
        return this.post('/transactions/queue/post-all', {});
    }

    async reverseTransaction(id) {
        return this.post(`/transactions/${id}/reverse`, {});
    }

    async previewCSV(file, delimiter = ',') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('delimiter', delimiter);

        const headers = {
            'Authorization': `Bearer ${this.token}`,
        };

        // Add ledger context
        if (this.currentLedgerId) {
            headers['X-Ledger-ID'] = this.currentLedgerId;
        }

        const response = await fetch(`${API_BASE}/transactions/csv-preview`, {
            method: 'POST',
            headers: headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error('CSV preview failed');
        }

        return response.json();
    }

    async importCSV(bankAccountId, file, mappingConfig, csvMappingId = null) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('mapping_config', JSON.stringify(mappingConfig));
        if (csvMappingId) {
            formData.append('csv_mapping_id', csvMappingId);
        }

        const headers = {
            'Authorization': `Bearer ${this.token}`,
        };

        // Add ledger context
        if (this.currentLedgerId) {
            headers['X-Ledger-ID'] = this.currentLedgerId;
        }

        const response = await fetch(`${API_BASE}/transactions/import-csv/${bankAccountId}`, {
            method: 'POST',
            headers: headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Import failed');
        }

        return response.json();
    }

    async getCSVMappings() {
        return this.get('/csv-mappings/');
    }

    async createCSVMapping(data) {
        return this.post('/csv-mappings/', data);
    }

    async deleteCSVMapping(id) {
        return this.delete(`/csv-mappings/${id}`);
    }

    async getCategories() {
        return this.get('/categories/');
    }

    async createCategory(data) {
        return this.post('/categories/', data);
    }

    async getBudgets() {
        return this.get('/budgets/');
    }

    async createBudget(data) {
        return this.post('/budgets/', data);
    }

    async getBudget(id) {
        return this.get(`/budgets/${id}`);
    }

    async setBudgetLines(budgetId, lines) {
        return this.post(`/budgets/${budgetId}/lines`, lines);
    }

    async getBudgetReport(budgetId) {
        return this.get(`/budgets/${budgetId}/report`);
    }

    async deleteBudget(id) {
        return this.delete(`/budgets/${id}`)
    }

    async getBudgetDrilldown(budgetId, accountId, month = null) {
        let params = `?account_id=${accountId}`;
        if (month) params += `&month=${month}`;
        return this.get(`/budgets/${budgetId}/drilldown${params}`);
    }

    async getBalanceSheet(asOfDate = null) {
        const params = asOfDate ? `?as_of_date=${asOfDate}` : '';
        return this.get(`/reports/balance-sheet${params}`);
    }

    async getIncomeStatement(startDate, endDate) {
        return this.get(`/reports/income-statement?start_date=${startDate}&end_date=${endDate}`);
    }

    // Ledger methods
    async getLedgers() {
        return this.get('/ledgers/');
    }

    async createLedger(name) {
        return this.post('/ledgers/', { name });
    }

    async getLedger(id) {
        return this.get(`/ledgers/${id}`);
    }

    async updateLedger(id, name) {
        return this.put(`/ledgers/${id}`, { name });
    }

    async deleteLedger(id) {
        return this.delete(`/ledgers/${id}`);
    }

    async switchLedger(ledgerId) {
        return this.post(`/ledgers/${ledgerId}/switch`, {});
    }

    async getLedgerMembers(ledgerId) {
        return this.get(`/ledgers/${ledgerId}/members`);
    }

    async inviteMember(ledgerId, email, role) {
        return this.post(`/ledgers/${ledgerId}/members`, { email, role });
    }

    async updateMemberRole(ledgerId, userId, role) {
        return this.put(`/ledgers/${ledgerId}/members/${userId}`, { role });
    }

    async removeMember(ledgerId, userId) {
        return this.delete(`/ledgers/${ledgerId}/members/${userId}`);
    }

    async leaveLedger(ledgerId) {
        return this.post(`/ledgers/${ledgerId}/leave`, {});
    }

    // Receipts
    async uploadReceipt(file, receiptData = {}) {
        const formData = new FormData();
        formData.append('file', file);

        if (receiptData.receipt_date) {
            formData.append('receipt_date', receiptData.receipt_date);
        }
        if (receiptData.amount) {
            formData.append('amount', receiptData.amount);
        }
        if (receiptData.description) {
            formData.append('description', receiptData.description);
        }

        const headers = {
            'Authorization': `Bearer ${this.token}`,
            'X-Ledger-ID': this.currentLedgerId
        };

        const response = await fetch(`${this.baseURL}/receipts/upload`, {
            method: 'POST',
            headers,
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to upload receipt');
        }

        return response.json();
    }

    async getReceipts(status = null) {
        const params = status ? `?status=${status}` : '';
        return this.get(`/receipts/${params}`);
    }

    async getReceipt(id) {
        return this.get(`/receipts/${id}`);
    }

    getReceiptImage(id) {
        return `${API_BASE}/receipts/${id}/image?token=${this.token}&ledger=${this.currentLedgerId}`;
    }

    async matchReceipt(receiptId, transactionId) {
        return this.post(`/receipts/${receiptId}/match/${transactionId}`, {});
    }

    async unmatchReceipt(receiptId) {
        return this.post(`/receipts/${receiptId}/unmatch`, {});
    }

    async updateReceipt(id, data) {
        return this.put(`/receipts/${id}`, data);
    }

    async deleteReceipt(id) {
        return this.delete(`/receipts/${id}`);
    }
}

export default new API();
