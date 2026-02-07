import api from './api.js';
import { formatCurrency, getTodayDate, getFirstDayOfMonth, getLastDayOfMonth } from './utils.js';

class ReportsManager {
    constructor() {
        this.currentReport = 'balance-sheet';
    }

    init() {
        this.setupEventListeners();
        this.setDefaultDates();
    }

    setupEventListeners() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchReport(e.target.dataset.report);
            });
        });

        document.getElementById('generate-balance-btn').addEventListener('click', () => {
            this.generateBalanceSheet();
        });

        document.getElementById('generate-income-btn').addEventListener('click', () => {
            this.generateIncomeStatement();
        });
    }

    setDefaultDates() {
        document.getElementById('balance-date').value = getTodayDate();
        document.getElementById('income-start-date').value = getFirstDayOfMonth();
        document.getElementById('income-end-date').value = getLastDayOfMonth();
    }

    switchReport(reportType) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-report="${reportType}"]`).classList.add('active');

        document.querySelectorAll('.report-content').forEach(content => {
            content.style.display = 'none';
        });

        if (reportType === 'balance-sheet') {
            document.getElementById('balance-sheet-report').style.display = 'block';
        } else if (reportType === 'income-statement') {
            document.getElementById('income-statement-report').style.display = 'block';
        }

        this.currentReport = reportType;
    }

    async generateBalanceSheet() {
        const asOfDate = document.getElementById('balance-date').value;

        try {
            const data = await api.getBalanceSheet(asOfDate);
            this.renderBalanceSheet(data);
        } catch (error) {
            alert('Feil ved generering av balanse: ' + error.message);
        }
    }

    renderBalanceSheet(data) {
        const content = document.getElementById('balance-sheet-content');

        const html = `
            <div class="report-section">
                <h3>Eiendeler</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Kontonr</th>
                            <th>Kontonavn</th>
                            <th style="text-align: right;">Beløp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.assets.map(item => `
                            <tr>
                                <td>${item.account_number}</td>
                                <td>${item.account_name}</td>
                                <td style="text-align: right;">${formatCurrency(item.balance)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="report-total">
                    Sum eiendeler: ${formatCurrency(data.total_assets)}
                </div>
            </div>

            <div class="report-section">
                <h3>Gjeld</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Kontonr</th>
                            <th>Kontonavn</th>
                            <th style="text-align: right;">Beløp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.liabilities.map(item => `
                            <tr>
                                <td>${item.account_number}</td>
                                <td>${item.account_name}</td>
                                <td style="text-align: right;">${formatCurrency(item.balance)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="report-total">
                    Sum gjeld: ${formatCurrency(data.total_liabilities)}
                </div>
            </div>

            <div class="report-section">
                <h3>Egenkapital</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Kontonr</th>
                            <th>Kontonavn</th>
                            <th style="text-align: right;">Beløp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.equity.map(item => `
                            <tr>
                                <td>${item.account_number}</td>
                                <td>${item.account_name}</td>
                                <td style="text-align: right;">${formatCurrency(item.balance)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="report-total">
                    Sum egenkapital: ${formatCurrency(data.total_equity)}
                </div>
            </div>

            <div class="report-total" style="font-size: 1.5rem; background: var(--primary-color); color: white;">
                Sum gjeld og egenkapital: ${formatCurrency(data.total_liabilities + data.total_equity)}
            </div>
        `;

        content.innerHTML = html;
    }

    async generateIncomeStatement() {
        const startDate = document.getElementById('income-start-date').value;
        const endDate = document.getElementById('income-end-date').value;

        if (!startDate || !endDate) {
            alert('Vennligst velg både start- og sluttdato');
            return;
        }

        try {
            const data = await api.getIncomeStatement(startDate, endDate);
            this.renderIncomeStatement(data);
        } catch (error) {
            alert('Feil ved generering av resultatregnskap: ' + error.message);
        }
    }

    renderIncomeStatement(data) {
        const content = document.getElementById('income-statement-content');

        const html = `
            <div class="report-section">
                <h3>Inntekter</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Kontonr</th>
                            <th>Kontonavn</th>
                            <th style="text-align: right;">Beløp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.revenues.map(item => `
                            <tr>
                                <td>${item.account_number}</td>
                                <td>${item.account_name}</td>
                                <td style="text-align: right;">${formatCurrency(item.amount)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="report-total">
                    Sum inntekter: ${formatCurrency(data.total_revenue)}
                </div>
            </div>

            <div class="report-section">
                <h3>Kostnader</h3>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Kontonr</th>
                            <th>Kontonavn</th>
                            <th style="text-align: right;">Beløp</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.expenses.map(item => `
                            <tr>
                                <td>${item.account_number}</td>
                                <td>${item.account_name}</td>
                                <td style="text-align: right;">${formatCurrency(item.amount)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <div class="report-total">
                    Sum kostnader: ${formatCurrency(data.total_expenses)}
                </div>
            </div>

            <div class="report-total" style="font-size: 1.5rem; background: ${data.net_income >= 0 ? 'var(--success-color)' : 'var(--danger-color)'}; color: white;">
                Netto resultat: ${formatCurrency(data.net_income)}
            </div>
        `;

        content.innerHTML = html;
    }
}

const reportsManager = new ReportsManager();

export default reportsManager;
