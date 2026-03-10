/* CHE GOLOSO - POS Main JavaScript (Updated) */

(function() {
    'use strict';

    // State
    let cart = {
        items: [],
        subtotal: 0,
        discount: 0,
        total: 0,
        itemCount: 0
    };

    let currentProduct = null;
    let searchTimeout = null;
    let cartFocusIndex = -1; // îndice del cart-item activo por teclado (-1 = ninguno)

    // DOM Elements
    const productSearch = document.getElementById('product-search');
    const searchResults = document.getElementById('search-results');
    const searchResultsList = document.getElementById('search-results-list');
    const cartItems = document.getElementById('cart-items');
    const cartSubtotal = document.getElementById('cart-subtotal');
    const cartDiscount = document.getElementById('cart-discount');
    const discountRow = document.getElementById('discount-row');
    const cartTotal = document.getElementById('cart-total');
    const cartItemsCount = document.getElementById('cart-items-count');
    const btnCheckout = document.getElementById('btn-checkout');
    const btnClearCart = document.getElementById('clear-cart');
    const quickAccessGrid = document.getElementById('quick-access-grid');

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        initClock();
        initSearch();
        initCart();
        initQuickAccess();
        initCheckout();
        initActionButtons();
        initKeyboardShortcuts();
        initQuickAddProduct();
        initHeaderSuspended();
        loadCart();
    });
    
    // Header suspended button
    function initHeaderSuspended() {
        const headerSuspendedBtn = document.getElementById('header-suspended-btn');
        if (headerSuspendedBtn) {
            headerSuspendedBtn.addEventListener('click', () => {
                openSuspendedModal();
            });
        }
    }
    
    // Quick add product
    function initQuickAddProduct() {
        const confirmBtn = document.getElementById('confirm-quick-add');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', handleQuickAddProduct);
        }
        
        // Allow Enter key to submit in the modal
        const quickAddForm = document.getElementById('quick-add-product-form');
        if (quickAddForm) {
            quickAddForm.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleQuickAddProduct();
                }
            });
        }
    }
    
    async function handleQuickAddProduct() {
        const barcode = document.getElementById('quick-add-barcode').value;
        const name = document.getElementById('quick-add-name').value.trim();
        const salePrice = document.getElementById('quick-add-sale-price').value;
        const purchasePrice = document.getElementById('quick-add-purchase-price').value || 0;
        const categoryId = document.getElementById('quick-add-category').value;
        const initialStock = document.getElementById('quick-add-stock').value || 0;
        const shouldAddToCart = document.getElementById('quick-add-to-cart').checked;
        
        // Validation
        if (!name) {
            showToast('El nombre del producto es requerido', 'error');
            document.getElementById('quick-add-name').focus();
            return;
        }
        
        if (!salePrice || parseFloat(salePrice) <= 0) {
            showToast('El precio de venta es requerido', 'error');
            document.getElementById('quick-add-sale-price').focus();
            return;
        }
        
        try {
            const response = await fetch('/pos/api/quick-add-product/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    barcode: barcode,
                    name: name,
                    sale_price: parseFloat(salePrice),
                    purchase_price: parseFloat(purchasePrice),
                    category_id: categoryId || null,
                    initial_stock: parseInt(initialStock)
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(data.message, 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('quickAddProductModal'));
                if (modal) modal.hide();
                
                // Add to cart if checkbox is checked
                if (shouldAddToCart && data.product) {
                    await addToCart(data.product.id, 1);
                }
                
                // Focus back to search
                if (productSearch) {
                    productSearch.value = '';
                    productSearch.focus();
                }
            } else {
                showToast(data.error || 'Error al crear producto', 'error');
            }
        } catch (error) {
            console.error('Quick add product error:', error);
            showToast('Error al crear producto', 'error');
        }
    }

    // Clock
    function initClock() {
        function updateClock() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('es-AR');
            const clockEl = document.getElementById('pos-clock');
            if (clockEl) {
                clockEl.innerHTML = `<i class="fas fa-clock me-1"></i>${timeStr}`;
            }
        }
        updateClock();
        setInterval(updateClock, 1000);
    }

    // Search
    function initSearch() {
        if (!productSearch) return;
        
        productSearch.addEventListener('input', debounce(handleSearch, 150));
        productSearch.addEventListener('keydown', handleSearchKeydown);
        
        document.addEventListener('click', function(e) {
            if (searchResults && !searchResults.contains(e.target) && e.target !== productSearch) {
                hideSearchResults();
            }
        });
    }

    async function handleSearch(e) {
        const query = e.target.value.trim();
        
        // Empezar a buscar desde 1 caracter
        if (query.length < 1) {
            hideSearchResults();
            return;
        }

        try {
            const response = await fetch(`${API_URLS.search}?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.products && data.products.length > 0) {
                showSearchResults(data.products);
            } else {
                // Solo mostrar mensaje si hay al menos 2 caracteres
                if (query.length >= 2) {
                    showSearchResultsEmpty(query);
                } else {
                    hideSearchResults();
                }
            }
        } catch (error) {
            console.error('Search error:', error);
            showToast('Error al buscar productos', 'error');
        }
    }
    
    function showSearchResultsEmpty(query) {
        if (!searchResultsList || !searchResults) return;
        
        // Check if it looks like a barcode (numeric, 8-13 digits)
        const isBarcode = /^\d{8,13}$/.test(query);
        
        if (isBarcode) {
            searchResultsList.innerHTML = `
                <div class="search-result-empty text-center p-3">
                    <i class="fas fa-barcode fa-2x text-warning mb-2"></i>
                    <p class="mb-2 text-light">Código de barras no encontrado:</p>
                    <p class="mb-3"><code class="fs-5">${query}</code></p>
                    <p class="text-muted small mb-3">¿Qué desea hacer?</p>
                    <div class="d-flex justify-content-center gap-2 flex-wrap">
                        <button type="button" class="btn btn-success" onclick="openQuickAddProduct('${query}')">
                            <i class="fas fa-plus-circle me-2"></i>Producto Nuevo
                        </button>
                        <a href="/stocks/bulk-load/?barcode=${query}" class="btn btn-primary">
                            <i class="fas fa-boxes me-2"></i>Carga por Bulto/Display
                        </a>
                    </div>
                    <p class="text-muted small mt-2 mb-0">
                        <i class="fas fa-info-circle me-1"></i>
                        Use "Carga por Bulto" para cargar desde packaging mayorista
                    </p>
                </div>
            `;
        } else {
            searchResultsList.innerHTML = `
                <div class="search-result-empty text-center text-muted p-3">
                    <i class="fas fa-search mb-2"></i>
                    <p class="mb-0">No se encontraron productos para "${query}"</p>
                </div>
            `;
        }
        searchResults.style.display = 'block';
    }
    
    // Open quick add product modal
    window.openQuickAddProduct = function(barcode) {
        const modal = document.getElementById('quickAddProductModal');
        if (!modal) return;
        
        // Reset form
        document.getElementById('quick-add-barcode').value = barcode;
        document.getElementById('quick-add-name').value = '';
        document.getElementById('quick-add-sale-price').value = '';
        document.getElementById('quick-add-purchase-price').value = '';
        document.getElementById('quick-add-category').value = '';
        document.getElementById('quick-add-stock').value = '1';
        document.getElementById('quick-add-to-cart').checked = true;
        
        // Update bulk load link with barcode
        const bulkLoadLink = document.getElementById('option-bulk-load');
        if (bulkLoadLink) {
            bulkLoadLink.href = `/stocks/bulk-load/?barcode=${barcode}`;
        }
        
        // Hide search results
        hideSearchResults();
        
        // Clear search input
        if (productSearch) productSearch.value = '';
        
        // Show modal
        new bootstrap.Modal(modal).show();
        
        // Focus on name field
        setTimeout(() => {
            document.getElementById('quick-add-name').focus();
        }, 500);
    };

    function handleSearchKeydown(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const query = e.target.value.trim();
            
            // Check if it's a barcode (numeric, 8-13 digits)
            if (/^\d{8,13}$/.test(query)) {
                addProductByBarcode(query);
            } else {
                // Select first result if available
                const firstResult = searchResultsList?.querySelector('.search-result-item');
                if (firstResult) {
                    firstResult.click();
                }
            }
        }
        
        // Arrow keys navigation
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            navigateSearchResults(e.key === 'ArrowDown' ? 1 : -1);
        }

        // Tab desde búsqueda → activar navegación del carrito
        if (e.key === 'Tab' && !e.shiftKey) {
            if (searchResults?.style.display !== 'none') return; // el handler global selecciona el 1º resultado
            if (cart.items?.length > 0) {
                e.preventDefault();
                hideSearchResults();
                setCartFocus(cartFocusIndex >= 0 ? cartFocusIndex : cart.items.length - 1);
            }
        }
    }

    function navigateSearchResults(direction) {
        const items = searchResultsList?.querySelectorAll('.search-result-item');
        if (!items || items.length === 0) return;
        
        const current = searchResultsList.querySelector('.search-result-item.active');
        let newIndex = 0;
        
        if (current) {
            const currentIndex = Array.from(items).indexOf(current);
            newIndex = currentIndex + direction;
            if (newIndex < 0) newIndex = items.length - 1;
            if (newIndex >= items.length) newIndex = 0;
            current.classList.remove('active');
        }
        
        items[newIndex].classList.add('active');
        items[newIndex].scrollIntoView({ block: 'nearest' });
    }

    function showSearchResults(products) {
        if (!searchResultsList || !searchResults) return;
        
        searchResultsList.innerHTML = products.map(product => `
            <div class="search-result-item" data-product='${JSON.stringify(product)}'>
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="search-result-name">
                            ${product.name}
                            ${product.is_bulk ? '<span class="badge bg-info ms-1">Granel</span>' : ''}
                            ${product.allow_sell_by_amount ? '<span class="badge bg-warning ms-1">$ Monto</span>' : ''}
                        </div>
                        <div class="search-result-info">
                            ${product.barcode || 'Sin código'} | Stock: ${product.stock} ${product.unit}
                            ${product.is_bulk ? `| $${product.unit_price}/${product.unit}` : ''}
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="search-result-price">${formatCurrency(product.unit_price)}</div>
                        ${product.allow_sell_by_amount ? '<button class="btn btn-sm btn-warning sell-by-amount-btn" data-product-id="' + product.id + '"><i class="fas fa-dollar-sign"></i></button>' : ''}
                    </div>
                </div>
            </div>
        `).join('');
        
        searchResults.style.display = 'block';
        
        // Add click handlers for regular items
        searchResultsList.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', function(e) {
                // Don't trigger if clicking the sell-by-amount button
                if (e.target.closest('.sell-by-amount-btn')) return;
                
                const product = JSON.parse(this.dataset.product);
                
                // For bulk products, show quantity modal
                if (product.is_bulk) {
                    showBulkQuantityModal(product);
                } else {
                    addToCart(product.id, 1);
                    hideSearchResults();
                    productSearch.value = '';
                    productSearch.focus();
                }
            });
        });
        
        // Add handlers for sell-by-amount buttons
        searchResultsList.querySelectorAll('.sell-by-amount-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const productItem = this.closest('.search-result-item');
                const product = JSON.parse(productItem.dataset.product);
                showSellByAmountModal(product);
            });
        });
    }
    
    function showBulkQuantityModal(product) {
        const modalHtml = `
            <div class="modal fade" id="bulkQuantityModal" tabindex="-1">
                <div class="modal-dialog modal-sm">
                    <div class="modal-content bg-dark text-white">
                        <div class="modal-header border-secondary">
                            <h5 class="modal-title"><i class="fas fa-weight me-2"></i>${product.name}</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="text-muted mb-2">Precio: ${formatCurrency(product.unit_price)}/${product.unit}</p>
                            <label class="form-label">Cantidad (${product.unit})</label>
                            <input type="number" 
                                   class="form-control form-control-lg bg-secondary text-white text-center" 
                                   id="bulk-quantity-input"
                                   min="0.001"
                                   step="0.001"
                                   value="0.500"
                                   autofocus>
                            <div class="mt-3 text-center">
                                <span class="fs-4">Total: <strong id="bulk-total-preview">${formatCurrency(0.5 * product.unit_price)}</strong></span>
                            </div>
                        </div>
                        <div class="modal-footer border-secondary">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary" id="confirm-bulk-quantity">Agregar</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('bulkQuantityModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = new bootstrap.Modal(document.getElementById('bulkQuantityModal'));
        const input = document.getElementById('bulk-quantity-input');
        const preview = document.getElementById('bulk-total-preview');
        const confirmBtn = document.getElementById('confirm-bulk-quantity');
        
        input.addEventListener('input', () => {
            const qty = parseFloat(input.value) || 0;
            preview.textContent = formatCurrency(qty * product.unit_price);
        });
        
        confirmBtn.addEventListener('click', () => {
            const qty = parseFloat(input.value) || 0;
            if (qty > 0) {
                addToCart(product.id, qty);
                modal.hide();
                hideSearchResults();
                productSearch.value = '';
                productSearch.focus();
            }
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmBtn.click();
            }
        });
        
        modal.show();
        setTimeout(() => input.select(), 200);
    }
    
    function showSellByAmountModal(product) {
        const modalHtml = `
            <div class="modal fade" id="sellByAmountModal" tabindex="-1">
                <div class="modal-dialog modal-sm">
                    <div class="modal-content bg-dark text-white">
                        <div class="modal-header border-secondary bg-warning bg-opacity-25">
                            <h5 class="modal-title"><i class="fas fa-dollar-sign me-2"></i>Venta por Monto</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-2"><strong>${product.name}</strong></p>
                            <p class="text-muted mb-3">Precio: ${formatCurrency(product.unit_price)}/${product.unit}</p>
                            
                            <label class="form-label">¿Cuánto querés vender?</label>
                            <div class="input-group input-group-lg">
                                <span class="input-group-text bg-warning text-dark">$</span>
                                <input type="number" 
                                       class="form-control bg-secondary text-white text-center" 
                                       id="sell-amount-input"
                                       min="1"
                                       step="1"
                                       value="500"
                                       autofocus>
                            </div>
                            
                            <!-- Quick amount buttons -->
                            <div class="d-flex gap-2 mt-3 flex-wrap">
                                <button type="button" class="btn btn-outline-warning quick-amount-btn" data-amount="100">$100</button>
                                <button type="button" class="btn btn-outline-warning quick-amount-btn" data-amount="200">$200</button>
                                <button type="button" class="btn btn-outline-warning quick-amount-btn" data-amount="500">$500</button>
                                <button type="button" class="btn btn-outline-warning quick-amount-btn" data-amount="1000">$1000</button>
                                <button type="button" class="btn btn-outline-warning quick-amount-btn" data-amount="2000">$2000</button>
                            </div>
                            
                            <div class="mt-4 p-3 bg-secondary rounded">
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Cantidad:</span>
                                    <strong id="amount-quantity-preview">-- ${product.unit}</strong>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Total real:</span>
                                    <strong id="amount-total-preview" class="text-warning">$--</strong>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer border-secondary">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-warning text-dark" id="confirm-sell-amount">
                                <i class="fas fa-cart-plus me-1"></i>Agregar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('sellByAmountModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = new bootstrap.Modal(document.getElementById('sellByAmountModal'));
        const input = document.getElementById('sell-amount-input');
        const qtyPreview = document.getElementById('amount-quantity-preview');
        const totalPreview = document.getElementById('amount-total-preview');
        const confirmBtn = document.getElementById('confirm-sell-amount');
        
        async function updatePreview() {
            const amount = parseFloat(input.value) || 0;
            if (amount <= 0) {
                qtyPreview.textContent = `-- ${product.unit}`;
                totalPreview.textContent = '$--';
                return;
            }
            
            try {
                const response = await fetch('/pos/api/calculate-by-amount/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CSRF_TOKEN
                    },
                    body: JSON.stringify({
                        product_id: product.id,
                        amount: amount
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    qtyPreview.textContent = `${data.quantity.toFixed(3)} ${data.unit}`;
                    totalPreview.textContent = formatCurrency(data.actual_total);
                }
            } catch (error) {
                console.error('Calculate error:', error);
            }
        }
        
        input.addEventListener('input', debounce(updatePreview, 300));
        
        // Quick amount buttons
        document.querySelectorAll('.quick-amount-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                input.value = btn.dataset.amount;
                updatePreview();
            });
        });
        
        confirmBtn.addEventListener('click', async () => {
            const amount = parseFloat(input.value) || 0;
            if (amount <= 0) return;
            
            try {
                const response = await fetch('/pos/api/cart/add-by-amount/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CSRF_TOKEN
                    },
                    body: JSON.stringify({
                        transaction_id: TRANSACTION_ID,
                        product_id: product.id,
                        amount: amount
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    showToast(data.message, 'success');
                    await loadCart();
                    modal.hide();
                    hideSearchResults();
                    productSearch.value = '';
                    productSearch.focus();
                } else {
                    showToast(data.error, 'error');
                }
            } catch (error) {
                console.error('Add by amount error:', error);
                showToast('Error al agregar producto', 'error');
            }
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmBtn.click();
            }
        });
        
        modal.show();
        setTimeout(() => {
            input.select();
            updatePreview();
        }, 200);
    }

    function hideSearchResults() {
        if (searchResults) {
            searchResults.style.display = 'none';
        }
    }

    async function addProductByBarcode(barcode) {
        try {
            const response = await fetch(`${API_URLS.search}?q=${barcode}`);
            const data = await response.json();
            
            if (data.products && data.products.length > 0) {
                const product = data.products[0];
                // For bulk products, show modal
                if (product.is_bulk) {
                    showBulkQuantityModal(product);
                } else {
                    addToCart(product.id, 1);
                    productSearch.value = '';
                }
            } else {
                // Product not found - open modal with options
                openQuickAddProduct(barcode);
            }
        } catch (error) {
            console.error('Barcode search error:', error);
            showToast('Error al buscar producto', 'error');
        }
    }

    // Cart
    function initCart() {
        if (btnClearCart) {
            btnClearCart.addEventListener('click', clearCart);
        }
        document.getElementById('cart-nav-up')?.addEventListener('click', () => {
            if (!cart.items?.length) return;
            navigateCart(-1);
        });
        document.getElementById('cart-nav-down')?.addEventListener('click', () => {
            if (!cart.items?.length) return;
            navigateCart(1);
        });
    }

    // ── Helpers de navegación del carrito por teclado ─────────────────────────
    function setCartFocus(idx) {
        const items = cartItems ? Array.from(cartItems.querySelectorAll('.cart-item')) : [];
        if (!items.length) { cartFocusIndex = -1; return; }
        if (idx < 0) idx = items.length - 1;
        if (idx >= items.length) idx = 0;
        items.forEach(i => i.classList.remove('kb-active'));
        cartFocusIndex = idx;
        items[idx].classList.add('kb-active');
        items[idx].focus();
        items[idx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        document.getElementById('cart-kb-hint')?.classList.add('visible');
    }

    function clearCartFocus() {
        cartFocusIndex = -1;
        cartItems?.querySelectorAll('.cart-item').forEach(i => i.classList.remove('kb-active'));
        document.getElementById('cart-kb-hint')?.classList.remove('visible');
    }

    function navigateCart(dir) {
        const items = cartItems ? Array.from(cartItems.querySelectorAll('.cart-item')) : [];
        if (!items.length) return;
        const newIdx = cartFocusIndex < 0
            ? (dir > 0 ? 0 : items.length - 1)
            : cartFocusIndex + dir;
        setCartFocus(newIdx);
    }

    async function loadCart() {
        try {
            const response = await fetch(API_URLS.getCart);
            const data = await response.json();
            
            if (data.items) {
                cart = {
                    items: data.items,
                    subtotal: data.totals?.subtotal || 0,
                    discount: data.totals?.discount || 0,
                    total: data.totals?.total || 0,
                    itemCount: data.totals?.items_count || 0
                };
                renderCart();
            }
        } catch (error) {
            console.error('Load cart error:', error);
        }
    }

    async function addToCart(productId, quantity = 1) {
        try {
            const response = await fetch(API_URLS.addToCart, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    transaction_id: TRANSACTION_ID,
                    product_id: productId,
                    quantity: quantity
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Reload cart to get updated items
                await loadCart();
                showToast(data.message || 'Producto agregado', 'success');
            } else {
                showToast(data.error || 'Error al agregar producto', 'error');
            }
        } catch (error) {
            console.error('Add to cart error:', error);
            showToast('Error al agregar producto', 'error');
        }
    }

    async function updateCartItem(itemId, quantity) {
        try {
            const response = await fetch(`${API_URLS.updateCart}${itemId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    quantity: quantity
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await loadCart();
            } else {
                showToast(data.error || 'Error al actualizar', 'error');
            }
        } catch (error) {
            console.error('Update cart error:', error);
        }
    }

    async function removeCartItem(itemId) {
        try {
            const response = await fetch(`${API_URLS.removeFromCart}${itemId}/remove/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                await loadCart();
                showToast('Producto eliminado', 'info');
            }
        } catch (error) {
            console.error('Remove from cart error:', error);
        }
    }

    async function clearCart() {
        if (!confirm('¿Está seguro de vaciar el carrito?')) return;
        
        try {
            const response = await fetch(API_URLS.clearCart, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                cart = { items: [], subtotal: 0, discount: 0, total: 0, itemCount: 0 };
                renderCart();
                showToast('Carrito vaciado', 'info');
            }
        } catch (error) {
            console.error('Clear cart error:', error);
        }
    }

    function renderCart() {
        if (!cartItems) return;
        
        const btnCostSale = document.getElementById('btn-cost-sale');
        const btnInternalConsumption = document.getElementById('btn-internal-consumption');
        
        if (!cart.items || cart.items.length === 0) {
            cartItems.innerHTML = `
                <div class="cart-empty text-center text-muted py-5">
                    <i class="fas fa-shopping-basket fa-3x mb-3"></i>
                    <p>El carrito está vacío</p>
                    <small>Escanee o busque productos para agregar</small>
                </div>
            `;
            if (btnCheckout) btnCheckout.disabled = true;
            if (btnCostSale) btnCostSale.disabled = true;
            if (btnInternalConsumption) btnInternalConsumption.disabled = true;
        } else {
            cartItems.innerHTML = cart.items.map(item => `
                <div class="cart-item" data-item-id="${item.id}">
                    <div class="cart-item-info">
                        <div class="cart-item-name">
                            ${item.product_name || item.name}
                            ${item.promotion_name ? `<span class="cart-item-promo badge bg-success ms-1">${item.promotion_name}</span>` : ''}
                        </div>
                        <div class="cart-item-price">${formatCurrency(item.unit_price)} c/u</div>
                    </div>
                    <div class="cart-item-quantity">
                        <button class="btn btn-sm btn-outline-secondary qty-btn" tabindex="-1" data-action="decrease">
                            <i class="fas fa-minus"></i>
                        </button>
                        <input type="number" class="qty-input" tabindex="-1" value="${item.quantity}" min="0.001" step="0.001">
                        <button class="btn btn-sm btn-outline-secondary qty-btn" tabindex="-1" data-action="increase">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <div class="cart-item-subtotal">
                        ${item.discount > 0 ? `<small class="text-success d-block">-${formatCurrency(item.discount)}</small>` : ''}
                        ${formatCurrency(item.subtotal)}
                    </div>
                    <div class="cart-item-remove" title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </div>
                </div>
            `).join('');
            
            if (btnCheckout) btnCheckout.disabled = false;
            if (btnCostSale) btnCostSale.disabled = false;
            if (btnInternalConsumption) btnInternalConsumption.disabled = false;
            
            // Add event listeners
            cartItems.querySelectorAll('.cart-item').forEach(itemEl => {
                const itemId = itemEl.dataset.itemId;
                
                itemEl.querySelector('.cart-item-remove').addEventListener('click', () => {
                    removeCartItem(itemId);
                });
                
                const qtyInput = itemEl.querySelector('.qty-input');
                qtyInput.addEventListener('change', () => {
                    updateCartItem(itemId, parseFloat(qtyInput.value));
                });
                
                itemEl.querySelectorAll('.qty-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        let qty = parseFloat(qtyInput.value);
                        if (btn.dataset.action === 'increase') {
                            qty += 1;
                        } else {
                            qty = Math.max(0, qty - 1);
                        }
                        if (qty === 0) {
                            removeCartItem(itemId);
                        } else {
                            updateCartItem(itemId, qty);
                        }
                    });
                });
            });
            
            // ── TECLADO: navegación por ítems del carrito ─────────────────────────────
            const allItems = Array.from(cartItems.querySelectorAll('.cart-item'));
            allItems.forEach((itemEl, idx) => {
                const itemData = cart.items[idx];
                const qtyInput = itemEl.querySelector('.qty-input');

                itemEl.setAttribute('tabindex', '-1');

                itemEl.addEventListener('focus', () => {
                    allItems.forEach(i => i.classList.remove('kb-active'));
                    itemEl.classList.add('kb-active');
                    cartFocusIndex = idx;
                    document.getElementById('cart-kb-hint')?.classList.add('visible');
                });

                itemEl.addEventListener('blur', () => {
                    setTimeout(() => {
                        if (cartItems && !cartItems.contains(document.activeElement)) {
                            clearCartFocus();
                        }
                    }, 80);
                });

                itemEl.addEventListener('keydown', (e) => {
                    switch (e.key) {
                        case 'ArrowUp':
                            e.preventDefault(); e.stopPropagation();
                            setCartFocus(idx - 1 < 0 ? allItems.length - 1 : idx - 1);
                            break;
                        case 'ArrowDown':
                            e.preventDefault(); e.stopPropagation();
                            setCartFocus(idx + 1 >= allItems.length ? 0 : idx + 1);
                            break;
                        case '+': case '=':
                            e.preventDefault(); e.stopPropagation();
                            if (itemData) updateCartItem(itemData.id, (itemData.quantity || 1) + 1);
                            break;
                        case '-': case '_':
                            e.preventDefault(); e.stopPropagation();
                            if (itemData) {
                                const nq = Math.max(0, (itemData.quantity || 1) - 1);
                                if (nq === 0) removeCartItem(itemData.id);
                                else updateCartItem(itemData.id, nq);
                            }
                            break;
                        case 'Delete': case 'Backspace':
                            e.preventDefault(); e.stopPropagation();
                            if (itemData) removeCartItem(itemData.id);
                            setTimeout(() => {
                                const rem = cartItems?.querySelectorAll('.cart-item');
                                if (rem?.length > 0) setCartFocus(Math.min(idx, rem.length - 1));
                                else { clearCartFocus(); productSearch?.focus(); }
                            }, 350);
                            break;
                        case 'Enter':
                            e.preventDefault();
                            if (qtyInput) {
                                qtyInput.classList.add('editing');
                                qtyInput.focus();
                                qtyInput.select();
                            }
                            break;
                        case 'Escape':
                            e.preventDefault(); e.stopPropagation();
                            clearCartFocus();
                            productSearch?.focus();
                            break;
                        case 'Tab':
                            e.preventDefault();
                            if (!e.shiftKey) {
                                if (idx === allItems.length - 1) {
                                    clearCartFocus();
                                    document.getElementById('btn-checkout')?.focus();
                                } else {
                                    setCartFocus(idx + 1);
                                }
                            } else {
                                if (idx === 0) { clearCartFocus(); productSearch?.focus(); }
                                else setCartFocus(idx - 1);
                            }
                            break;
                    }
                });
            });

            // Qty-input: modo edición (Enter/Esc/Tab devuelven al cart-item)
            cartItems.querySelectorAll('.qty-input').forEach((input, idx) => {
                const itemEl = allItems[idx];
                const itemData = cart.items[idx];
                input.addEventListener('focus', () => input.select());
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === 'Escape' || e.key === 'Tab') {
                        e.preventDefault();
                        if (e.key === 'Enter' && itemData)
                            updateCartItem(itemData.id, parseFloat(input.value) || 1);
                        input.classList.remove('editing');
                        setTimeout(() => itemEl?.focus(), 50);
                    }
                });
            });

            // Restaurar kb-active si el carrito se re-renderizó mientras estaba enfocado
            if (cartFocusIndex >= 0 && cartFocusIndex < allItems.length) {
                allItems[cartFocusIndex].classList.add('kb-active');
                document.getElementById('cart-kb-hint')?.classList.add('visible');
            }
        }
        
        // Update totals
        if (cartSubtotal) cartSubtotal.textContent = formatCurrency(cart.subtotal);
        if (cartItemsCount) cartItemsCount.textContent = cart.itemCount || cart.items?.length || 0;
        
        if (cart.discount > 0) {
            if (cartDiscount) cartDiscount.textContent = `-${formatCurrency(cart.discount)}`;
            if (discountRow) discountRow.style.display = 'flex';
        } else {
            if (discountRow) discountRow.style.display = 'none';
        }
        
        if (cartTotal) cartTotal.textContent = formatCurrency(cart.total);
    }

    // Quick Access
    function initQuickAccess() {
        if (!quickAccessGrid) return;
        
        quickAccessGrid.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const productId = this.dataset.productId;
                if (productId) {
                    addToCart(parseInt(productId), 1);
                }
            });
        });
    }

    // Action Buttons
    function initActionButtons() {
        const btnHold = document.getElementById('btn-hold');
        const btnCancel = document.getElementById('btn-cancel');
        const btnDiscount = document.getElementById('btn-discount');
        const btnReprint = document.getElementById('btn-reprint');
        
        // Discount button
        if (btnDiscount) {
            btnDiscount.addEventListener('click', () => {
                if (cart.items.length === 0) {
                    showToast('El carrito está vacío', 'warning');
                    return;
                }
                openDiscountModal();
            });
        }
        
        // Reprint button
        if (btnReprint) {
            btnReprint.addEventListener('click', async () => {
                try {
                    const response = await fetch('/pos/api/last-transaction/');
                    const data = await response.json();
                    
                    if (data.success && data.transaction_id) {
                        window.open(`/pos/ticket/${data.transaction_id}/`, '_blank');
                    } else {
                        showToast('No hay ticket anterior para reimprimir', 'warning');
                    }
                } catch (error) {
                    console.error('Reprint error:', error);
                    showToast('Error al obtener último ticket', 'error');
                }
            });
        }
        
        if (btnHold) {
            btnHold.addEventListener('click', async () => {
                if (cart.items.length === 0) {
                    showToast('El carrito está vacío', 'warning');
                    return;
                }
                
                try {
                    const response = await fetch(`/pos/api/transaction/${TRANSACTION_ID}/suspend/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': CSRF_TOKEN
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        showToast('Venta suspendida', 'info');
                        window.location.reload();
                    } else {
                        showToast(data.message || 'Error al suspender', 'error');
                    }
                } catch (error) {
                    console.error('Suspend error:', error);
                }
            });
        }
        
        if (btnCancel) {
            btnCancel.addEventListener('click', async () => {
                if (cart.items.length === 0) {
                    showToast('El carrito está vacío', 'warning');
                    return;
                }
                
                if (!confirm('¿Está seguro de cancelar esta venta?')) return;
                
                try {
                    const response = await fetch(`/pos/api/transaction/${TRANSACTION_ID}/cancel/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': CSRF_TOKEN
                        },
                        body: JSON.stringify({ reason: 'Cancelada por cajero' })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        showToast('Venta cancelada', 'info');
                        window.location.reload();
                    } else {
                        showToast(data.message || 'Error al cancelar', 'error');
                    }
                } catch (error) {
                    console.error('Cancel error:', error);
                }
            });
        }
        
        // Suspended transactions button
        const btnSuspended = document.getElementById('btn-suspended');
        if (btnSuspended) {
            btnSuspended.addEventListener('click', () => {
                openSuspendedModal();
            });
        }
        
        // Cost Sale button
        const btnCostSale = document.getElementById('btn-cost-sale');
        if (btnCostSale) {
            btnCostSale.addEventListener('click', () => {
                if (cart.items.length === 0) {
                    showToast('El carrito está vacío', 'warning');
                    return;
                }
                openCostSaleModal();
            });
        }
        
        // Internal Consumption button
        const btnInternalConsumption = document.getElementById('btn-internal-consumption');
        if (btnInternalConsumption) {
            btnInternalConsumption.addEventListener('click', () => {
                if (cart.items.length === 0) {
                    showToast('El carrito está vacío', 'warning');
                    return;
                }
                openInternalConsumptionModal();
            });
        }
    }
    
    // Suspended Transactions Modal
    async function openSuspendedModal() {
        try {
            const response = await fetch('/pos/api/suspended-transactions/');
            const data = await response.json();
            
            if (!data.success || !data.transactions || data.transactions.length === 0) {
                showToast('No hay ventas apartadas', 'info');
                return;
            }
            
            // Create modal HTML
            let modalHtml = `
                <div class="modal fade" id="suspendedModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content bg-dark text-light">
                            <div class="modal-header">
                                <h5 class="modal-title"><i class="fas fa-pause-circle me-2"></i>Ventas Apartadas</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="list-group">
            `;
            
            data.transactions.forEach(tx => {
                const date = new Date(tx.created_at);
                const dateStr = date.toLocaleString('es-AR');
                modalHtml += `
                    <div class="list-group-item list-group-item-action bg-secondary text-light d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">Ticket: ${tx.ticket_number || '#' + tx.id}</h6>
                            <small class="text-muted">${dateStr} - ${tx.items_count} producto(s)</small>
                        </div>
                        <div>
                            <span class="badge bg-primary fs-6 me-2">${formatCurrency(tx.total)}</span>
                            <button class="btn btn-success btn-sm" onclick="resumeTransaction(${tx.id})">
                                <i class="fas fa-play me-1"></i>Retomar
                            </button>
                        </div>
                    </div>
                `;
            });
            
            modalHtml += `
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove existing modal if present
            const existingModal = document.getElementById('suspendedModal');
            if (existingModal) existingModal.remove();
            
            // Add modal to DOM
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('suspendedModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading suspended transactions:', error);
            showToast('Error al cargar ventas apartadas', 'error');
        }
    }
    
    // Resume suspended transaction
    window.resumeTransaction = async function(transactionId) {
        try {
            const response = await fetch(`/pos/api/transaction/${transactionId}/resume/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Venta retomada', 'success');
                // Redirect to POS with resumed transaction
                window.location.href = `/pos/?transaction=${transactionId}`;
            } else {
                showToast(data.message || 'Error al retomar venta', 'error');
            }
        } catch (error) {
            console.error('Resume error:', error);
            showToast('Error al retomar venta', 'error');
        }
    };
    
    // Discount Modal Functions
    function openDiscountModal() {
        const discountModal = document.getElementById('discountModal');
        if (!discountModal) return;
        
        const discountValue = document.getElementById('discount-value');
        const discountSymbol = document.getElementById('discount-symbol');
        const discountPreviewAmount = document.getElementById('discount-preview-amount');
        
        // Reset modal
        if (discountValue) discountValue.value = 10;
        document.getElementById('discount-percent').checked = true;
        if (discountSymbol) discountSymbol.textContent = '%';
        
        // Update preview
        updateDiscountPreview();
        
        // Type change handlers
        document.querySelectorAll('input[name="discount-type"]').forEach(radio => {
            radio.addEventListener('change', () => {
                if (radio.value === 'percent') {
                    discountSymbol.textContent = '%';
                } else {
                    discountSymbol.textContent = '$';
                }
                updateDiscountPreview();
            });
        });
        
        // Value change handler
        if (discountValue) {
            discountValue.addEventListener('input', updateDiscountPreview);
        }
        
        const modal = new bootstrap.Modal(discountModal);
        modal.show();
        
        // Focus on value input
        setTimeout(() => discountValue?.focus(), 300);
        
        // Confirm button
        const confirmBtn = document.getElementById('confirm-discount');
        if (confirmBtn) {
            const newBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
            newBtn.addEventListener('click', () => applyDiscount(modal));
        }
    }
    
    function updateDiscountPreview() {
        const discountValue = parseFloat(document.getElementById('discount-value')?.value || 0);
        const isPercent = document.getElementById('discount-percent')?.checked;
        const previewEl = document.getElementById('discount-preview-amount');
        
        if (!previewEl) return;
        
        let discountAmount = 0;
        if (isPercent) {
            discountAmount = cart.subtotal * (discountValue / 100);
        } else {
            discountAmount = discountValue;
        }
        
        previewEl.textContent = formatCurrency(discountAmount);
    }
    
    async function applyDiscount(modal) {
        const discountValue = parseFloat(document.getElementById('discount-value')?.value || 0);
        const isPercent = document.getElementById('discount-percent')?.checked;
        const reason = document.getElementById('discount-reason')?.value || '';
        
        if (discountValue <= 0) {
            showToast('Ingrese un valor de descuento válido', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/pos/api/transaction/${TRANSACTION_ID}/discount/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    type: isPercent ? 'percent' : 'fixed',
                    value: discountValue,
                    reason: reason
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Descuento aplicado', 'success');
                modal.hide();
                await loadCart();
            } else {
                showToast(data.error || 'Error al aplicar descuento', 'error');
            }
        } catch (error) {
            console.error('Discount error:', error);
            showToast('Error al aplicar descuento', 'error');
        }
    }
    
    // Cost Sale Modal Functions
    function openCostSaleModal() {
        const costSaleModal = document.getElementById('costSaleModal');
        if (!costSaleModal) return;
        
        // Calculate cost total (estimate - real calculation happens on server)
        // We'll show the current total as estimate
        const costSaleTotal = document.getElementById('cost-sale-total');
        if (costSaleTotal) {
            costSaleTotal.textContent = 'Calculando...';
        }
        
        // Clear items list temporarily
        const costSaleItems = document.getElementById('cost-sale-items');
        if (costSaleItems) {
            costSaleItems.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Calculando costos...</div>';
        }
        
        // Fetch cost total from server
        fetchCostTotal();
        
        const modal = new bootstrap.Modal(costSaleModal);
        modal.show();
        
        // Setup confirm button
        const confirmBtn = document.getElementById('confirm-cost-sale');
        if (confirmBtn) {
            // Remove old listeners
            const newBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
            
            newBtn.addEventListener('click', processCostSale);
        }
    }
    
    async function fetchCostTotal() {
        const costSaleTotal = document.getElementById('cost-sale-total');
        const costSaleItems = document.getElementById('cost-sale-items');
        
        try {
            const response = await fetch(API_URLS.calculateCost);
            const data = await response.json();
            
            if (data.success) {
                // Store the cost total for later use
                window.costSaleTotal = data.total_cost;
                
                if (costSaleTotal) {
                    costSaleTotal.textContent = formatCurrency(data.total_cost);
                }
                
                if (costSaleItems && data.items) {
                    costSaleItems.innerHTML = data.items.map(item => `
                        <div class="d-flex justify-content-between py-1 border-bottom border-secondary">
                            <span>${item.product_name} x ${item.quantity}</span>
                            <span>${formatCurrency(item.total)}</span>
                        </div>
                    `).join('');
                }
            } else {
                if (costSaleTotal) {
                    costSaleTotal.textContent = 'Error';
                }
            }
        } catch (error) {
            console.error('Error fetching cost total:', error);
            if (costSaleTotal) {
                costSaleTotal.textContent = 'Error de conexión';
            }
        }
    }
    
    async function processCostSale() {
        const note = document.getElementById('cost-sale-note')?.value || '';
        const selectedMethod = document.querySelector('input[name="cost-payment-method"]:checked');
        
        if (!selectedMethod) {
            showToast('Seleccione un método de pago', 'warning');
            return;
        }
        
        const costTotal = window.costSaleTotal || 0;
        if (costTotal <= 0) {
            showToast('Error: No se pudo calcular el costo', 'error');
            return;
        }
        
        const confirmBtn = document.getElementById('confirm-cost-sale');
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
        }
        
        try {
            const response = await fetch(API_URLS.costSale, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    transaction_id: TRANSACTION_ID,
                    payments: [{
                        method_id: selectedMethod.dataset.methodId,
                        method_code: selectedMethod.dataset.methodCode,
                        amount: costTotal
                    }],
                    note: note
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`Venta al costo completada. Total: ${formatCurrency(data.total)}`, 'success');
                
                // Close modal and redirect to ticket
                bootstrap.Modal.getInstance(document.getElementById('costSaleModal'))?.hide();
                
                if (data.transaction_id) {
                    window.open(`/pos/ticket/${data.transaction_id}/`, '_blank');
                }
                
                window.location.reload();
            } else {
                showToast(data.error || 'Error al procesar venta al costo', 'error');
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Venta al Costo';
                }
            }
        } catch (error) {
            console.error('Cost sale error:', error);
            showToast('Error de conexión', 'error');
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Venta al Costo';
            }
        }
    }
    
    // Internal Consumption Modal Functions
    function openInternalConsumptionModal() {
        const consumptionModal = document.getElementById('internalConsumptionModal');
        if (!consumptionModal) return;
        
        // Populate items list
        const consumptionItems = document.getElementById('consumption-items');
        if (consumptionItems && cart.items) {
            consumptionItems.innerHTML = cart.items.map(item => `
                <div class="d-flex justify-content-between py-1 border-bottom border-secondary">
                    <span>${item.product_name || item.name}</span>
                    <span>x ${item.quantity}</span>
                </div>
            `).join('');
        }
        
        // Fetch real cost value
        const costValue = document.getElementById('consumption-cost-value');
        if (costValue) {
            costValue.textContent = 'Calculando...';
            fetch(API_URLS.calculateCost)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        costValue.textContent = formatCurrency(data.total_cost);
                    }
                })
                .catch(() => {
                    costValue.textContent = 'N/A';
                });
        }
        
        const modal = new bootstrap.Modal(consumptionModal);
        modal.show();
        
        // Setup confirm button
        const confirmBtn = document.getElementById('confirm-consumption');
        if (confirmBtn) {
            // Remove old listeners
            const newBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
            
            newBtn.addEventListener('click', processInternalConsumption);
        }
    }
    
    async function processInternalConsumption() {
        const note = document.getElementById('consumption-note')?.value || '';
        
        if (!note.trim()) {
            showToast('Ingrese quién consume para el registro', 'warning');
            return;
        }
        
        const confirmBtn = document.getElementById('confirm-consumption');
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
        }
        
        try {
            const response = await fetch(API_URLS.internalConsumption, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    transaction_id: TRANSACTION_ID,
                    note: note
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`Consumo interno registrado. Ticket: ${data.ticket_number}`, 'success');
                
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('internalConsumptionModal'))?.hide();
                
                if (data.transaction_id) {
                    window.open(`/pos/ticket/${data.transaction_id}/`, '_blank');
                }
                
                window.location.reload();
            } else {
                showToast(data.error || 'Error al registrar consumo', 'error');
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Consumo';
                }
            }
        } catch (error) {
            console.error('Internal consumption error:', error);
            showToast('Error de conexión', 'error');
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Consumo';
            }
        }
    }

    // Checkout
    function initCheckout() {
        const checkoutModal = document.getElementById('checkoutModal');
        const confirmPayment = document.getElementById('confirm-payment');
        const checkoutTotal = document.getElementById('checkout-total');
        const totalReceived = document.getElementById('total-received');
        const changeAmount = document.getElementById('change-amount');
        const paymentInputs = document.getElementById('payment-inputs');
        
        if (!btnCheckout || !checkoutModal) return;
        
        // Auto-select first payment method and focus amount when modal opens
        checkoutModal.addEventListener('shown.bs.modal', () => {
            const firstCheckbox = document.querySelector('.payment-method-check');
            if (firstCheckbox && !firstCheckbox.checked) {
                firstCheckbox.checked = true;
                firstCheckbox.dispatchEvent(new Event('change'));
            }
            // Auto-focus el input de monto después de que se cree
            setTimeout(() => {
                const firstAmountInput = paymentInputs?.querySelector('.payment-amount');
                if (firstAmountInput) {
                    firstAmountInput.focus();
                    firstAmountInput.select();
                }
            }, 150);
        });
        
        btnCheckout.addEventListener('click', () => {
            if (!checkoutTotal) return;
            
            checkoutTotal.textContent = formatCurrency(cart.total);
            if (paymentInputs) paymentInputs.innerHTML = '';
            if (totalReceived) totalReceived.textContent = formatCurrency(0);
            if (changeAmount) changeAmount.textContent = formatCurrency(0);
            if (confirmPayment) confirmPayment.disabled = true;
            
            // Reset checkboxes
            document.querySelectorAll('.payment-method-check').forEach(cb => {
                cb.checked = false;
            });
            
            const modal = new bootstrap.Modal(checkoutModal);
            modal.show();
        });
        
        // Tab desde el botón COBRAR → vuelve al buscador (completa el ciclo de Tab)
        btnCheckout.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' && !e.shiftKey) {
                e.preventDefault();
                productSearch?.focus();
            }
            if (e.key === 'Tab' && e.shiftKey) {
                e.preventDefault();
                if (cart.items?.length > 0) setCartFocus(cart.items.length - 1);
                else productSearch?.focus();
            }
        });
        
        // Payment method checkboxes
        document.querySelectorAll('.payment-method-check').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const methodId = this.dataset.methodId;
                const methodName = this.dataset.methodName;
                const methodCode = this.dataset.methodCode;
                
                if (this.checked) {
                    // Check if Mercado Pago Point method
                    const isMercadoPago = methodCode === 'mercadopago' || methodCode === 'mp_point';
                    
                    // Add input
                    const inputHtml = `
                        <div class="payment-method-input mb-3" id="input-method-${methodId}">
                            <label class="form-label">${methodName}</label>
                            <div class="input-group">
                                <span class="input-group-text">$</span>
                                <input type="number" 
                                       class="form-control bg-dark text-white payment-amount" 
                                       data-method-id="${methodId}"
                                       data-method-code="${methodCode || ''}"
                                       step="0.01" 
                                       min="0"
                                       value="${cart.total.toFixed(2)}">
                            </div>
                            ${isMercadoPago ? `
                            <div class="mt-2">
                                <button type="button" class="btn btn-info btn-sm btn-mp-point" data-method-id="${methodId}">
                                    <i class="fas fa-mobile-alt me-1"></i>Enviar a Point
                                </button>
                                <span class="ms-2 mp-status text-muted small" id="mp-status-${methodId}"></span>
                            </div>
                            ` : ''}
                        </div>
                    `;
                    if (paymentInputs) {
                        paymentInputs.insertAdjacentHTML('beforeend', inputHtml);
                        
                        // Focus the input
                        const input = paymentInputs.querySelector(`[data-method-id="${methodId}"]`);
                        if (input) {
                            input.focus();
                            input.select();
                            input.addEventListener('input', updatePaymentTotals);
                            // Teclado: Tab → confirm; Enter → confirmar si habilitado
                            input.addEventListener('keydown', (ev) => {
                                if (ev.key === 'Tab' && !ev.shiftKey) {
                                    ev.preventDefault();
                                    const allAmts = Array.from(paymentInputs.querySelectorAll('.payment-amount'));
                                    const ci = allAmts.indexOf(input);
                                    if (allAmts[ci + 1]) {
                                        allAmts[ci + 1].focus();
                                    } else {
                                        document.getElementById('confirm-payment')?.focus();
                                    }
                                }
                                if (ev.key === 'Tab' && ev.shiftKey) {
                                    ev.preventDefault();
                                    const allAmts = Array.from(paymentInputs.querySelectorAll('.payment-amount'));
                                    const ci = allAmts.indexOf(input);
                                    if (allAmts[ci - 1]) {
                                        allAmts[ci - 1].focus();
                                    } else {
                                        document.querySelector('.payment-method-check')?.focus();
                                    }
                                }
                                if (ev.key === 'Enter') {
                                    ev.preventDefault();
                                    const btn = document.getElementById('confirm-payment');
                                    if (btn && !btn.disabled) btn.click();
                                }
                            });
                        }
                        
                        // Add Mercado Pago Point button handler
                        if (isMercadoPago) {
                            const mpBtn = paymentInputs.querySelector(`.btn-mp-point[data-method-id="${methodId}"]`);
                            if (mpBtn) {
                                mpBtn.addEventListener('click', () => handleMercadoPagoPoint(methodId));
                            }
                        }
                    }
                } else {
                    // Remove input
                    const inputDiv = document.getElementById(`input-method-${methodId}`);
                    if (inputDiv) inputDiv.remove();
                }
                
                updatePaymentTotals();
            });
        });
        
        // Handle Mercado Pago Point integration
        async function handleMercadoPagoPoint(methodId) {
            const input = document.querySelector(`.payment-amount[data-method-id="${methodId}"]`);
            const statusEl = document.getElementById(`mp-status-${methodId}`);
            const mpBtn = document.querySelector(`.btn-mp-point[data-method-id="${methodId}"]`);
            
            if (!input) return;
            
            const amount = parseFloat(input.value) || 0;
            if (amount <= 0) {
                showToast('Ingrese un monto válido', 'warning');
                return;
            }
            
            try {
                mpBtn.disabled = true;
                mpBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Enviando...';
                statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Conectando con Point...';
                statusEl.className = 'ms-2 mp-status text-info small';
                
                const response = await fetch('/mercadopago/api/create-intent/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CSRF_TOKEN
                    },
                    body: JSON.stringify({
                        amount: amount,
                        transaction_id: TRANSACTION_ID,
                        description: `Venta POS - ${cart.itemCount} items`
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusEl.innerHTML = '<i class="fas fa-check text-success"></i> Enviado al Point';
                    statusEl.className = 'ms-2 mp-status text-success small';
                    mpBtn.innerHTML = '<i class="fas fa-check me-1"></i>Enviado';
                    
                    // Start polling for payment status
                    if (data.payment_intent && data.payment_intent.id) {
                        pollMercadoPagoStatus(data.payment_intent.id, methodId, statusEl, mpBtn);
                    }
                    
                    showToast('Pago enviado al Point. Esperando confirmación...', 'info');
                } else {
                    throw new Error(data.error || 'Error al conectar con Mercado Pago');
                }
            } catch (error) {
                console.error('MP Point error:', error);
                statusEl.innerHTML = '<i class="fas fa-times text-danger"></i> Error';
                statusEl.className = 'ms-2 mp-status text-danger small';
                mpBtn.disabled = false;
                mpBtn.innerHTML = '<i class="fas fa-mobile-alt me-1"></i>Reintentar';
                showToast(error.message || 'Error al conectar con Mercado Pago Point', 'error');
            }
        }
        
        // Poll for Mercado Pago payment status
        async function pollMercadoPagoStatus(paymentIntentId, methodId, statusEl, mpBtn) {
            let attempts = 0;
            const maxAttempts = 60; // 2 minutes max
            
            const pollInterval = setInterval(async () => {
                attempts++;
                
                if (attempts > maxAttempts) {
                    clearInterval(pollInterval);
                    statusEl.innerHTML = '<i class="fas fa-clock text-warning"></i> Tiempo agotado';
                    mpBtn.disabled = false;
                    mpBtn.innerHTML = '<i class="fas fa-mobile-alt me-1"></i>Reintentar';
                    return;
                }
                
                try {
                    const response = await fetch(`/mercadopago/api/status/${paymentIntentId}/`);
                    const data = await response.json();
                    
                    if (data.status === 'approved' || data.status === 'FINISHED') {
                        clearInterval(pollInterval);
                        statusEl.innerHTML = '<i class="fas fa-check-circle text-success"></i> ¡Pago aprobado!';
                        mpBtn.classList.remove('btn-info');
                        mpBtn.classList.add('btn-success');
                        mpBtn.innerHTML = '<i class="fas fa-check me-1"></i>Aprobado';
                        showToast('¡Pago con Mercado Pago aprobado!', 'success');
                    } else if (data.status === 'rejected' || data.status === 'cancelled' || data.status === 'CANCELED') {
                        clearInterval(pollInterval);
                        statusEl.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Rechazado';
                        mpBtn.disabled = false;
                        mpBtn.innerHTML = '<i class="fas fa-mobile-alt me-1"></i>Reintentar';
                        showToast('Pago rechazado o cancelado', 'warning');
                    } else {
                        // Still processing
                        statusEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Esperando... (${attempts}s)`;
                    }
                } catch (error) {
                    console.error('Poll error:', error);
                }
            }, 2000); // Poll every 2 seconds
        }
        
        function updatePaymentTotals() {
            let total = 0;
            if (paymentInputs) {
                paymentInputs.querySelectorAll('.payment-amount').forEach(input => {
                    total += parseFloat(input.value) || 0;
                });
            }
            
            if (totalReceived) totalReceived.textContent = formatCurrency(total);
            
            const change = total - cart.total;
            if (changeAmount) changeAmount.textContent = formatCurrency(Math.max(0, change));
            
            // Enable confirm button if total received >= cart total
            if (confirmPayment) confirmPayment.disabled = total < cart.total;
        }
        
        if (confirmPayment) {
            confirmPayment.addEventListener('click', async () => {
                const payments = [];
                if (paymentInputs) {
                    paymentInputs.querySelectorAll('.payment-amount').forEach(input => {
                        const amount = parseFloat(input.value) || 0;
                        if (amount > 0) {
                            payments.push({
                                method_id: parseInt(input.dataset.methodId),
                                amount: amount
                            });
                        }
                    });
                }
                
                if (payments.length === 0) {
                    showToast('Seleccione un método de pago', 'warning');
                    return;
                }
                
                try {
                    confirmPayment.disabled = true;
                    confirmPayment.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
                    
                    const response = await fetch(API_URLS.checkout, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': CSRF_TOKEN
                        },
                        body: JSON.stringify({
                            transaction_id: TRANSACTION_ID,
                            payments: payments
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        bootstrap.Modal.getInstance(checkoutModal).hide();
                        
                        // Show success modal with print option
                        showSaleSuccessModal(data);
                    } else {
                        showToast(data.error || 'Error al procesar la venta', 'error');
                    }
                } catch (error) {
                    console.error('Checkout error:', error);
                    showToast('Error al procesar la venta', 'error');
                } finally {
                    confirmPayment.disabled = false;
                    confirmPayment.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Pago';
                }
            });
            // Shift+Tab desde confirm-payment → último input de monto
            confirmPayment.addEventListener('keydown', (e) => {
                if (e.key === 'Tab' && e.shiftKey) {
                    e.preventDefault();
                    const allAmts = paymentInputs?.querySelectorAll('.payment-amount');
                    if (allAmts && allAmts.length > 0) {
                        allAmts[allAmts.length - 1].focus();
                    } else {
                        document.querySelector('.payment-method-check')?.focus();
                    }
                }
            });
        }
    }
    
    // Show sale success modal with print option
    function showSaleSuccessModal(data) {
        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="saleSuccessModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content bg-dark text-white">
                        <div class="modal-body text-center py-5">
                            <div class="mb-4">
                                <i class="fas fa-check-circle text-success" style="font-size: 5rem;"></i>
                            </div>
                            <h3 class="mb-3">¡Venta Completada!</h3>
                            <p class="mb-2 text-muted">Ticket: <strong class="text-white">${data.ticket_number}</strong></p>
                            <p class="mb-4 h4">Total: <strong class="text-success">${formatCurrency(data.total)}</strong></p>
                            ${data.change > 0 ? `
                                <div class="alert alert-warning mb-4">
                                    <i class="fas fa-coins me-2"></i>
                                    <strong>Vuelto: ${formatCurrency(data.change)}</strong>
                                </div>
                            ` : ''}
                            <div class="d-flex justify-content-center gap-3">
                                <button type="button" class="btn btn-outline-light btn-lg" id="btnSkipPrint">
                                    <i class="fas fa-forward me-2"></i>Continuar
                                </button>
                                <button type="button" class="btn btn-primary btn-lg" id="btnPrintTicket">
                                    <i class="fas fa-print me-2"></i>Imprimir Ticket
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('saleSuccessModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const successModal = document.getElementById('saleSuccessModal');
        const modal = new bootstrap.Modal(successModal);
        modal.show();
        
        // Foco en "Continuar" al mostrar el modal (navegación por teclado)
        successModal.addEventListener('shown.bs.modal', () => {
            document.getElementById('btnSkipPrint')?.focus();
        }, { once: true });
        
        // Print ticket button
        document.getElementById('btnPrintTicket').addEventListener('click', () => {
            // Abrir ventana del ticket (se auto-imprime y auto-cierra sola)
            const printWin = window.open(`/pos/ticket/${data.transaction_id}/`, '_blank', 'width=320,height=500,menubar=no,toolbar=no,location=no,status=no');
            if (printWin) {
                printWin.focus();
            }
            modal.hide();
            window.location.reload();
        });
        
        // Skip print button
        document.getElementById('btnSkipPrint').addEventListener('click', () => {
            modal.hide();
            window.location.reload();
        });
        
        // Cleanup on hide
        successModal.addEventListener('hidden.bs.modal', () => {
            successModal.remove();
        });
    }

    // Keyboard Shortcuts
    // ─── Keyboard shortcuts (dynamic, from server) ───────────────────────────

    // Build a lookup map:  key → action  (e.g. 'F8' → 'checkout')
    let shortcutMap = {};

    function buildShortcutMap(shortcuts) {
        shortcutMap = {};
        (shortcuts || []).forEach(sc => {
            if (sc.is_enabled && sc.key && sc.key !== 'none') {
                shortcutMap[sc.key] = sc.action;
            }
        });
    }

    // Expose so pos-sidebar.js can refresh after admin changes
    window.POS_rebuildShortcuts = buildShortcutMap;

    function dispatchAction(action) {
        switch (action) {
            case 'help':                showShortcutsHelp(); break;
            case 'search_focus':
                if (productSearch) { productSearch.focus(); productSearch.select(); }
                break;
            case 'clear_cart':          clearCart(); break;
            case 'hold':                document.getElementById('btn-hold')?.click(); break;
            case 'suspended':           document.getElementById('btn-suspended')?.click(); break;
            case 'discount':            document.getElementById('btn-discount')?.click(); break;
            case 'cancel':              document.getElementById('btn-cancel')?.click(); break;
            case 'checkout':
                if (btnCheckout && !btnCheckout.disabled) btnCheckout.click();
                break;
            case 'reprint':             document.getElementById('btn-reprint')?.click(); break;
            case 'cost_sale':           document.getElementById('btn-cost-sale')?.click(); break;
            case 'internal_consumption':document.getElementById('btn-internal-consumption')?.click(); break;
            case 'sales_history':
                // Open sidebar → history tab
                if (window.POS_sidebar) window.POS_sidebar.openTab('history');
                break;
            case 'dashboard':
                if (confirm('¿Salir del POS?')) window.location.href = '/accounts/dashboard/';
                break;
            // pay_* actions → quick checkout
            default:
                if (action.startsWith('pay_')) {
                    const methodCode = action.replace('pay_', '');
                    window.POS_sidebar?.triggerQuickPay(methodCode);
                }
        }
    }

    function initKeyboardShortcuts() {
        // Build map from pre-loaded shortcuts
        buildShortcutMap(typeof INITIAL_SHORTCUTS !== 'undefined' ? INITIAL_SHORTCUTS : []);

        document.addEventListener('keydown', function(e) {
            // Get active modal
            const activeModal = document.querySelector('.modal.show');
            
            // Modal-specific shortcuts
            if (activeModal) {
                const modalId = activeModal.id;
                
                // Checkout modal shortcuts
                if (modalId === 'checkoutModal') {
                    // Enter to confirm payment (from anywhere in the modal)
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        const confirmBtn = document.getElementById('confirm-payment');
                        if (confirmBtn && !confirmBtn.disabled) {
                            confirmBtn.click();
                        }
                    }
                    // Escape to close modal
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        bootstrap.Modal.getInstance(activeModal).hide();
                    }
                    // Number keys 1-9 for payment method selection
                    if (e.key >= '1' && e.key <= '9' && !e.target.tagName.match(/INPUT|TEXTAREA/)) {
                        e.preventDefault();
                        const methodIndex = parseInt(e.key) - 1;
                        const checkboxes = document.querySelectorAll('.payment-method-check');
                        if (checkboxes[methodIndex]) {
                            checkboxes[methodIndex].checked = !checkboxes[methodIndex].checked;
                            checkboxes[methodIndex].dispatchEvent(new Event('change'));
                        }
                    }
                }
                
                // Quantity modal shortcuts
                if (modalId === 'quantityModal') {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        document.getElementById('confirm-quantity')?.click();
                    }
                }
                
                // Cost sale modal shortcuts
                if (modalId === 'costSaleModal') {
                    if (e.key === 'Enter' && !e.target.tagName.match(/INPUT|TEXTAREA/)) {
                        e.preventDefault();
                        document.getElementById('confirm-cost-sale')?.click();
                    }
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        bootstrap.Modal.getInstance(activeModal).hide();
                    }
                }
                
                // Internal consumption modal shortcuts
                if (modalId === 'internalConsumptionModal') {
                    if (e.key === 'Enter' && !e.target.tagName.match(/INPUT|TEXTAREA/)) {
                        e.preventDefault();
                        document.getElementById('confirm-consumption')?.click();
                    }
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        bootstrap.Modal.getInstance(activeModal).hide();
                    }
                }
                
                // Discount modal shortcuts
                if (modalId === 'discountModal') {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        document.getElementById('confirm-discount')?.click();
                    }
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        bootstrap.Modal.getInstance(activeModal)?.hide();
                    }
                }
                
                // Sale success modal shortcuts (→ P para imprimir, Enter/Esp continuar)
                if (modalId === 'saleSuccessModal') {
                    if (e.key === 'p' || e.key === 'P') {
                        e.preventDefault();
                        document.getElementById('btnPrintTicket')?.click();
                    }
                }
                
                return; // Don't process other shortcuts while modal is open
            }
            
            // Don't trigger shortcuts when typing in inputs (except specific keys)
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                // Escape - blur input and clear search
                if (e.key === 'Escape') {
                    e.target.blur();
                    hideSearchResults();
                    if (productSearch) {
                        productSearch.value = '';
                        productSearch.focus();
                    }
                }
                // Tab in search - select first result
                if (e.key === 'Tab' && e.target === productSearch && searchResults?.style.display !== 'none') {
                    e.preventDefault();
                    const firstResult = searchResultsList?.querySelector('.search-result-item');
                    if (firstResult) {
                        firstResult.click();
                    }
                }
                // Permite F-keys (F1-F12) desde inputs que NO sean el buscador
                // Ej: desde qty-input del carrito, F8 dispara COBRAR, F4 apartar, etc.
                if (/^F\d+$/.test(e.key) && e.target !== productSearch) {
                    // Continuar hasta el switch de atajos globales
                } else {
                    return;
                }
            }
            
            // Global shortcuts (when not in an input) — dynamic from shortcutMap
            // Handle always-on non-configurable keys first
            if (e.key === 'Escape') {
                hideSearchResults();
                if (productSearch) { productSearch.value = ''; productSearch.focus(); }
                return;
            }
            if (e.key === '+' || e.key === '=') {
                e.preventDefault();
                if (cart.items && cart.items.length > 0) {
                    const target = cartFocusIndex >= 0 ? cart.items[cartFocusIndex] : cart.items[cart.items.length - 1];
                    if (target?.product_id) addToCart(target.product_id, 1);
                }
                return;
            }
            if (e.key === '-') {
                e.preventDefault();
                if (cart.items && cart.items.length > 0) {
                    const target = cartFocusIndex >= 0 ? cart.items[cartFocusIndex] : cart.items[cart.items.length - 1];
                    if (target && target.quantity > 1) updateCartItem(target.id, target.quantity - 1);
                    else if (target) removeCartItem(target.id);
                }
                return;
            }
            if (e.key === 'Delete') {
                e.preventDefault();
                if (cart.items && cart.items.length > 0) {
                    const target = cartFocusIndex >= 0 ? cart.items[cartFocusIndex] : cart.items[cart.items.length - 1];
                    if (target) removeCartItem(target.id);
                }
                return;
            }

            // Alt+1-9 for quick access buttons
            if (e.key >= '1' && e.key <= '9' && e.altKey) {
                e.preventDefault();
                const buttonIndex = parseInt(e.key) - 1;
                const quickBtns = quickAccessGrid?.querySelectorAll('.quick-btn');
                if (quickBtns?.[buttonIndex]) quickBtns[buttonIndex].click();
                return;
            }

            // Configurable shortcut lookup
            const keyStr = e.altKey ? `Alt+${e.key}` : e.key;
            const action = shortcutMap[keyStr];
            if (action) {
                e.preventDefault();
                dispatchAction(action);
            }
        });
        
        // Auto-focus search bar after any click outside inputs
        document.addEventListener('click', function(e) {
            if (!e.target.matches('input, button, a, .btn, .quick-btn, .cart-item *, .search-result-item *')) {
                setTimeout(() => {
                    if (productSearch && !document.querySelector('.modal.show')) {
                        productSearch.focus();
                    }
                }, 100);
            }
        });
    }
    
    function showShortcutsHelp() {
        // Build dynamic rows from shortcutMap
        const shortcuts = typeof INITIAL_SHORTCUTS !== 'undefined' ? INITIAL_SHORTCUTS : [];
        const configRows = shortcuts.map(sc => {
            const keyHtml = sc.key === 'none'
                ? '<span style="color:#555">—</span>'
                : `<kbd style="background:#222;color:#00d2d3;padding:2px 6px;border-radius:3px;font-family:monospace">${sc.key}</kbd>`;
            return `<tr><td>${keyHtml}</td><td>${sc.label}</td></tr>`;
        }).join('');

        const helpHtml = `
            <div class="modal fade" id="shortcutsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content bg-dark text-white">
                        <div class="modal-header border-secondary">
                            <h5 class="modal-title"><i class="fas fa-keyboard me-2"></i>Atajos de Teclado</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6 class="text-muted mb-2">Atajos configurados</h6>
                                    <table class="table table-dark table-sm">
                                        <tbody>${configRows}</tbody>
                                    </table>
                                    <p class="text-muted small mb-0">
                                        <i class="fas fa-cog me-1"></i>
                                        Configurables desde
                                        <a href="/admin/pos/poskeyboardshortcut/" target="_blank" class="text-info">Admin → Atajos</a>
                                    </p>
                                </div>
                                <div class="col-md-6">
                                    <h6 class="text-muted mb-2">Teclas fijas</h6>
                                    <table class="table table-dark table-sm">
                                        <tbody>
                                            <tr class="table-active"><td colspan="2"><strong>Ciclo de Tab</strong></td></tr>
                                            <tr><td><kbd>Tab</kbd></td><td>Búsqueda → Carrito → COBRAR → (vuelve)</td></tr>
                                            <tr><td><kbd>Shift+Tab</kbd></td><td>Navegar hacia atrás</td></tr>
                                            <tr><td><kbd>Tab</kbd> en búsqueda</td><td>Selecciona primer resultado</td></tr>
                                            <tr class="table-active"><td colspan="2"><strong>Navegación carrito</strong></td></tr>
                                            <tr><td><kbd>↑</kbd> <kbd>↓</kbd></td><td>Mover selección al ítem anterior / siguiente</td></tr>
                                            <tr><td><kbd>+</kbd> <kbd>-</kbd></td><td>Aumentar / disminuir cantidad del ítem seleccionado</td></tr>
                                            <tr><td><kbd>Enter</kbd></td><td>Editar cantidad exacta del ítem seleccionado</td></tr>
                                            <tr><td><kbd>Delete</kbd></td><td>Eliminar ítem seleccionado</td></tr>
                                            <tr><td><kbd>Esc</kbd></td><td>Volver al buscador</td></tr>
                                            <tr><td><kbd>Tab</kbd> (último ítem)</td><td>Ir a COBRAR</td></tr>
                                            <tr class="table-active"><td colspan="2"><strong>General</strong></td></tr>
                                            <tr><td><kbd>Enter</kbd></td><td>Agregar producto / confirmar</td></tr>
                                            <tr><td><kbd>↑</kbd> <kbd>↓</kbd></td><td>Navegar resultados de búsqueda</td></tr>
                                            <tr><td><kbd>+</kbd> <kbd>-</kbd></td><td>Cantidad del ítem enfocado (o último si ninguno)</td></tr>
                                            <tr><td><kbd>Alt+1-9</kbd></td><td>Botones de acceso rápido</td></tr>
                                            <tr><td><kbd>P</kbd> (modal éxito)</td><td>Imprimir ticket</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('shortcutsModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', helpHtml);
        const modal = new bootstrap.Modal(document.getElementById('shortcutsModal'));
        modal.show();
    }

    // Expose formatCurrency and showToast for pos-sidebar.js
    window.POS_formatCurrency = (v) => formatCurrency(v);
    window.POS_showToast = (msg, type) => showToast(msg, type);
    window.POS_cart = () => cart;
    window.POS_loadCart = loadCart;

    // Utility functions
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function formatCurrency(value) {
        if (value === null || value === undefined) return '$0,00';
        const number = parseFloat(value);
        if (isNaN(number)) return '$0,00';
        
        // Argentine format: $1.234,56
        const parts = number.toFixed(2).split('.');
        const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        const decPart = parts[1];
        
        return '$' + intPart + ',' + decPart;
    }

    function showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';
        
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
                <div class="toast-body d-flex justify-content-between align-items-center">
                    <span>${message}</span>
                    <button type="button" class="btn-close btn-close-white ms-2" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
        toast.show();
        
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

})();
