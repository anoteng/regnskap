import api from './api.js';
import { showModal, closeModal, showError, showSuccess, formatDate } from './utils.js';

class ReceiptsManager {
    constructor() {
        this.receipts = [];
        this.currentFilter = 'PENDING';
    }

    init() {
        this.setupEventListeners();
        this.loadReceipts();
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

    renderReceiptCard(receipt) {
        const imageUrl = api.getReceiptImage(receipt.id);

        return `
            <div class="receipt-card ${receipt.status === 'MATCHED' ? 'receipt-matched' : ''}">
                <div class="receipt-image-container">
                    <img src="${imageUrl}" alt="Kvittering" class="receipt-image" onclick="receiptsManager.showFullImage(${receipt.id})">
                </div>
                <div class="receipt-info">
                    <div class="receipt-meta">
                        <strong>${receipt.original_filename || 'Kvittering'}</strong>
                        <small>${formatDate(receipt.created_at)}</small>
                    </div>
                    ${receipt.receipt_date ? `<div><small>Dato: ${formatDate(receipt.receipt_date)}</small></div>` : ''}
                    ${receipt.amount ? `<div><small>Beløp: ${parseFloat(receipt.amount).toFixed(2)} kr</small></div>` : ''}
                    ${receipt.description ? `<div><small>${receipt.description}</small></div>` : ''}

                    ${receipt.ai_extracted_date || receipt.ai_extracted_amount || receipt.ai_extracted_vendor ? `
                        <div style="background: #f0f9ff; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem; border-left: 3px solid #3b82f6;">
                            <small><strong>🤖 AI-analyse:</strong></small><br>
                            ${receipt.ai_extracted_vendor ? `<small>Leverandør: ${receipt.ai_extracted_vendor}</small><br>` : ''}
                            ${receipt.ai_extracted_date ? `<small>Dato: ${formatDate(receipt.ai_extracted_date)}</small><br>` : ''}
                            ${receipt.ai_extracted_amount ? `<small>Beløp: ${parseFloat(receipt.ai_extracted_amount).toFixed(2)} kr</small><br>` : ''}
                            ${receipt.ai_confidence ? `<small>Sikkerhet: ${(parseFloat(receipt.ai_confidence) * 100).toFixed(0)}%</small>` : ''}
                        </div>
                    ` : ''}

                    ${receipt.ai_processing_error ? `
                        <div style="background: #fee2e2; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;">
                            <small><strong>AI-feil:</strong> ${receipt.ai_processing_error}</small>
                        </div>
                    ` : ''}

                    ${receipt.status === 'MATCHED' ? `
                        <div class="receipt-status">
                            ✓ Matchet til transaksjon #${receipt.matched_transaction_id}
                        </div>
                        <div class="receipt-actions">
                            <button class="btn btn-sm btn-secondary" onclick="receiptsManager.unmatchReceipt(${receipt.id})">
                                Fjern match
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="receiptsManager.deleteReceipt(${receipt.id})">
                                Slett
                            </button>
                        </div>
                    ` : `
                        <div class="receipt-actions">
                            ${!receipt.ai_processed_at ? `
                                <button class="btn btn-sm" style="background: #3b82f6; color: white;" onclick="receiptsManager.analyzeWithAI(${receipt.id}, event)">
                                    🤖 Analyser med AI
                                </button>
                            ` : ''}
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
                    💾 Lagre rotasjon
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

        const content = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                <div>
                    <h3>Kvittering</h3>
                    <img src="${api.getReceiptImage(receiptId)}" style="width: 100%; border-radius: 4px; margin-bottom: 1rem;">
                    ${receipt.receipt_date ? `<p>Dato: ${formatDate(receipt.receipt_date)}</p>` : ''}
                    ${receipt.amount ? `<p>Beløp: ${parseFloat(receipt.amount).toFixed(2)} kr</p>` : ''}
                    ${receipt.description ? `<p>${receipt.description}</p>` : ''}
                </div>
                <div>
                    <h3>Søk etter transaksjon</h3>
                    <div class="form-group">
                        <label>Søk</label>
                        <input type="text" id="transaction-search" placeholder="Søk på beskrivelse, beløp eller dato...">
                    </div>
                    <div class="form-group">
                        <label>Dato fra</label>
                        <input type="date" id="search-start-date" value="${receipt.receipt_date || ''}">
                    </div>
                    <div class="form-group">
                        <label>Dato til</label>
                        <input type="date" id="search-end-date" value="${receipt.receipt_date || ''}">
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

        showModal('Koble kvittering til transaksjon', content);

        this.currentReceiptForMatching = receiptId;

        // Auto-search if we have date
        if (receipt.receipt_date) {
            setTimeout(() => this.searchTransactions(), 100);
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

        const content = `
            <form id="edit-receipt-form">
                <div class="form-group">
                    <label>Dato</label>
                    <input type="date" id="receipt-date" value="${receipt.receipt_date || ''}">
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

        showModal('Rediger kvittering', content);

        document.getElementById('edit-receipt-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveReceiptEdit(id);
        });
    }

    async saveReceiptEdit(id) {
        const date = document.getElementById('receipt-date').value;
        const amount = document.getElementById('receipt-amount').value;
        const description = document.getElementById('receipt-description').value;

        try {
            await api.updateReceipt(id, {
                receipt_date: date || null,
                amount: amount || null,
                description: description || null
            });

            closeModal();
            showSuccess('Kvittering oppdatert');
            await this.loadReceipts();
        } catch (error) {
            showError('Kunne ikke oppdatere kvittering: ' + error.message);
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

    async analyzeWithAI(id, event) {
        const receipt = this.receipts.find(r => r.id === id);
        if (!receipt) return;

        const confirmed = confirm('Analysere denne kvitteringen med AI? Dette vil bruke en AI-operasjon fra ditt månedlige abonnement.');
        if (!confirmed) return;

        try {
            // Show loading state
            let button = null;
            if (event && event.target) {
                button = event.target;
                const originalText = button.innerHTML;
                button.innerHTML = '⏳ Analyserer...';
                button.disabled = true;
            }

            const response = await fetch(`${api.baseURL}/ai/analyze-receipt/${id}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${api.token}`,
                    'X-Ledger-ID': api.currentLedgerId
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'AI-analyse feilet');
            }

            const result = await response.json();

            if (result.success) {
                showSuccess('AI-analyse fullført! Data er ekstrahert og lagret.');
                await this.loadReceipts();
            } else {
                throw new Error(result.error || 'AI-analyse feilet');
            }
        } catch (error) {
            showError('Kunne ikke analysere kvittering: ' + error.message);
            // Reload to reset button state
            await this.loadReceipts();
        }
    }
}

const receiptsManager = new ReceiptsManager();
window.receiptsManager = receiptsManager;

export default receiptsManager;
