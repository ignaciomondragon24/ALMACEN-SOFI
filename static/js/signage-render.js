/**
 * SIGNAGE RENDERER v2 - Fixed flex layout + seasonal theme decorations.
 * Used by preview_batch.html and print_layout.html.
 */
var SignageRenderer = (function () {
    'use strict';

    var THEME_COLORS = {
        navidad:     '#c41e3a',
        pascua:      '#9b59b6',
        san_valentin:'#e91e8c',
        dia_madre:   '#c2185b',
        halloween:   '#ff6600',
        año_nuevo:   '#FFD700',
        patrio:      '#74acdf',
    };

    function formatPrice(val) {
        if (val === '' || val === null || val === undefined) return '';
        var n = parseFloat(String(val).replace(',', '.'));
        if (isNaN(n)) return '';
        var parts = n.toFixed(2).split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        return '$' + parts[0] + (parts[1] !== '00' ? ',' + parts[1] : '');
    }

    function renderSign(el, layout, type) {
        var d = el.dataset;
        var L = layout || {};

        // Outer card — visual frame only (no padding)
        el.style.background = L.background_color || '#fff';
        el.style.border = (L.border_width || 0) + 'px solid ' + (L.border_color || '#000');
        el.style.borderRadius = (L.border_radius || 0) + 'px';
        el.style.fontFamily = L.font_family || 'Arial, sans-serif';
        el.style.overflow = 'hidden';
        el.style.display = 'flex';
        el.style.flexDirection = 'column';
        el.style.position = 'relative';

        // Inner content div — fills the card using flex (FIX: was height:100%)
        var inner = document.createElement('div');
        inner.className = 'sign-inner';
        inner.style.flex = '1';
        inner.style.minHeight = '0';
        inner.style.padding = (L.padding || 3) + 'mm';
        inner.style.boxSizing = 'border-box';
        inner.style.width = '100%';
        inner.style.display = 'flex';
        inner.style.flexDirection = 'column';
        inner.style.justifyContent = 'center';
        inner.style.alignItems = 'center';
        inner.style.textAlign = L.text_align || 'center';
        inner.style.overflow = 'hidden';
        inner.style.position = 'relative';
        inner.style.zIndex = '1';

        if (type === 'simple')           renderSimple(inner, d, L);
        else if (type === 'promotional') renderPromotional(inner, d, L);
        else if (type === 'bulk')        renderBulk(inner, d, L);
        else if (type === 'weight')      renderWeight(inner, d, L);

        el.innerHTML = '';
        el.appendChild(inner);

        // Theme accent stripe
        if (L.theme && L.theme !== 'none' && THEME_COLORS[L.theme]) {
            var stripe = document.createElement('div');
            stripe.style.cssText = 'position:absolute;top:0;left:0;right:0;height:1.5mm;' +
                'background:' + THEME_COLORS[L.theme] + ';z-index:3;pointer-events:none;';
            el.appendChild(stripe);
        }

        // Background watermark
        if (L.bg_watermark_show && L.bg_watermark) {
            var wm = document.createElement('div');
            wm.className = 'sign-watermark';
            wm.setAttribute('aria-hidden', 'true');
            wm.textContent = L.bg_watermark;
            el.appendChild(wm);
        }

        // Corner icons
        if (L.corner_tl) _addCorner(el, L.corner_tl, 'tl');
        if (L.corner_tr) _addCorner(el, L.corner_tr, 'tr');
        if (L.corner_bl) _addCorner(el, L.corner_bl, 'bl');
        if (L.corner_br) _addCorner(el, L.corner_br, 'br');
    }

    function _addCorner(el, icon, pos) {
        var span = document.createElement('span');
        span.className = 'sign-corner-icon sign-corner-' + pos;
        span.setAttribute('aria-hidden', 'true');
        span.textContent = icon;
        el.appendChild(span);
    }

    function renderSimple(inner, d, L) {
        if (L.show_store_name) {
            var sh = mkEl('div', 'store-header', L.store_name || 'CHE GOLOSO');
            sh.style.backgroundColor = L.store_name_bg || '#333';
            sh.style.color = L.store_name_color || '#fff';
            sh.style.fontSize = (L.store_name_size || 8) + 'px';
            inner.appendChild(sh);
        }

        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.fontSize = (L.product_name_size || 14) + 'px';
        name.style.fontWeight = L.product_name_weight || 'bold';
        name.style.color = L.product_name_color || '#000';
        inner.appendChild(name);

        if (L.gramaje_show !== false && d.gramaje) {
            var gr = mkEl('div', 'gramaje', d.gramaje);
            gr.style.fontSize = (L.gramaje_size || 9) + 'px';
            gr.style.color = L.gramaje_color || '#666';
            inner.appendChild(gr);
        }

        var price = mkEl('div', 'price fit-text', formatPrice(d.price));
        price.style.fontSize = (L.price_size || 32) + 'px';
        price.style.fontWeight = L.price_weight || 'bold';
        price.style.color = L.price_color || '#27ae60';
        inner.appendChild(price);
    }

    function renderPromotional(inner, d, L) {
        if (L.promo_label_show !== false) {
            var label = mkEl('div', 'promo-label', L.promo_label_text || 'PROMO!!');
            label.style.backgroundColor = L.promo_label_bg || '#FFD700';
            label.style.color = L.promo_label_color || '#cc0000';
            label.style.fontSize = (L.promo_label_size || 12) + 'px';
            inner.appendChild(label);
        }

        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.fontSize = (L.product_name_size || 12) + 'px';
        name.style.fontWeight = L.product_name_weight || 'bold';
        name.style.color = L.product_name_color || '#fff';
        inner.appendChild(name);

        var up = mkEl('div', 'unit-price', formatPrice(d.price));
        up.style.fontSize = (L.unit_price_size || 14) + 'px';
        up.style.color = L.unit_price_color || '#fff';
        inner.appendChild(up);

        if (d.promoQty) {
            var badge = mkEl('div', 'promo-badge fit-text', d.promoQty + ' X');
            badge.style.fontSize = (L.promo_badge_size || 24) + 'px';
            badge.style.color = L.promo_badge_color || '#FFD700';
            inner.appendChild(badge);
        }

        if (d.promoPrice) {
            var pp = mkEl('div', 'price fit-text', formatPrice(d.promoPrice));
            pp.style.fontSize = (L.promo_price_size || 28) + 'px';
            pp.style.fontWeight = L.promo_price_weight || 'bold';
            pp.style.color = L.promo_price_color || '#fff';
            inner.appendChild(pp);
        }
    }

    function renderBulk(inner, d, L) {
        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.fontSize = (L.product_name_size || 16) + 'px';
        name.style.fontWeight = L.product_name_weight || 'bold';
        name.style.color = L.product_name_color || '#000';
        inner.appendChild(name);

        var price = mkEl('div', 'price fit-text', formatPrice(d.price));
        price.style.fontSize = (L.total_price_size || 28) + 'px';
        price.style.fontWeight = L.total_price_weight || 'bold';
        price.style.color = L.total_price_color || '#e74c3c';
        inner.appendChild(price);

        var pkgParts = [];
        if (d.packageType) pkgParts.push(d.packageType.toUpperCase());
        if (d.packageQty)  pkgParts.push('× ' + d.packageQty);
        if (pkgParts.length) {
            var pkg = mkEl('div', 'package-info fit-text', pkgParts.join(' '));
            pkg.style.fontSize = (L.package_info_size || 12) + 'px';
            pkg.style.color = L.package_info_color || '#2c3e50';
            pkg.style.fontWeight = L.package_info_weight || 'bold';
            inner.appendChild(pkg);
        }
    }

    function renderWeight(inner, d, L) {
        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.fontSize = (L.product_name_size || 14) + 'px';
        name.style.fontWeight = L.product_name_weight || 'bold';
        name.style.color = L.product_name_color || '#000';
        inner.appendChild(name);

        if (L.show_dividers !== false) {
            var div1 = document.createElement('div');
            div1.className = 'divider';
            div1.style.borderColor = L.divider_color || '#ccc';
            inner.appendChild(div1);
        }

        var row = document.createElement('div');
        row.className = 'weight-row';

        var prices = [
            { val: d.price100g, label: '100 gr', size: L.price_100g_size || 12, color: L.price_100g_color || '#000', weight: 'normal' },
            { val: d.price250g, label: '¼ Kg', size: L.price_250g_size || 14, color: L.price_250g_color || '#000', weight: 'normal' },
            { val: d.price1kg, label: 'Kg', size: L.price_1kg_size || 20, color: L.price_1kg_color || '#e74c3c', weight: L.price_1kg_weight || 'bold' },
        ];

        prices.forEach(function (p) {
            if (p.val) {
                var cell = document.createElement('div');
                cell.className = 'weight-cell';
                var lbl = mkEl('span', 'weight-label', p.label);
                var prc = mkEl('span', 'fit-text', formatPrice(p.val));
                prc.style.fontSize = p.size + 'px';
                prc.style.color = p.color;
                prc.style.fontWeight = p.weight;
                cell.appendChild(lbl);
                cell.appendChild(prc);
                row.appendChild(cell);
            }
        });

        inner.appendChild(row);
    }

    // Auto-fit: shrink font-size until text fits container width
    function autoFitAll() {
        document.querySelectorAll('.sign-card .fit-text, .sign-preview .fit-text').forEach(autoFitElement);
    }

    function autoFitElement(el) {
        // Use sign-inner as reference since it has the actual padding
        var parent = el.closest('.sign-inner') || el.closest('.sign-card') || el.closest('.sign-preview') || el.parentElement;
        if (!parent) return;
        var maxWidth = parent.clientWidth - 4;
        if (maxWidth <= 0) return;
        var fontSize = parseFloat(window.getComputedStyle(el).fontSize);
        if (isNaN(fontSize)) return;
        var minSize = 5;
        var iterations = 0;
        while (el.scrollWidth > maxWidth && fontSize > minSize && iterations < 80) {
            fontSize -= 0.5;
            el.style.fontSize = fontSize + 'px';
            iterations++;
        }
    }

    function mkEl(tag, cls, text) {
        var e = document.createElement(tag);
        e.className = cls;
        if (text) e.textContent = text;
        return e;
    }

    return {
        renderSign: renderSign,
        autoFitAll: autoFitAll,
        autoFitElement: autoFitElement,
        formatPrice: formatPrice,
    };
})();
