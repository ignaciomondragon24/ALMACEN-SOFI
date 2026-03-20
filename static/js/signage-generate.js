/**
 * CHE GOLOSO - Sign Generator Page Logic
 * Product search, auto-fill, items management, and print triggering.
 */

class SignGenerator {
    constructor(config) {
        this.config = config;
        this.items = [];
        this.renderer = new SignRenderer();
        this._init();
    }

    _init() {
        this._setupSearch();
        this._setupPrintControls();
        this._updateItemsUI();
    }

    /* ----------------------------------------------------------
       PRODUCT SEARCH
       ---------------------------------------------------------- */
    _setupSearch() {
        const input = document.getElementById('productSearch');
        const results = document.getElementById('searchResults');
        let timeout = null;

        input.addEventListener('input', () => {
            clearTimeout(timeout);
            const q = input.value.trim();
            if (q.length < 2) { results.innerHTML = ''; results.style.display = 'none'; return; }

            timeout = setTimeout(() => this._search(q), 300);
        });

        // Close results on outside click
        document.addEventListener('click', e => {
            if (!e.target.closest('#productSearch') && !e.target.closest('#searchResults')) {
                results.style.display = 'none';
            }
        });
    }

    async _search(query) {
        const results = document.getElementById('searchResults');
        try {
            const resp = await fetch(`/stocks/api/search/?q=${encodeURIComponent(query)}`);
            const data = await resp.json();
            const products = data.products || [];

            if (products.length === 0) {
                results.innerHTML = '<div class="search-result-item text-muted">No se encontraron productos</div>';
            } else {
                results.innerHTML = products.map(p => `
                    <div class="search-result-item" data-id="${p.id}">
                        <div class="d-flex justify-content-between">
                            <strong>${this._escapeHtml(p.name)}</strong>
                            <span class="text-primary fw-bold">${this._formatPrice(p.sale_price)}</span>
                        </div>
                        <small class="text-muted">${p.barcode || ''} ${p.sku ? '| ' + p.sku : ''}</small>
                    </div>
                `).join('');

                results.querySelectorAll('.search-result-item[data-id]').forEach(el => {
                    el.addEventListener('click', () => {
                        const id = el.dataset.id;
                        this.addProduct(id);
                        results.style.display = 'none';
                        document.getElementById('productSearch').value = '';
                    });
                });
            }
            results.style.display = 'block';
        } catch (err) {
            console.error('Search error:', err);
        }
    }

    /* ----------------------------------------------------------
       ADD PRODUCT
       ---------------------------------------------------------- */
    async addProduct(productId) {
        try {
            const resp = await fetch(
                `${this.config.productDataUrl}?product_id=${productId}&sign_type=${this.config.signType}`
            );
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            this.items.push({
                id: Date.now(),
                product_id: data.product_id,
                product_name: data.product_name,
                data: data.data,
                copies: 1,
            });

            this._updateItemsUI();
            this._updatePreview();
        } catch (err) {
            console.error('Error adding product:', err);
            alert('Error al agregar producto: ' + err.message);
        }
    }

    /* ----------------------------------------------------------
       ITEMS MANAGEMENT
       ---------------------------------------------------------- */
    removeItem(itemId) {
        this.items = this.items.filter(i => i.id !== itemId);
        this._updateItemsUI();
        this._updatePreview();
    }

    setCopies(itemId, copies) {
        const item = this.items.find(i => i.id === itemId);
        if (item) {
            item.copies = Math.max(1, parseInt(copies) || 1);
            this._updateItemsUI();
            this._updatePreview();
        }
    }

    editItemData(itemId, key, value) {
        const item = this.items.find(i => i.id === itemId);
        if (item && item.data) {
            item.data[key] = value;
            this._updatePreview();
        }
    }

    _updateItemsUI() {
        const list = document.getElementById('itemsList');
        const counter = document.getElementById('itemCount');

        const totalCopies = this.items.reduce((s, i) => s + (i.copies || 1), 0);
        if (counter) counter.textContent = `${this.items.length} producto(s), ${totalCopies} cartel(es)`;

        if (this.items.length === 0) {
            list.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-search fa-2x mb-2"></i>
                    <p>Buscá un producto arriba para agregar carteles.</p>
                </div>`;
            return;
        }

        list.innerHTML = this.items.map(item => `
            <div class="item-row p-2 mb-2 rounded" style="background:var(--dsg-surface,#2a2a3e);">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong>${this._escapeHtml(item.product_name)}</strong>
                    <button class="btn btn-sm btn-outline-danger" onclick="generator.removeItem(${item.id})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <label class="text-muted small mb-0">Copias:</label>
                    <input type="number" class="form-control form-control-sm" style="width:70px"
                        value="${item.copies}" min="1" max="100"
                        onchange="generator.setCopies(${item.id}, this.value)">
                    <button class="btn btn-sm btn-outline-info ms-auto"
                        onclick="generator.toggleItemEdit(${item.id})" title="Editar datos">
                        <i class="fas fa-pen"></i>
                    </button>
                </div>
                <div id="edit-${item.id}" class="item-edit mt-2" style="display:none;">
                    ${this._renderDataFields(item)}
                </div>
            </div>
        `).join('');
    }

    _renderDataFields(item) {
        if (!item.data) return '';
        return Object.entries(item.data).map(([key, val]) => `
            <div class="input-group input-group-sm mb-1">
                <span class="input-group-text" style="font-size:0.75rem;">${key}</span>
                <input type="text" class="form-control" value="${this._escapeHtml(String(val))}"
                    onchange="generator.editItemData(${item.id}, '${key}', this.value)">
            </div>
        `).join('');
    }

    toggleItemEdit(itemId) {
        const el = document.getElementById(`edit-${itemId}`);
        if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }

    /* ----------------------------------------------------------
       PREVIEW
       ---------------------------------------------------------- */
    _updatePreview() {
        const container = document.getElementById('previewArea');
        if (!container) return;
        container.innerHTML = '';

        if (this.items.length === 0) {
            container.innerHTML = '<p class="text-muted text-center">Vista previa aquí</p>';
            return;
        }

        // Show first item as preview
        const firstItem = this.items[0];
        const maxW = container.clientWidth - 20;
        const cw = this.config.widthMM * 3.78;
        const ch = this.config.heightMM * 3.78;
        const scale = Math.min(maxW / cw, 2);

        this.renderer.render(container, this.config.layout, firstItem.data,
            this.config.widthMM, this.config.heightMM, scale);
    }

    /* ----------------------------------------------------------
       PRINT
       ---------------------------------------------------------- */
    _setupPrintControls() {
        const btnPrint = document.getElementById('btnPrint');
        if (btnPrint) {
            btnPrint.addEventListener('click', () => this.print());
        }
    }

    print() {
        if (this.items.length === 0) {
            alert('Agregá al menos un producto antes de imprimir.');
            return;
        }

        const paperSize = document.getElementById('paperSize')?.value || 'A4';

        const manager = new SignPrintManager({
            signWidthMM: this.config.widthMM,
            signHeightMM: this.config.heightMM,
            layout: this.config.layout,
            items: this.items,
            paperSize: paperSize,
            margin: 5,
            gap: 2,
        });

        manager.openPrintWindow(this.config.printUrl);
    }

    /* ----------------------------------------------------------
       UTILS
       ---------------------------------------------------------- */
    _formatPrice(value) {
        const num = parseFloat(value) || 0;
        return '$' + num.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}


/* ============================================================
   INITIALIZATION
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
    if (typeof GENERATE_CONFIG !== 'undefined') {
        window.generator = new SignGenerator(GENERATE_CONFIG);
    }
});
