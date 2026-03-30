import api from './api.js';
import { showModal, closeModal, showError, showSuccess, formatDate } from './utils.js';

class ReceiptsManager {
    constructor() {
        this.receipts = [];
        this.currentFilter = 'PENDING';
        this.subscription = null;
    }

    async init() {
        await this.checkSubscription();

        const view = document.getElementById('receipts-view');
        const viewHeader = view.querySelector('.view-header > div');
        const subtitle = view.querySelector('.subtitle');

        if (this.subscription && this.subscription.tier === 'FREE') {
            this.renderUpgradeInfo();
            return;
        }

        // Restore visibility for paid users
        if (viewHeader) viewHeader.style.display = '';
        if (subtitle) subtitle.style.display = '';
        const h1 = view.querySelector('h1');
        if (h1) h1.textContent = 'Vedleggskø';

        if (!this._listenersAttached) {
            this.setupEventListeners();
            this._listenersAttached = true;
        }
        this.loadReceipts();
    }

    async checkSubscription() {
        try {
            this.subscription = await api.getMySubscription();
        } catch (error) {
            console.error('Error checking subscription:', error);
            this.subscription = { tier: 'FREE', has_subscription: false };
        }
    }

    renderUpgradeInfo() {
        const container = document.getElementById('receipts-list');
        const view = document.getElementById('receipts-view');
        // Hide filters and subtitle for free users
        const viewHeader = view.querySelector('.view-header > div');
        if (viewHeader) viewHeader.style.display = 'none';
        const subtitle = view.querySelector('.subtitle');
        if (subtitle) subtitle.style.display = 'none';
        // Update the page title
        const h1 = view.querySelector('h1');
        if (h1) h1.textContent = 'Vedlegg';

        container.innerHTML = `
            <div class="card" style="max-width: 640px; margin: 2rem auto; text-align: center; padding: 2rem;">
                <h2 style="margin-bottom: 1rem;">Vedlegg og kvitteringer</h2>
                <p style="margin-bottom: 1.5rem; color: var(--text-secondary);">
                    Oppgrader for å laste opp og organisere kvitteringer og fakturaer.
                </p>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem;text-align:left;">
                    <div style="background: var(--bg-secondary); border-radius: 8px; padding: 1.25rem;">
                        <h3 style="margin-bottom: 0.75rem;">Basic</h3>
                        <ul style="list-style: none; padding: 0; margin: 0 0 1rem;">
                            <li style="padding: 0.3rem 0;">&#10003; Last opp kvitteringer og fakturaer</li>
                            <li style="padding: 0.3rem 0;">&#10003; Koble vedlegg til transaksjoner</li>
                            <li style="padding: 0.3rem 0;">&#10003; Manuell registrering av metadata</li>
                        </ul>
                        <div style="font-weight: bold;">10 kr/mnd</div>
                    </div>
                    <div style="background: var(--bg-secondary); border-radius: 8px; padding: 1.25rem; border: 2px solid var(--color-primary);">
                        <h3 style="margin-bottom: 0.75rem;">Premium</h3>
                        <ul style="list-style: none; padding: 0; margin: 0 0 1rem;">
                            <li style="padding: 0.3rem 0;">&#10003; Alt i Basic</li>
                            <li style="padding: 0.3rem 0;">&#10003; AI-gjenkjenning av beløp, dato og leverandør</li>
                            <li style="padding: 0.3rem 0;">&#10003; Forslag til regnskapskonto</li>
                            <li style="padding: 0.3rem 0;">&#10003; Fakturahåndtering med forfallsdato</li>
                        </ul>
                        <div style="font-weight: bold;">25 kr/mnd</div>
                    </div>
                </div>

                <p style="color: var(--text-secondary); font-size: 0.875rem;">
                    Kontakt administrator for &#229; oppgradere.
                </p>
            </div>
        `;
    }

