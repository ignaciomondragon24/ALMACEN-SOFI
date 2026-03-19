/**
 * SIGNAGE RENDERER v4 — Renders sign cards in preview, print and designer.
 * Usage: SignageRenderer.renderSign(element, layoutObj, typeString)
 */
var SignageRenderer = (function () {
    'use strict';

    /* ── Price formatter (Argentine $1.234,56) ───────────────── */
    function formatPrice(val) {
        if (val === '' || val === null || val === undefined) return '';
        var n = parseFloat(String(val).replace(',', '.'));
        if (isNaN(n)) return '';
        var parts = n.toFixed(2).split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        var cents = parts[1];
        return '$' + parts[0] + (cents !== '00' ? ',' + cents : '');
    }

    function mk(tag, cls, text) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text !== undefined && text !== null) e.textContent = text;
        return e;
    }

    /* ── Main entry ──────────────────────────────────────────── */
    function renderSign(el, layout, type) {
        var d = el.dataset;
        var L = (layout && typeof layout === 'object') ? layout : {};

        // Clear previous content
        el.innerHTML = '';

        // Outer card styles
        el.style.background = L.background_color || '#fff';
        el.style.border = (L.border_width || 2) + 'px solid ' + (L.border_color || '#000');
        el.style.borderRadius = (L.border_radius || 0) + 'px';
        el.style.fontFamily = L.font_family || 'Arial, sans-serif';
        el.style.overflow = 'hidden';
        el.style.display = 'flex';
        el.style.flexDirection = 'column';
        el.style.position = 'relative';
        el.style.boxSizing = 'border-box';

        // Inner container
        var inner = mk('div', 'sign-inner');
        inner.style.cssText =
            'flex:1;min-height:0;width:100%;box-sizing:border-box;' +
            'padding:' + (L.padding || 3) + 'mm;' +
            'display:flex;flex-direction:column;justify-content:center;align-items:center;' +
            'text-align:center;overflow:hidden;position:relative;z-index:1;';

        // Dispatch to type renderer
        if (type === 'simple') _simple(inner, d, L);
        else if (type === 'promotional') _promo(inner, d, L);
        else if (type === 'bulk') _bulk(inner, d, L);
        else if (type === 'weight') _weight(inner, d, L);
        else _simple(inner, d, L);

        el.appendChild(inner);

        // Theme decorations
        _decorate(el, L);
    }

    /* ── SIMPLE ──────────────────────────────────────────────── */
    function _simple(inner, d, L) {
        if (L.show_store_name) {
            var sh = mk('div', 'store-header', L.store_name || 'CHE GOLOSO');
            sh.style.cssText =
                'width:100%;padding:1mm 2mm;text-align:center;font-weight:700;' +
                'letter-spacing:1px;text-transform:uppercase;margin-bottom:1mm;' +
                'font-size:' + (L.store_name_size || 8) + 'px;' +
                'background:' + (L.store_name_bg || '#333') + ';' +
                'color:' + (L.store_name_color || '#fff') + ';border-radius:2px;';
            inner.appendChild(sh);
        }

        var name = mk('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 14) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        if (L.gramaje_show !== false && d.gramaje) {
            var gr = mk('div', 'gramaje', d.gramaje);
            gr.style.cssText =
                'width:100%;font-size:' + (L.gramaje_size || 9) + 'px;' +
                'color:' + (L.gramaje_color || '#666') + ';margin:0.5mm 0;';
            inner.appendChild(gr);
        }

        var price = mk('div', 'price fit-text', formatPrice(d.price));
        price.style.cssText =
            'width:100%;line-height:1;' +
            'font-size:' + (L.price_size || 32) + 'px;' +
            'font-weight:' + (L.price_weight || 'bold') + ';' +
            'color:' + (L.price_color || '#27ae60') + ';';
        inner.appendChild(price);
    }

    /* ── PROMOTIONAL ─────────────────────────────────────────── */
    function _promo(inner, d, L) {
        if (L.promo_label_show !== false) {
            var lbl = mk('div', 'promo-label', L.promo_label_text || 'PROMO!!');
            lbl.style.cssText =
                'display:inline-block;padding:1mm 3mm;border-radius:4px;font-weight:800;' +
                'text-transform:uppercase;letter-spacing:1px;margin-bottom:1mm;' +
                'font-size:' + (L.promo_label_size || 12) + 'px;' +
                'background:' + (L.promo_label_bg || '#FFD700') + ';' +
                'color:' + (L.promo_label_color || '#cc0000') + ';';
            inner.appendChild(lbl);
        }

        var name = mk('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 12) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#fff') + ';';
        inner.appendChild(name);

        if (d.price) {
            var up = mk('div', 'unit-price fit-text', 'c/u ' + formatPrice(d.price));
            up.style.cssText =
                'width:100%;text-decoration:line-through;opacity:.75;' +
                'font-size:' + (L.unit_price_size || 14) + 'px;' +
                'color:' + (L.unit_price_color || '#fff') + ';';
            inner.appendChild(up);
        }

        var qty = d.promoQty || d['promo-qty'] || '';
        if (qty) {
            var badge = mk('div', 'promo-badge fit-text', 'LLEV\u00c1 ' + qty);
            badge.style.cssText =
                'width:100%;font-weight:900;line-height:1;' +
                'font-size:' + (L.promo_badge_size || 24) + 'px;' +
                'color:' + (L.promo_badge_color || '#FFD700') + ';';
            inner.appendChild(badge);
        }

        var pp = d.promoPrice || d['promo-price'] || '';
        if (pp) {
            var pEl = mk('div', 'price fit-text', formatPrice(pp));
            pEl.style.cssText =
                'width:100%;line-height:1;' +
                'font-size:' + (L.promo_price_size || 28) + 'px;' +
                'font-weight:' + (L.promo_price_weight || 'bold') + ';' +
                'color:' + (L.promo_price_color || '#fff') + ';';
            inner.appendChild(pEl);
        }
    }

    /* ── BULK ────────────────────────────────────────────────── */
    function _bulk(inner, d, L) {
        var name = mk('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 16) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        var price = mk('div', 'price fit-text', formatPrice(d.price));
        price.style.cssText =
            'width:100%;line-height:1;' +
            'font-size:' + (L.total_price_size || 28) + 'px;' +
            'font-weight:' + (L.total_price_weight || 'bold') + ';' +
            'color:' + (L.total_price_color || '#e74c3c') + ';';
        inner.appendChild(price);

        var pType = d.packageType || d['package-type'] || '';
        var pQty = d.packageQty || d['package-qty'] || '';
        var parts = [];
        if (pType) parts.push(pType.toUpperCase());
        if (pQty) parts.push('\u00d7 ' + pQty);
        if (parts.length) {
            var pkg = mk('div', 'package-info fit-text', parts.join(' '));
            pkg.style.cssText =
                'width:100%;text-transform:uppercase;margin-top:0.5mm;' +
                'font-size:' + (L.package_info_size || 12) + 'px;' +
                'font-weight:' + (L.package_info_weight || 'bold') + ';' +
                'color:' + (L.package_info_color || '#2c3e50') + ';';
            inner.appendChild(pkg);
        }
    }

    /* ── WEIGHT ──────────────────────────────────────────────── */
    function _weight(inner, d, L) {
        var name = mk('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 14) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        if (L.show_dividers !== false) {
            var dv = mk('div', 'divider');
            dv.style.cssText =
                'width:80%;height:0;border-top:1px solid ' +
                (L.divider_color || '#ccc') + ';margin:1mm auto;';
            inner.appendChild(dv);
        }

        var row = mk('div', 'weight-row');
        row.style.cssText =
            'width:100%;display:flex;justify-content:space-around;' +
            'align-items:baseline;gap:1mm;padding:0 1mm;';

        // Read from both camelCase and kebab-case (HTML dataset converts kebab to camelCase)
        var p100 = d.price100g || d['price-100g'] || '';
        var p250 = d.price250g || d['price-250g'] || '';
        var p1kg = d.price1kg || d['price-1kg'] || '';

        var tiers = [
            {val: p100, lbl: '100g', sz: L.price_100g_size || 12, cl: L.price_100g_color || '#000', wt: 'normal'},
            {val: p250, lbl: '\u00bcKg', sz: L.price_250g_size || 14, cl: L.price_250g_color || '#000', wt: 'normal'},
            {val: p1kg, lbl: '1Kg', sz: L.price_1kg_size || 20, cl: L.price_1kg_color || '#e74c3c', wt: L.price_1kg_weight || 'bold'},
        ];

        tiers.forEach(function (t) {
            if (!t.val) return;
            var cell = mk('div', 'weight-cell');
            cell.style.cssText = 'text-align:center;flex:1;';
            var lb = mk('span', 'weight-label', t.lbl);
            lb.style.cssText = 'display:block;font-size:60%;opacity:.7;text-transform:uppercase;';
            var pr = mk('span', 'fit-text', formatPrice(t.val));
            pr.style.cssText =
                'display:block;font-size:' + t.sz + 'px;' +
                'color:' + t.cl + ';font-weight:' + t.wt + ';';
            cell.appendChild(lb);
            cell.appendChild(pr);
            row.appendChild(cell);
        });

        inner.appendChild(row);
    }

    /* ── Theme Decorations ───────────────────────────────────── */
    var THEME_COLORS = {
        navidad: '#c41e3a', pascua: '#9b59b6', san_valentin: '#e91e8c',
        dia_madre: '#c2185b', halloween: '#ff6600', anio_nuevo: '#FFD700',
        patrio: '#74acdf',
    };

    function _decorate(el, L) {
        if (L.theme && L.theme !== 'none' && THEME_COLORS[L.theme]) {
            var stripe = document.createElement('div');
            stripe.style.cssText =
                'position:absolute;top:0;left:0;right:0;height:1.5mm;' +
                'background:' + THEME_COLORS[L.theme] + ';z-index:3;pointer-events:none;';
            el.appendChild(stripe);
        }
        if (L.bg_watermark_show && L.bg_watermark) {
            var wm = mk('div', 'sign-watermark', L.bg_watermark);
            wm.style.cssText =
                'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
                'font-size:3em;opacity:.08;pointer-events:none;z-index:0;user-select:none;';
            el.appendChild(wm);
        }
        var POS = {tl: 'top:1mm;left:1mm', tr: 'top:1mm;right:1mm', bl: 'bottom:1mm;left:1mm', br: 'bottom:1mm;right:1mm'};
        ['tl', 'tr', 'bl', 'br'].forEach(function (p) {
            var ico = L['corner_' + p];
            if (!ico) return;
            var sp = mk('span', 'sign-corner-icon', ico);
            sp.style.cssText =
                'position:absolute;font-size:1em;line-height:1;pointer-events:none;z-index:4;' + POS[p] + ';';
            el.appendChild(sp);
        });
    }

    /* ── Auto-fit text ───────────────────────────────────────── */
    function autoFitAll() {
        document.querySelectorAll('.sign-card .fit-text, .sign-preview .fit-text').forEach(function (el) {
            _fitOne(el);
        });
    }

    function _fitOne(el) {
        var ref = el.closest('.sign-inner') || el.parentElement;
        if (!ref) return;
        var maxW = ref.clientWidth - 4;
        if (maxW <= 0) return;
        var fs = parseFloat(window.getComputedStyle(el).fontSize);
        if (isNaN(fs)) return;
        var i = 0;
        while (el.scrollWidth > maxW && fs > 6 && i < 80) {
            fs -= 0.5;
            el.style.fontSize = fs + 'px';
            i++;
        }
    }

    return {
        renderSign: renderSign,
        autoFitAll: autoFitAll,
        formatPrice: formatPrice,
    };
})();
