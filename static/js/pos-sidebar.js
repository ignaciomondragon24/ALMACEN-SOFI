/* CHE GOLOSO - POS Sidebar: shortcuts, quick pay, products, history */
(function () {
    'use strict';

    // ─── Estado ────────────────────────────────────────────────────────────────
    let sidebarOpen = true;
    let quickProductsCache = null;   // all products loaded once
    let historyLoaded = false;

    // ─── Elementos ─────────────────────────────────────────────────────────────
    const sidebar      = document.getElementById('pos-sidebar');
    const toggleBtn    = document.getElementById('sidebar-toggle-btn');
    const toggleIcon   = document.getElementById('sidebar-toggle-icon');
    const closeBtn     = document.getElementById('sidebar-close-btn');
    const tabBtns      = document.querySelectorAll('.sidebar-tab-btn');
    const panes        = document.querySelectorAll('.sidebar-pane');
    const refreshBtn   = document.getElementById('btn-refresh-history');
    const qpSearch     = document.getElementById('quick-products-search');
    const qpList       = document.getElementById('quick-products-list');

    // ─── Init ───────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        initToggle();
        initTabs();
        initQuickPayButtons();
        initProductsPane();
        initHistory();
    });

    // ─── Toggle sidebar ─────────────────────────────────────────────────────────
    function setSidebarState(open) {
        sidebarOpen = open;
        sidebar?.classList.toggle('collapsed', !open);
        if (toggleBtn) toggleBtn.classList.toggle('visible', !open);
        if (toggleIcon) toggleIcon.className = open ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
        if (toggleBtn) toggleBtn.title = open ? 'Abrir panel' : 'Abrir panel';
    }

    function initToggle() {
        if (!sidebar) return;
        // Botón externo (solo visible cuando está cerrado)
        toggleBtn?.addEventListener('click', () => setSidebarState(true));
        // Botón X dentro del sidebar
        closeBtn?.addEventListener('click', () => setSidebarState(false));
        // Estado inicial: sidebar abierto, botón externo oculto
        setSidebarState(true);
    }

    // ─── Tabs ───────────────────────────────────────────────────────────────────
    function initTabs() {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => openTab(btn.dataset.tab));
        });
    }

    function openTab(tabId) {
        // Open sidebar if collapsed
        if (!sidebarOpen) {
            setSidebarState(true);
        }
        tabBtns.forEach(b => {
            b.classList.toggle('active', b.dataset.tab === tabId);
            b.setAttribute('aria-selected', b.dataset.tab === tabId);
        });
        panes.forEach(p => {
            p.classList.toggle('active', p.id === `pane-${tabId}`);
        });
        // Load data on demand
        if (tabId === 'history') loadHistory();
        if (tabId === 'products') loadQuickProducts();
    }

    // Expose for external use (keyboard shortcuts, etc.)
    window.POS_sidebar = { openTab, triggerQuickPay };

    // ─── Quick Pay Buttons ──────────────────────────────────────────────────────
    function initQuickPayButtons() {
        document.querySelectorAll('.quick-pay-btn').forEach(btn => {
            btn.addEventListener('click', () => triggerQuickPay(btn.dataset.methodCode));
            btn.addEventListener('keydown', e => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    triggerQuickPay(btn.dataset.methodCode);
                }
            });
        });

        // Keep buttons enabled/disabled in sync with cart
        setInterval(syncQuickPayState, 800);
    }

    function syncQuickPayState() {
        const hasItems = (window.POS_cart?.()?.items?.length || 0) > 0;
        document.querySelectorAll('.quick-pay-btn').forEach(btn => {
            btn.disabled = !hasItems;
        });
    }

    async function triggerQuickPay(methodCode) {
        // Pago Mixto: redirigir al overlay especializado
        if (methodCode === 'mixed') {
            if (window.POS_openMixedCheckout) {
                window.POS_openMixedCheckout();
            } else {
                window.POS_showToast?.('Función de pago mixto no disponible', 'error');
            }
            return;
        }

        const cart = window.POS_cart?.();
        if (!cart || cart.items.length === 0) {
            window.POS_showToast?.('El carrito está vacío', 'warning');
            return;
        }
        const btn = document.querySelector(`.quick-pay-btn[data-method-code="${methodCode}"]`);
        const methodName = btn?.dataset.methodName || methodCode;

        if (!confirm(`¿Cobrar $${window.POS_formatCurrency?.(cart.total) || cart.total} con ${methodName}?`)) return;

        try {
            btn?.classList.add('disabled');
            window.POS_showToast?.(`Procesando con ${methodName}...`, 'info');

            const resp = await fetch(API_URLS.quickCheckout, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify({ transaction_id: TRANSACTION_ID, method_code: methodCode }),
            });
            const data = await resp.json();

            if (data.success) {
                showQuickPaySuccess(data);
            } else {
                window.POS_showToast?.(data.error || 'Error al cobrar', 'error');
                btn?.classList.remove('disabled');
            }
        } catch (err) {
            console.error('Quick pay error:', err);
            window.POS_showToast?.('Error de conexión', 'error');
            btn?.classList.remove('disabled');
        }
    }

    function showQuickPaySuccess(data) {
        const change = parseFloat(data.change || 0);
        const changeHtml = change > 0
            ? `<div class="alert alert-warning my-3"><i class="fas fa-coins me-2"></i><strong>Vuelto: ${window.POS_formatCurrency?.(change) || '$' + change}</strong></div>`
            : '';

        const html = `
        <div class="modal fade" id="quickPaySuccessModal" tabindex="-1" data-bs-backdrop="static">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content bg-dark text-white">
                    <div class="modal-body text-center py-4">
                        <i class="fas fa-check-circle text-success mb-3" style="font-size:4rem"></i>
                        <h4 class="mb-1">¡Cobrado con ${data.method_name}!</h4>
                        <p class="text-muted mb-1">Ticket: <strong class="text-white">${data.ticket_number}</strong></p>
                        <p class="h4 mb-2">Total: <strong class="text-success">${window.POS_formatCurrency?.(data.total) || '$' + data.total}</strong></p>
                        ${changeHtml}
                        <div class="d-flex justify-content-center gap-3 mt-3">
                            <button class="btn btn-outline-light btn-lg" id="qps-skip">
                                <i class="fas fa-forward me-2"></i>Continuar
                            </button>
                            <button class="btn btn-primary btn-lg" id="qps-print">
                                <i class="fas fa-print me-2"></i>Imprimir
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;

        document.getElementById('quickPaySuccessModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', html);

        const el = document.getElementById('quickPaySuccessModal');
        const modal = new bootstrap.Modal(el);
        modal.show();

        el.addEventListener('shown.bs.modal', () => document.getElementById('qps-skip')?.focus(), { once: true });

        document.getElementById('qps-print').addEventListener('click', () => {
            window.open(`/pos/ticket/${data.transaction_id}/`, '_blank', 'width=320,height=500,menubar=no,toolbar=no');
            modal.hide();
            window.location.reload();
        });
        document.getElementById('qps-skip').addEventListener('click', () => {
            modal.hide();
            window.location.reload();
        });
        el.addEventListener('hidden.bs.modal', () => el.remove());

        // Keyboard: P = print, Enter/Esc = skip
        el.addEventListener('keydown', e => {
            if (e.key === 'p' || e.key === 'P') { e.preventDefault(); document.getElementById('qps-print')?.click(); }
        });
    }

    // ─── Products Pane ──────────────────────────────────────────────────────────
    function initProductsPane() {
        if (!qpSearch) return;
        qpSearch.addEventListener('input', () => renderProducts(qpSearch.value.trim().toLowerCase()));
    }

    async function loadQuickProducts() {
        if (quickProductsCache !== null) { renderProducts(qpSearch?.value?.trim().toLowerCase() || ''); return; }

        if (qpList) qpList.innerHTML = '<p style="color:#888;text-align:center;padding:20px 0"><i class="fas fa-spinner fa-spin me-1"></i>Cargando...</p>';

        try {
            // Usar endpoint dedicado que devuelve todos los productos activos
            const resp = await fetch(API_URLS.allProducts);
            const data = await resp.json();
            quickProductsCache = data.products || [];
            renderProducts('');
        } catch (err) {
            console.error('Load products error:', err);
            if (qpList) qpList.innerHTML = '<p style="color:#e74c3c;text-align:center;padding:16px">Error al cargar productos.</p>';
        }
    }

    function renderProducts(filter) {
        if (!qpList || quickProductsCache === null) return;

        const list = filter
            ? quickProductsCache.filter(p =>
                p.name.toLowerCase().includes(filter) ||
                (p.barcode || '').includes(filter) ||
                (p.sku || '').toLowerCase().includes(filter)
            )
            : quickProductsCache;

        if (list.length === 0) {
            qpList.innerHTML = '<p style="color:#888;text-align:center;padding:16px">Sin resultados.</p>';
            return;
        }

        qpList.innerHTML = list.slice(0, 80).map(p => `
            <div class="quick-product-item" tabindex="0"
                 data-product-id="${p.id}" data-is-bulk="${p.is_bulk}"
                 role="button" title="${p.name}">
                <span class="quick-product-code">${p.barcode || p.sku || '—'}</span>
                <span class="quick-product-name">${p.name}</span>
                <span class="quick-product-price">${window.POS_formatCurrency?.(p.unit_price) || '$' + p.unit_price}</span>
            </div>
        `).join('');

        qpList.querySelectorAll('.quick-product-item').forEach(item => {
            const addProduct = () => {
                const id = parseInt(item.dataset.productId);
                // Trigger via window global exposed by pos-main.js (addToCart is inside IIFE)
                // We use a custom event to communicate
                document.dispatchEvent(new CustomEvent('pos:addToCart', { detail: { productId: id, quantity: 1 } }));
            };
            item.addEventListener('click', addProduct);
            item.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); addProduct(); } });
        });
    }

    // ─── Sales History ──────────────────────────────────────────────────────────
    function initHistory() {
        refreshBtn?.addEventListener('click', () => { historyLoaded = false; loadHistory(); });
    }

    async function loadHistory() {
        if (historyLoaded) return;
        const list = document.getElementById('sales-history-list');
        if (!list) return;
        list.innerHTML = '<p style="color:#888;text-align:center;padding:16px"><i class="fas fa-spinner fa-spin me-1"></i>Cargando...</p>';

        try {
            const resp = await fetch(API_URLS.salesHistory);
            const data = await resp.json();
            historyLoaded = true;

            if (!data.success || !data.transactions?.length) {
                list.innerHTML = '<p id="history-empty" style="color:#888;font-size:.82rem;text-align:center;padding:20px 0"><i class="fas fa-info-circle me-1"></i>No hay ventas aún.</p>';
                return;
            }

            list.innerHTML = data.transactions.map(tx => `
                <div class="history-item" tabindex="0" data-tx-id="${tx.id}" role="button">
                    <div class="d-flex justify-content-between align-items-baseline">
                        <span class="history-ticket">${tx.ticket_number}</span>
                        <span class="history-time">${tx.completed_at}</span>
                    </div>
                    <div class="d-flex justify-content-between align-items-baseline mt-1">
                        <span class="history-total">${window.POS_formatCurrency?.(tx.total) || '$' + tx.total}</span>
                        <span style="font-size:.7rem;color:#888">${tx.transaction_type}</span>
                    </div>
                    <div class="history-preview">${tx.items_preview}</div>
                    <div class="history-payments">${tx.payments.join(' + ')}</div>
                    <button class="btn btn-outline-info btn-reprint-history"
                            data-tx-id="${tx.id}" title="Reimprimir ticket ${tx.ticket_number}">
                        <i class="fas fa-print me-1"></i>Reimprimir
                    </button>
                </div>
            `).join('');

            list.querySelectorAll('.btn-reprint-history').forEach(btn => {
                btn.addEventListener('click', e => {
                    e.stopPropagation();
                    const txId = btn.dataset.txId;
                    window.open(`/pos/ticket/${txId}/`, '_blank', 'width=320,height=500,menubar=no,toolbar=no');
                });
            });

        } catch (err) {
            console.error('History load error:', err);
            list.innerHTML = '<p style="color:#e74c3c;text-align:center;padding:16px">Error al cargar historial.</p>';
        }
    }

    // ─── Bridge: pos-main exposes addToCart via custom event ────────────────────
    // pos-main.js must listen for this to work:
    // (added at bottom of pos-main.js via the exposed global)
    document.addEventListener('pos:addToCart', async (e) => {
        const { productId, quantity } = e.detail;
        try {
            const resp = await fetch(API_URLS.addToCart, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify({ transaction_id: TRANSACTION_ID, product_id: productId, quantity }),
            });
            const data = await resp.json();
            if (data.success) {
                window.POS_showToast?.(data.message || 'Producto agregado', 'success');
                window.POS_loadCart?.();
            } else {
                window.POS_showToast?.(data.error || 'Error al agregar', 'error');
            }
        } catch (err) {
            window.POS_showToast?.('Error de conexión', 'error');
        }
    });

})();