    setupEventListeners() {
        document.querySelectorAll('input[name="receipt-filter"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.loadReceipts();
            });
        });
    }

    async loadReceipts() {
        try {
            const status = this.currentFilter === 'all' ? null : this.currentFilter;
            this.receipts = await api.getReceipts(status);
            this.renderReceipts();
        } catch (error) {
            console.error('Error loading receipts:', error);
            showError('Kunne ikke laste vedlegg: ' + error.message);
        }
    }

    renderReceipts() {
        const container = document.getElementById('receipts-list');

        if (this.receipts.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <p>Ingen vedlegg funnet.</p>
                    <p>Last opp kvitteringer fra mobil-appen for å se dem her.</p>
                </div>
            `;
            return;
        }

        const html = `
            <div class="receipts-grid">
                ${this.receipts.map(r => this.renderReceiptCard(r)).join('')}
            </div>
        `;

        container.innerHTML = html;
    }

    get isPremium() {
        return this.subscription && this.subscription.tier === 'PREMIUM';
    }

    renderReceiptCard(receipt) {
        const imageUrl = api.getReceiptImage(receipt.id);
        const isInvoice = receipt.attachment_type === 'INVOICE';
        const typeLabel = isInvoice ? 'Faktura' : 'Kvittering';
        const typeBadgeStyle = isInvoice
            ? 'background:#dbeafe;color:#1e40af;'
            : 'background:#dcfce7;color:#166534;';

        const aiInfo = receipt.ai_extracted_vendor
            ? `<div><small>Leverandør: ${receipt.ai_extracted_vendor}</small></div>`
            : '';

        const isPdf = receipt.mime_type === 'application/pdf';

        const aiButton = this.isPremium && !receipt.ai_extracted_vendor
            ? `<button class="btn btn-sm btn-secondary" onclick="receiptsManager.extractWithAI(${receipt.id})">
                   AI-gjenkjenning
               </button>`
            : '';

        const thumbnail = isPdf
            ? `<div class="receipt-image receipt-pdf-thumb" onclick="receiptsManager.showFullImage(${receipt.id})"
                    style="display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;background:#f3f4f6;color:#374151;">
                   <span style="font-size:2rem;">📄</span>
                   <span style="font-size:0.65rem;margin-top:4px;">PDF</span>
               </div>`
            : `<img src="${imageUrl}" alt="${typeLabel}" class="receipt-image" onclick="receiptsManager.showFullImage(${receipt.id})">`;

        return `
            <div class="receipt-card ${receipt.status === 'MATCHED' ? 'receipt-matched' : ''}">
                <div class="receipt-image-container">
                    ${thumbnail}
                </div>
                <div class="receipt-info">
                    <div class="receipt-meta">
                        <strong>${receipt.original_filename || typeLabel}</strong>
                        <span style="font-size:0.75rem;padding:2px 6px;border-radius:4px;${typeBadgeStyle}">${typeLabel}</span>
                        <small>${formatDate(receipt.created_at)}</small>
                    </div>
                    ${receipt.receipt_date ? `<div><small>Dato: ${formatDate(receipt.receipt_date)}</small></div>` : ''}
                    ${isInvoice && receipt.due_date ? `<div><small style="color:#b45309;">Forfall: ${formatDate(receipt.due_date)}</small></div>` : ''}
                    ${receipt.amount ? `<div><small>Beløp: ${parseFloat(receipt.amount).toFixed(2)} kr</small></div>` : ''}
                    ${aiInfo}
                    ${receipt.description ? `<div><small>${receipt.description}</small></div>` : ''}

                    ${receipt.status === 'MATCHED' ? `
                        <div class="receipt-status">
                            &#10003; Matchet til transaksjon #${receipt.matched_transaction_id}
                        </div>
                        <div class="receipt-actions">
                            ${aiButton}
                            <button class="btn btn-sm btn-secondary" onclick="receiptsManager.unmatchReceipt(${receipt.id})">
                                Fjern match
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="receiptsManager.deleteReceipt(${receipt.id})">
                                Slett
                            </button>
                        </div>
                    ` : `
                        <div class="receipt-actions">
                            ${aiButton}
                            <button class="btn btn-sm btn-primary" onclick="receiptsManager.showMatchModal(${receipt.id})">
                                Koble til transaksjon
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="receiptsManager.editReceipt(${receipt.id})">
                                Rediger
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="receiptsManager.deleteReceipt(${receipt.id})">
                                Slett
                            </button>
                        </div>
                    `}
                </div>
            </div>
        `;
    }

    showFullImage(id) {
        const receipt = this.receipts.find(r => r.id === id);
        if (!receipt) return;

        const imageUrl = api.getReceiptImage(id);

        if (receipt.mime_type === 'application/pdf') {
            window.open(imageUrl, '_blank');
            return;
        }

        // Create fullscreen overlay
        const overlay = document.createElement('div');
        overlay.id = 'receipt-viewer';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            z-index: 10000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        `;

        let rotation = 0;
        let scale = 1;

        overlay.innerHTML = `
            <div style="position: absolute; top: 1rem; right: 1rem; display: flex; gap: 0.5rem; z-index: 10001; flex-wrap: wrap; max-width: 600px; justify-content: flex-end;">
                <button id="rotate-left" class="btn btn-secondary" style="background: rgba(255,255,255,0.9); color: #000;">
                    ↶ Roter
                </button>
                <button id="rotate-right" class="btn btn-secondary" style="background: rgba(255,255,255,0.9); color: #000;">
                    Roter ↷
                </button>
                <button id="zoom-in" class="btn btn-secondary" style="background: rgba(255,255,255,0.9); color: #000;">
                    🔍+
                </button>
                <button id="zoom-out" class="btn btn-secondary" style="background: rgba(255,255,255,0.9); color: #000;">
                    🔍-
                </button>
                <button id="save-rotation" class="btn btn-primary" style="background: rgba(59,130,246,0.9); display: none;">
                    Lagre rotasjon
                </button>
                <button id="open-crop-editor" class="btn btn-secondary" style="background: rgba(255,255,255,0.9); color: #000;">
                    Beskjær / rediger
                </button>
                <button id="close-viewer" class="btn btn-danger" style="background: rgba(220,38,38,0.9);">
                    ✕ Lukk
                </button>
            </div>
            <div style="position: absolute; top: 1rem; left: 1rem; color: white; background: rgba(0,0,0,0.7); padding: 0.75rem; border-radius: 4px;">
                <strong>${receipt.original_filename}</strong><br>
                <small>Lastet opp: ${formatDate(receipt.created_at)}</small>
            </div>
            <div id="image-container" style="max-width: 90vw; max-height: 90vh; overflow: auto; display: flex; align-items: center; justify-content: center;">
                <img id="receipt-image" src="${imageUrl}" style="max-width: 100%; max-height: 90vh; transition: transform 0.3s; cursor: move;">
            </div>
        `;

        document.body.appendChild(overlay);

        const img = overlay.querySelector('#receipt-image');
        const container = overlay.querySelector('#image-container');

        // Rotation controls
        overlay.querySelector('#rotate-left').onclick = () => {
            rotation -= 90;
            img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
            overlay.querySelector('#save-rotation').style.display = rotation % 360 !== 0 ? 'block' : 'none';
        };

        overlay.querySelector('#rotate-right').onclick = () => {
            rotation += 90;
            img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
            overlay.querySelector('#save-rotation').style.display = rotation % 360 !== 0 ? 'block' : 'none';
        };

        // Save rotation
        overlay.querySelector('#save-rotation').onclick = async () => {
            try {
                await this.saveRotation(id, rotation);
                showSuccess('Rotasjon lagret!');
                overlay.remove();
                await this.loadReceipts();
            } catch (error) {
                showError('Kunne ikke lagre rotasjon: ' + error.message);
            }
        };

        // Zoom controls
        overlay.querySelector('#zoom-in').onclick = () => {
            scale = Math.min(scale + 0.25, 3);
            img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
        };

        overlay.querySelector('#zoom-out').onclick = () => {
            scale = Math.max(scale - 0.25, 0.5);
            img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
        };

        // Open crop editor
        overlay.querySelector('#open-crop-editor').onclick = () => {
            overlay.remove();
            this.openCropEditor(id, imageUrl);
        };

        // Close viewer
        overlay.querySelector('#close-viewer').onclick = () => {
            overlay.remove();
        };

        // Close on overlay click (but not on image)
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        };

        // Pan image when zoomed
        let isPanning = false;
        let startX, startY, scrollLeft, scrollTop;

        img.onmousedown = (e) => {
            if (scale > 1) {
                isPanning = true;
                startX = e.pageX - container.offsetLeft;
                startY = e.pageY - container.offsetTop;
                scrollLeft = container.scrollLeft;
                scrollTop = container.scrollTop;
                img.style.cursor = 'grabbing';
            }
        };

        container.onmousemove = (e) => {
            if (!isPanning) return;
            e.preventDefault();
            const x = e.pageX - container.offsetLeft;
            const y = e.pageY - container.offsetTop;
            const walkX = (x - startX) * 2;
            const walkY = (y - startY) * 2;
            container.scrollLeft = scrollLeft - walkX;
            container.scrollTop = scrollTop - walkY;
        };

        container.onmouseup = () => {
            isPanning = false;
            img.style.cursor = 'move';
        };

        container.onmouseleave = () => {
            isPanning = false;
            img.style.cursor = 'move';
        };

        // Keyboard shortcuts
        document.addEventListener('keydown', function handleKeyPress(e) {
            if (document.getElementById('receipt-viewer')) {
                if (e.key === 'Escape') {
                    overlay.remove();
                    document.removeEventListener('keydown', handleKeyPress);
                } else if (e.key === 'ArrowLeft') {
                    rotation -= 90;
                    img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
                } else if (e.key === 'ArrowRight') {
                    rotation += 90;
                    img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
                } else if (e.key === '+' || e.key === '=') {
                    scale = Math.min(scale + 0.25, 3);
                    img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
                } else if (e.key === '-') {
                    scale = Math.max(scale - 0.25, 0.5);
                    img.style.transform = `rotate(${rotation}deg) scale(${scale})`;
                }
            }
        });
    }

    async showMatchModal(receiptId) {
        const receipt = this.receipts.find(r => r.id === receiptId);
        if (!receipt) return;

        // Default date window: purchase date → purchase date + 3 days
        const purchaseDate = receipt.receipt_date || receipt.ai_extracted_date || '';
        const endDate = purchaseDate ? this._addDays(purchaseDate, 3) : '';

        const isPdf = receipt.mime_type === 'application/pdf';
        const previewHtml = isPdf
            ? `<iframe src="${api.getReceiptImage(receiptId)}" style="width:100%;height:300px;border:1px solid #e5e7eb;border-radius:4px;margin-bottom:1rem;"></iframe>`
            : `<img src="${api.getReceiptImage(receiptId)}" style="width: 100%; border-radius: 4px; margin-bottom: 1rem;">`;

        const content = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                <div>
                    <h3>Kvittering</h3>
                    ${previewHtml}
                    ${purchaseDate ? `<p>Dato: ${formatDate(purchaseDate)}</p>` : ''}
                    ${receipt.amount || receipt.ai_extracted_amount ? `<p>Beløp: ${parseFloat(receipt.amount || receipt.ai_extracted_amount).toFixed(2)} kr</p>` : ''}
                    ${receipt.ai_extracted_vendor ? `<p>Leverandør: ${receipt.ai_extracted_vendor}</p>` : ''}
                    ${receipt.description ? `<p>${receipt.description}</p>` : ''}
                </div>
                <div>
                    <h3>Søk etter transaksjon</h3>
                    <div id="match-suggestions" style="margin-bottom: 1rem;"></div>
                    <div class="form-group">
                        <label>Søk</label>
                        <input type="text" id="transaction-search" placeholder="Søk på beskrivelse, beløp eller dato...">
                    </div>
                    <div class="form-group" style="display: flex; gap: 1rem;">
                        <div style="flex: 1;">
                            <label>Dato fra</label>
                            <input type="date" id="search-start-date" value="${purchaseDate}">
                        </div>
                        <div style="flex: 1;">
                            <label>Dato til</label>
                            <input type="date" id="search-end-date" value="${endDate}">
                        </div>
                    </div>
                    <button class="btn btn-secondary" onclick="receiptsManager.searchTransactions()">
                        Søk
                    </button>
                    <div id="transaction-results" style="margin-top: 1rem; max-height: 400px; overflow-y: auto;">
                        <p><small>Søk etter transaksjoner for å koble kvitteringen</small></p>
                    </div>
                </div>
            </div>
        `;

        showModal('Koble kvittering til transaksjon', content, '1100px');
        this.currentReceiptForMatching = receiptId;

        // Load AI suggestions and auto-search in parallel
        if (purchaseDate) {
            setTimeout(() => {
                this.loadMatchSuggestions(receiptId);
                this.searchTransactions();
            }, 100);
        }
    }

    _addDays(dateStr, days) {
        const d = new Date(dateStr);
        d.setDate(d.getDate() + days);
        return d.toISOString().slice(0, 10);
    }

    async loadMatchSuggestions(receiptId) {
        const container = document.getElementById('match-suggestions');
        if (!container) return;
        try {
            const suggestions = await api.getMatchSuggestions(receiptId);
            if (!suggestions || suggestions.length === 0) return;

            const rows = suggestions.slice(0, 5).map(s => {
                const tx = s.transaction;
                const totalDebit = tx.journal_entries?.reduce((sum, e) => sum + parseFloat(e.debit), 0) || 0;
                const totalCredit = tx.journal_entries?.reduce((sum, e) => sum + parseFloat(e.credit), 0) || 0;
                const amount = totalCredit > 0 ? -totalCredit : totalDebit;
                const reasons = s.reasons.join(', ');
                return `
                    <tr>
                        <td>${formatDate(tx.transaction_date)}</td>
                        <td>${tx.description}</td>
                        <td>${amount.toFixed(2)} kr</td>
                        <td style="color: #6b7280; font-size: 0.8em;">${reasons}</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="receiptsManager.matchToTransaction(${tx.id})">
                                Velg
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');

            container.innerHTML = `
                <div style="background: #eff6ff; border-left: 3px solid #3b82f6; padding: 0.75rem; border-radius: 4px;">
                    <strong style="display: block; margin-bottom: 0.5rem;">✨ Foreslåtte treff</strong>
                    <table class="table" style="margin: 0;">
                        <thead><tr><th>Dato</th><th>Beskrivelse</th><th>Beløp</th><th>Grunn</th><th></th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `;
        } catch (e) {
            // Suggestions are best-effort — silent fail
        }
    }

    async searchTransactions() {
        const searchTerm = document.getElementById('transaction-search').value;
        const startDate = document.getElementById('search-start-date').value;
        const endDate = document.getElementById('search-end-date').value;

        try {
            const transactions = await api.getTransactions({
                start_date: startDate || undefined,
                end_date: endDate || undefined,
                limit: 50
            });

            const resultsContainer = document.getElementById('transaction-results');

            if (transactions.length === 0) {
                resultsContainer.innerHTML = '<p>Ingen transaksjoner funnet</p>';
                return;
            }

            // Filter by search term if provided
            let filteredTransactions = transactions;
            if (searchTerm) {
                const term = searchTerm.toLowerCase();
                filteredTransactions = transactions.filter(t =>
                    t.description.toLowerCase().includes(term) ||
                    t.reference?.toLowerCase().includes(term) ||
                    t.transaction_date.includes(term)
                );
            }

            resultsContainer.innerHTML = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>Dato</th>
                            <th>Beskrivelse</th>
                            <th>Beløp</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${filteredTransactions.map(t => {
                            const totalDebit = t.journal_entries?.reduce((sum, e) => sum + parseFloat(e.debit), 0) || 0;
                            const totalCredit = t.journal_entries?.reduce((sum, e) => sum + parseFloat(e.credit), 0) || 0;
                            const amount = totalCredit > 0 ? -totalCredit : totalDebit;

                            return `
                                <tr>
                                    <td>${formatDate(t.transaction_date)}</td>
                                    <td>${t.description}</td>
                                    <td>${amount.toFixed(2)} kr</td>
                                    <td>
                                        <button class="btn btn-sm btn-primary" onclick="receiptsManager.matchToTransaction(${t.id})">
                                            Velg
                                        </button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;
        } catch (error) {
            console.error('Error searching transactions:', error);
            showError('Kunne ikke søke etter transaksjoner: ' + error.message);
        }
    }

    async matchToTransaction(transactionId) {
        if (!this.currentReceiptForMatching) return;

        try {
            await api.matchReceipt(this.currentReceiptForMatching, transactionId);
            closeModal();
            showSuccess('Kvittering koblet til transaksjon');
            await this.loadReceipts();
        } catch (error) {
            showError('Kunne ikke koble kvittering: ' + error.message);
        }
    }

    async unmatchReceipt(id) {
        if (!confirm('Fjerne koblingen til transaksjonen?')) return;

        try {
            await api.unmatchReceipt(id);
            showSuccess('Kobling fjernet');
            await this.loadReceipts();
        } catch (error) {
            showError('Kunne ikke fjerne kobling: ' + error.message);
        }
    }

    editReceipt(id) {
        const receipt = this.receipts.find(r => r.id === id);
        if (!receipt) return;

        const isInvoice = receipt.attachment_type === 'INVOICE';

        const content = `
            <form id="edit-receipt-form">
                <div class="form-group">
                    <label>Type</label>
                    <select id="receipt-type">
                        <option value="RECEIPT" ${!isInvoice ? 'selected' : ''}>Kvittering</option>
                        <option value="INVOICE" ${isInvoice ? 'selected' : ''}>Faktura</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Dato</label>
                    <input type="date" id="receipt-date" value="${receipt.receipt_date || ''}">
                </div>
                <div class="form-group" id="due-date-group" style="${isInvoice ? '' : 'display:none'}">
                    <label>Forfallsdato</label>
                    <input type="date" id="receipt-due-date" value="${receipt.due_date || ''}">
                </div>
                <div class="form-group">
                    <label>Beløp</label>
                    <input type="number" step="0.01" id="receipt-amount" value="${receipt.amount || ''}">
                </div>
                <div class="form-group">
                    <label>Beskrivelse</label>
                    <textarea id="receipt-description" rows="3">${receipt.description || ''}</textarea>
                </div>
                <button type="submit" class="btn btn-primary">Lagre</button>
            </form>
        `;

        showModal('Rediger vedlegg', content);

        document.getElementById('receipt-type').addEventListener('change', (e) => {
            document.getElementById('due-date-group').style.display =
                e.target.value === 'INVOICE' ? '' : 'none';
        });

        document.getElementById('edit-receipt-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveReceiptEdit(id);
        });
    }

    async saveReceiptEdit(id) {
        const attachmentType = document.getElementById('receipt-type').value;
        const receiptDate = document.getElementById('receipt-date').value;
        const dueDate = document.getElementById('receipt-due-date').value;
        const amount = document.getElementById('receipt-amount').value;
        const description = document.getElementById('receipt-description').value;

        try {
            await api.updateReceipt(id, {
                attachment_type: attachmentType,
                receipt_date: receiptDate || null,
                due_date: attachmentType === 'INVOICE' ? (dueDate || null) : null,
                amount: amount || null,
                description: description || null
            });

            closeModal();
            showSuccess('Vedlegg oppdatert');
            await this.loadReceipts();
        } catch (error) {
            showError('Kunne ikke oppdatere vedlegg: ' + error.message);
        }
    }

    async extractWithAI(id) {
        try {
            showSuccess('AI-gjenkjenning kjøres...');
            const updated = await api.extractReceiptAI(id);
            const idx = this.receipts.findIndex(r => r.id === id);
            if (idx >= 0) this.receipts[idx] = updated;
            this.renderReceipts();
            showSuccess('AI-gjenkjenning fullført');
        } catch (error) {
            showError('AI-gjenkjenning feilet: ' + error.message);
        }
    }

    async deleteReceipt(id) {
        if (!confirm('Slette denne kvitteringen? Dette kan ikke angres.')) return;

        try {
            await api.deleteReceipt(id);
            showSuccess('Kvittering slettet');
            await this.loadReceipts();
        } catch (error) {
            showError('Kunne ikke slette kvittering: ' + error.message);
        }
    }

    openCropEditor(receiptId, imageUrl) {
        const overlay = document.createElement('div');
        overlay.id = 'crop-editor';
        overlay.style.cssText = `
            position: fixed; inset: 0;
            background: #1a1a1a;
            z-index: 10000;
            display: flex;
            flex-direction: column;
        `;
        overlay.innerHTML = `
            <div style="display:flex; align-items:center; gap:0.5rem; padding:0.75rem 1rem; background:#111; flex-wrap:wrap;">
                <span style="color:#fff; font-weight:600; margin-right:0.5rem;">Beskjær / roter</span>
                <button id="ce-rotate-left"  class="btn btn-secondary btn-sm">↶ Roter venstre</button>
                <button id="ce-rotate-right" class="btn btn-secondary btn-sm">Roter høyre ↷</button>
                <button id="ce-flip-h"       class="btn btn-secondary btn-sm">↔ Speilvend</button>
                <button id="ce-reset"        class="btn btn-secondary btn-sm">Tilbakestill</button>
                <div style="flex:1"></div>
                <button id="ce-save"   class="btn btn-primary btn-sm">Lagre</button>
                <button id="ce-cancel" class="btn btn-danger btn-sm">Avbryt</button>
            </div>
            <div style="flex:1; overflow:hidden; display:flex; align-items:center; justify-content:center;">
                <img id="ce-image" src="${imageUrl}" style="max-width:100%; max-height:100%;">
            </div>
        `;
        document.body.appendChild(overlay);

        const img = overlay.querySelector('#ce-image');
        img.onload = () => {
            const cropper = new Cropper(img, {
                viewMode: 1,
                autoCropArea: 1,
                responsive: true,
                checkCrossOrigin: false,
            });

            overlay.querySelector('#ce-rotate-left').onclick  = () => cropper.rotate(-90);
            overlay.querySelector('#ce-rotate-right').onclick = () => cropper.rotate(90);
            overlay.querySelector('#ce-flip-h').onclick       = () => {
                const data = cropper.getData();
                cropper.scaleX(-(cropper.getImageData().scaleX || 1));
            };
            overlay.querySelector('#ce-reset').onclick        = () => cropper.reset();

            overlay.querySelector('#ce-cancel').onclick = () => overlay.remove();

            overlay.querySelector('#ce-save').onclick = async () => {
                const btn = overlay.querySelector('#ce-save');
                btn.disabled = true;
                btn.textContent = 'Lagrer...';
                try {
                    const canvas = cropper.getCroppedCanvas({ maxWidth: 2048, maxHeight: 2048 });
                    await new Promise((resolve, reject) => {
                        canvas.toBlob(async (blob) => {
                            try {
                                const formData = new FormData();
                                formData.append('file', blob, 'edited.jpg');
                                const response = await fetch(`${api.baseURL}/receipts/${receiptId}/rotate`, {
                                    method: 'POST',
                                    headers: {
                                        'Authorization': `Bearer ${api.token}`,
                                        'X-Ledger-ID': api.currentLedgerId
                                    },
                                    body: formData
                                });
                                if (!response.ok) throw new Error('Lagring feilet');
                                resolve();
                            } catch (e) { reject(e); }
                        }, 'image/jpeg', 0.92);
                    });
                    overlay.remove();
                    showSuccess('Bilde lagret');
                    await this.loadReceipts();
                } catch (error) {
                    showError('Kunne ikke lagre: ' + error.message);
                    btn.disabled = false;
                    btn.textContent = 'Lagre';
                }
            };
        };
    }

    async saveRotation(receiptId, degrees) {
        // Normalize rotation to 0, 90, 180, 270
        const normalizedRotation = ((degrees % 360) + 360) % 360;

        // Get the image
        const imageUrl = api.getReceiptImage(receiptId);
        const img = new Image();
        img.crossOrigin = 'anonymous';

        return new Promise((resolve, reject) => {
            img.onload = async () => {
                try {
                    // Create canvas
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');

                    // Set canvas size based on rotation
                    if (normalizedRotation === 90 || normalizedRotation === 270) {
                        canvas.width = img.height;
                        canvas.height = img.width;
                    } else {
                        canvas.width = img.width;
                        canvas.height = img.height;
                    }

                    // Apply rotation
                    ctx.translate(canvas.width / 2, canvas.height / 2);
                    ctx.rotate(normalizedRotation * Math.PI / 180);
                    ctx.drawImage(img, -img.width / 2, -img.height / 2);

                    // Convert to blob
                    canvas.toBlob(async (blob) => {
                        try {
                            // Upload rotated image
                            const formData = new FormData();
                            formData.append('file', blob, 'rotated.jpg');

                            const response = await fetch(`${api.baseURL}/receipts/${receiptId}/rotate`, {
                                method: 'POST',
                                headers: {
                                    'Authorization': `Bearer ${api.token}`,
                                    'X-Ledger-ID': api.currentLedgerId
                                },
                                body: formData
                            });

                            if (!response.ok) {
                                throw new Error('Failed to save rotation');
                            }

                            resolve();
                        } catch (error) {
                            reject(error);
                        }
                    }, 'image/jpeg', 0.95);
                } catch (error) {
                    reject(error);
                }
            };

            img.onerror = () => reject(new Error('Failed to load image'));
            img.src = imageUrl;
        });
    }

}

const receiptsManager = new ReceiptsManager();
window.receiptsManager = receiptsManager;

export default receiptsManager;
