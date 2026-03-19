/**
 * SIGNAGE GENERATOR - Sign batch creation logic.
 * Handles template selection, product adding, form-specific fields, and batch submission.
 */
(function () {
    'use strict';

    var CFG = window.SIGNAGE_GENERATOR;
    var selectedTemplatePk = CFG.selectedTemplatePk;
    var selectedType = CFG.selectedTemplateType || '';
    var signItems = []; // Array of item data objects
    var nextId = 1;

    document.addEventListener('DOMContentLoaded', function () {
        bindTemplateSelection();
        bindProductSearch();
        bindProductCards();
        bindGenerate();
        bindPaperSize();

        // If template pre-selected, enable step 2
        if (selectedTemplatePk) {
            enableStep2();
        }
    });

    // ========== Template Selection ==========
    function bindTemplateSelection() {
        document.querySelectorAll('.template-card').forEach(function (card) {
            card.addEventListener('click', function () {
                document.querySelectorAll('.template-card').forEach(function (c) { c.classList.remove('selected'); });
                card.classList.add('selected');
                selectedTemplatePk = card.dataset.pk;
                selectedType = card.dataset.type;
                document.getElementById('formTemplatePk').value = selectedTemplatePk;
                enableStep2();
                // Clear items when switching templates (different type = different fields)
                signItems = [];
                renderSignItems();
            });
        });
    }

    function enableStep2() {
        var step = document.getElementById('stepProducts');
        step.style.opacity = '1';
        step.style.pointerEvents = 'auto';
    }

    // ========== Product Search ==========
    function bindProductSearch() {
        var searchInput = document.getElementById('productSearch');
        var catFilter = document.getElementById('categoryFilter');

        searchInput.addEventListener('input', filterProducts);
        catFilter.addEventListener('change', filterProducts);
    }

    function filterProducts() {
        var query = document.getElementById('productSearch').value.toLowerCase();
        var cat = document.getElementById('categoryFilter').value;

        document.querySelectorAll('.product-item').forEach(function (item) {
            var nameMatch = item.dataset.name.indexOf(query) !== -1;
            var catMatch = !cat || item.dataset.cat === cat;
            item.style.display = (nameMatch && catMatch) ? '' : 'none';
        });
    }

    // ========== Product Card Click ==========
    function bindProductCards() {
        document.querySelectorAll('.product-search-card').forEach(function (card) {
            card.addEventListener('click', function () {
                addSignItem({
                    product_id: card.dataset.pk,
                    product_name: card.dataset.name,
                    product_price: card.dataset.price,
                });
                card.classList.add('added');
                setTimeout(function () { card.classList.remove('added'); }, 600);
            });
        });
    }

    // ========== Sign Items Management ==========
    function addSignItem(productData) {
        var item = {
            id: nextId++,
            product_id: productData.product_id || '',
            custom_name: '',
            custom_price: '',
            product_name: productData.product_name || '',
            product_price: productData.product_price || '',
            gramaje: '',
            promo_quantity: '',
            promo_price: '',
            package_type: '',
            quantity_per_package: '',
            price_100g: '',
            price_250g: '',
            price_1kg: '',
            copies: 1,
        };
        signItems.push(item);
        renderSignItems();
        document.getElementById('stepConfigure').style.display = '';
    }

    function removeSignItem(id) {
        signItems = signItems.filter(function (i) { return i.id !== id; });
        renderSignItems();
        if (signItems.length === 0) {
            document.getElementById('stepConfigure').style.display = 'none';
        }
    }

    function renderSignItems() {
        var container = document.getElementById('signItemsList');
        container.innerHTML = '';

        signItems.forEach(function (item) {
            var card = document.createElement('div');
            card.className = 'sign-item-card card mb-2';
            card.innerHTML = buildItemHTML(item);
            container.appendChild(card);

            // Bind remove
            card.querySelector('.btn-remove-item').addEventListener('click', function () {
                removeSignItem(item.id);
            });

            // Bind field changes
            card.querySelectorAll('[data-field]').forEach(function (input) {
                input.addEventListener('input', function () {
                    item[input.dataset.field] = input.value;
                    updateTotals();
                });
            });
        });

        updateTotals();
    }

    function buildItemHTML(item) {
        var name = item.custom_name || item.product_name || 'Producto';
        var price = item.custom_price || item.product_price || '';

        var html = '<div class="card-body p-3">';
        html += '<div class="d-flex justify-content-between align-items-start mb-2">';
        html += '<div><strong>' + escapeHtml(name) + '</strong>';
        if (price) html += ' <span class="text-success">$' + price + '</span>';
        html += '</div>';
        html += '<button type="button" class="btn btn-sm btn-outline-danger btn-remove-item"><i class="fas fa-times"></i></button>';
        html += '</div>';

        // Row of common fields
        html += '<div class="row g-2">';

        // Custom name override
        html += '<div class="col-md-3"><label class="form-label small mb-0">Nombre (override)</label>';
        html += '<input type="text" class="form-control form-control-sm" data-field="custom_name" value="' + escapeAttr(item.custom_name) + '" placeholder="' + escapeAttr(item.product_name) + '"></div>';

        // Custom price override
        html += '<div class="col-md-2"><label class="form-label small mb-0">Precio (override)</label>';
        html += '<input type="number" class="form-control form-control-sm" data-field="custom_price" value="' + escapeAttr(item.custom_price) + '" placeholder="' + escapeAttr(item.product_price) + '" step="0.01"></div>';

        // Copies
        html += '<div class="col-md-1"><label class="form-label small mb-0">Copias</label>';
        html += '<input type="number" class="form-control form-control-sm" data-field="copies" value="' + item.copies + '" min="1" max="100"></div>';

        // Type-specific fields
        if (selectedType === 'simple') {
            html += '<div class="col-md-2"><label class="form-label small mb-0">Gramaje</label>';
            html += '<input type="text" class="form-control form-control-sm" data-field="gramaje" value="' + escapeAttr(item.gramaje) + '" placeholder="ej: 100g"></div>';
        } else if (selectedType === 'promotional') {
            html += '<div class="col-md-1"><label class="form-label small mb-0">Cant. Promo</label>';
            html += '<input type="number" class="form-control form-control-sm" data-field="promo_quantity" value="' + escapeAttr(item.promo_quantity) + '" placeholder="3" min="1"></div>';
            html += '<div class="col-md-2"><label class="form-label small mb-0">Precio Promo</label>';
            html += '<input type="number" class="form-control form-control-sm" data-field="promo_price" value="' + escapeAttr(item.promo_price) + '" placeholder="$500" step="0.01"></div>';
        } else if (selectedType === 'bulk') {
            html += '<div class="col-md-2"><label class="form-label small mb-0">Tipo Empaque</label>';
            html += '<select class="form-select form-select-sm" data-field="package_type">';
            html += '<option value="">-</option>';
            ['caja', 'bolsa', 'pack', 'display'].forEach(function (t) {
                html += '<option value="' + t + '"' + (item.package_type === t ? ' selected' : '') + '>' + t.charAt(0).toUpperCase() + t.slice(1) + '</option>';
            });
            html += '</select></div>';
            html += '<div class="col-md-2"><label class="form-label small mb-0">Contenido</label>';
            html += '<input type="text" class="form-control form-control-sm" data-field="quantity_per_package" value="' + escapeAttr(item.quantity_per_package) + '" placeholder="30U, 1kg"></div>';
        } else if (selectedType === 'weight') {
            html += '<div class="col-md-2"><label class="form-label small mb-0">Precio 100g</label>';
            html += '<input type="number" class="form-control form-control-sm" data-field="price_100g" value="' + escapeAttr(item.price_100g) + '" step="0.01"></div>';
            html += '<div class="col-md-2"><label class="form-label small mb-0">Precio ¼kg</label>';
            html += '<input type="number" class="form-control form-control-sm" data-field="price_250g" value="' + escapeAttr(item.price_250g) + '" step="0.01"></div>';
            html += '<div class="col-md-2"><label class="form-label small mb-0">Precio 1kg</label>';
            html += '<input type="number" class="form-control form-control-sm" data-field="price_1kg" value="' + escapeAttr(item.price_1kg) + '" step="0.01"></div>';
        }

        html += '</div></div>';
        return html;
    }

    function updateTotals() {
        var total = 0;
        signItems.forEach(function (item) {
            total += Math.max(1, parseInt(item.copies) || 1);
        });
        document.getElementById('signCount').textContent = signItems.length;
        document.getElementById('totalSignsInfo').textContent = total + ' cartel' + (total !== 1 ? 'es' : '') + ' en total';
        document.getElementById('btnGenerate').disabled = signItems.length === 0 || !selectedTemplatePk;
    }

    // ========== Generation / Submit ==========
    function bindGenerate() {
        document.getElementById('btnGenerate').addEventListener('click', function () {
            var items = signItems.map(function (item) {
                return {
                    product_id: item.product_id || null,
                    custom_name: item.custom_name,
                    custom_price: item.custom_price || null,
                    gramaje: item.gramaje,
                    promo_quantity: item.promo_quantity || null,
                    promo_price: item.promo_price || null,
                    package_type: item.package_type,
                    quantity_per_package: item.quantity_per_package,
                    price_100g: item.price_100g || null,
                    price_250g: item.price_250g || null,
                    price_1kg: item.price_1kg || null,
                    copies: Math.max(1, parseInt(item.copies) || 1),
                };
            });

            document.getElementById('formTemplatePk').value = selectedTemplatePk;
            document.getElementById('formPaperSize').value = document.getElementById('paperSize').value;
            document.getElementById('formItemsJson').value = JSON.stringify(items);
            document.getElementById('batchForm').submit();
        });
    }

    function bindPaperSize() {
        document.getElementById('paperSize').addEventListener('change', function () {
            document.getElementById('formPaperSize').value = this.value;
        });
    }

    // ========== Utilities ==========
    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return String(str || '').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

})();
