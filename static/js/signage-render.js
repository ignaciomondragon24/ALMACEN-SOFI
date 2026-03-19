/**
 * SIGNAGE RENDERER v3 — Authoritative renderer for all sign pages.
 * Used by: preview_batch.html, print_layout.html, designer preview.
 */
var SignageRenderer = (function () {
    'use strict';

    var THEME_COLORS = {
        navidad:      '#c41e3a',
        pascua:       '#9b59b6',
        san_valentin: '#e91e8c',
        dia_madre:    '#c2185b',
        halloween:    '#ff6600',
        anio_nuevo:   '#FFD700',
        patrio:       '#74acdf',
    };

    /* ── Price formatter (Argentine format) ──────────────────── */
    function formatPrice(val) {
        if (val === '' || val == null) return '';
        var n = parseFloat(String(val).replace(',', '.'));
        if (isNaN(n)) return '';
        var parts = n.toFixed(2).split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        return '$' + parts[0] + (parts[1] !== '00' ? ',' + parts[1] : '');
    }

    function mkEl(tag, cls, text) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text) e.textContent = text;
        return e;
    }

    /* ── Main entry point ────────────────────────────────────── */
    function renderSign(el, layout, type) {
        var d = el.dataset;
        var L = (layout && typeof layout === 'object') ? layout : {};

        // Outer card
        el.style.background    = L.background_color || '#fff';
        el.style.border        = (L.border_width || 2) + 'px solid ' + (L.border_color || '#000');
        el.style.borderRadius  = (L.border_radius || 0) + 'px';
        el.style.fontFamily    = L.font_family || 'Arial, sans-serif';
        el.style.overflow      = 'hidden';
        el.style.display       = 'flex';
        el.style.flexDirection = 'column';
        el.style.position      = 'relative';
        el.style.boxSizing     = 'border-box';

        // Inner content — flex:1 fills the card
        var inner = mkEl('div', 'sign-inner');
        inner.style.cssText =
            'flex:1;min-height:0;width:100%;box-sizing:border-box;' +
            'padding:' + (L.padding || 3) + 'mm;' +
            'display:flex;flex-direction:column;justify-content:center;align-items:center;' +
            'text-align:' + (L.text_align || 'center') + ';overflow:hidden;position:relative;z-index:1;';

        if (type === 'simple')           _renderSimple(inner, d, L);
        else if (type === 'promotional') _renderPromo(inner, d, L);
        else if (type === 'bulk')        _renderBulk(inner, d, L);
        else if (type === 'weight')      _renderWeight(inner, d, L);
        else                             _renderSimple(inner, d, L);

        el.innerHTML = '';
        el.appendChild(inner);

        // Decorations
        _decorate(el, L);
    }

    /* ── SIMPLE ──────────────────────────────────────────────── */
    function _renderSimple(inner, d, L) {
        if (L.show_store_name) {
            var sh = mkEl('div', 'store-header', L.store_name || 'CHE GOLOSO');
            sh.style.cssText = 'width:100%;padding:1mm 2mm;text-align:center;font-weight:700;' +
                'letter-spacing:1px;text-transform:uppercase;' +
                'font-size:' + (L.store_name_size || 8) + 'px;' +
                'background:' + (L.store_name_bg || '#333') + ';color:' + (L.store_name_color || '#fff') + ';' +
                'border-radius:2px;margin-bottom:1mm;';
            inner.appendChild(sh);
        }

        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText = 'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 14) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        if (L.gramaje_show !== false && d.gramaje) {
            var gr = mkEl('div', 'gramaje', d.gramaje);
            gr.style.cssText = 'width:100%;font-size:' + (L.gramaje_size || 9) + 'px;color:' + (L.gramaje_color || '#666') + ';margin:0.5mm 0;';
            inner.appendChild(gr);
        }

        var price = mkEl('div', 'price fit-text', formatPrice(d.price));
        price.style.cssText = 'width:100%;line-height:1;' +
            'font-size:' + (L.price_size || 32) + 'px;' +
            'font-weight:' + (L.price_weight || 'bold') + ';' +
            'color:' + (L.price_color || '#27ae60') + ';';
        inner.appendChild(price);
    }

    /* ── PROMOTIONAL ─────────────────────────────────────────── */
    function _renderPromo(inner, d, L) {
        if (L.promo_label_show !== false) {
            var lbl = mkEl('div', 'promo-label', L.promo_label_text || 'PROMO!!');
            lbl.style.cssText = 'display:inline-block;padding:1mm 3mm;border-radius:4px;font-weight:800;' +
                'text-transform:uppercase;letter-spacing:1px;margin-bottom:1mm;' +
                'font-size:' + (L.promo_label_size || 12) + 'px;' +
                'background:' + (L.promo_label_bg || '#FFD700') + ';color:' + (L.promo_label_color || '#cc0000') + ';';
            inner.appendChild(lbl);
        }

        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText = 'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 12) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#fff') + ';';
        inner.appendChild(name);

        var up = mkEl('div', 'unit-price fit-text', 'c/u ' + formatPrice(d.price));
        up.style.cssText = 'width:100%;text-decoration:line-through;opacity:.75;' +
            'font-size:' + (L.unit_price_size || 14) + 'px;' +
            'color:' + (L.unit_price_color || '#fff') + ';';
        inner.appendChild(up);

        if (d.promoQty) {
            var badge = mkEl('div', 'promo-badge fit-text', 'LLEV\u00c1 ' + d.promoQty);
            badge.style.cssText = 'width:100%;font-weight:900;line-height:1;' +
                'font-size:' + (L.promo_badge_size || 24) + 'px;' +
                'color:' + (L.promo_badge_color || '#FFD700') + ';';
            inner.appendChild(badge);
        }

        if (d.promoPrice) {
            var pp = mkEl('div', 'price fit-text', formatPrice(d.promoPrice));
            pp.style.cssText = 'width:100%;line-height:1;' +
                'font-size:' + (L.promo_price_size || 28) + 'px;' +
                'font-weight:' + (L.promo_price_weight || 'bold') + ';' +
                'color:' + (L.promo_price_color || '#fff') + ';';
            inner.appendChild(pp);
        }
    }

    /* ── BULK ────────────────────────────────────────────────── */
    function _renderBulk(inner, d, L) {
        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText = 'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 16) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        var price = mkEl('div', 'price fit-text', formatPrice(d.price));
        price.style.cssText = 'width:100%;line-height:1;' +
            'font-size:' + (L.total_price_size || 28) + 'px;' +
            'font-weight:' + (L.total_price_weight || 'bold') + ';' +
            'color:' + (L.total_price_color || '#e74c3c') + ';';
        inner.appendChild(price);

        var parts = [];
        if (d.packageType) parts.push(d.packageType.toUpperCase());
        if (d.packageQty)  parts.push('\u00d7 ' + d.packageQty);
        if (parts.length) {
            var pkg = mkEl('div', 'package-info fit-text', parts.join(' '));
            pkg.style.cssText = 'width:100%;text-transform:uppercase;margin-top:0.5mm;' +
                'font-size:' + (L.package_info_size || 12) + 'px;' +
                'font-weight:' + (L.package_info_weight || 'bold') + ';' +
                'color:' + (L.package_info_color || '#2c3e50') + ';';
            inner.appendChild(pkg);
        }
    }

    /* ── WEIGHT ──────────────────────────────────────────────── */
    function _renderWeight(inner, d, L) {
        var name = mkEl('div', 'product-name fit-text-multi', d.name || 'PRODUCTO');
        name.style.cssText = 'width:100%;padding:0 1mm;text-transform:uppercase;line-height:1.15;' +
            'font-size:' + (L.product_name_size || 14) + 'px;' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';';
        inner.appendChild(name);

        if (L.show_dividers !== false) {
            var dv = document.createElement('div');
            dv.className = 'divider';
            dv.style.cssText = 'width:80%;height:0;border-top:1px solid ' + (L.divider_color || '#ccc') + ';margin:1mm auto;';
            inner.appendChild(dv);
        }

        var row = mkEl('div', 'weight-row');
        row.style.cssText = 'width:100%;display:flex;justify-content:space-around;align-items:baseline;gap:1mm;padding:0 1mm;';

        var tiers = [
            { val: d.price100g, lbl: '100g',  sz: L.price_100g_size || 12, cl: L.price_100g_color || '#000', wt: 'normal' },
            { val: d.price250g, lbl: '\u00bc Kg', sz: L.price_250g_size || 14, cl: L.price_250g_color || '#000', wt: 'normal' },
            { val: d.price1kg,  lbl: '1 Kg',  sz: L.price_1kg_size  || 20, cl: L.price_1kg_color  || '#e74c3c', wt: L.price_1kg_weight || 'bold' },
        ];

        tiers.forEach(function (t) {
            if (!t.val) return;
            var cell = mkEl('div', 'weight-cell');
            cell.style.cssText = 'text-align:center;flex:1;';
            var lb = mkEl('span', 'weight-label', t.lbl);
            lb.style.cssText = 'display:block;font-size:60%;opacity:.7;text-transform:uppercase;';
            var pr = mkEl('span', 'fit-text', formatPrice(t.val));
            pr.style.cssText = 'display:block;font-size:' + t.sz + 'px;color:' + t.cl + ';font-weight:' + t.wt + ';';
            cell.appendChild(lb);
            cell.appendChild(pr);
            row.appendChild(cell);
        });

        inner.appendChild(row);
    }

    /* ── Decorations ─────────────────────────────────────────── */
    function _decorate(el, L) {
        // Theme accent stripe
        if (L.theme && L.theme !== 'none' && THEME_COLORS[L.theme]) {
            var stripe = document.createElement('div');
            stripe.style.cssText = 'position:absolute;top:0;left:0;right:0;height:1.5mm;' +
                'background:' + THEME_COLORS[L.theme] + ';z-index:3;pointer-events:none;';
            el.appendChild(stripe);
        }

        // Watermark
        if (L.bg_watermark_show && L.bg_watermark) {
            var wm = mkEl('div', 'sign-watermark', L.bg_watermark);
            wm.setAttribute('aria-hidden', 'true');
            el.appendChild(wm);
        }

        // Corner icons
        var POSITIONS = {
            tl: 'top:1mm;left:1mm',
            tr: 'top:1mm;right:1mm',
            bl: 'bottom:1mm;left:1mm',
            br: 'bottom:1mm;right:1mm',
        };
        ['tl', 'tr', 'bl', 'br'].forEach(function (pos) {
            var ico = L['corner_' + pos];
            if (!ico) return;
            var sp = mkEl('span', 'sign-corner-icon sign-corner-' + pos, ico);
            sp.setAttribute('aria-hidden', 'true');
            sp.style.cssText = 'position:absolute;font-size:1em;line-height:1;pointer-events:none;z-index:4;' + POSITIONS[pos] + ';';
            el.appendChild(sp);
        });
    }

    /* ── Auto-fit text ───────────────────────────────────────── */
    function autoFitAll() {
        document.querySelectorAll('.sign-card .fit-text, .sign-preview .fit-text').forEach(autoFitElement);
    }

    function autoFitElement(el) {
        var ref = el.closest('.sign-inner') || el.closest('.sign-card') || el.closest('.sign-preview') || el.parentElement;
        if (!ref) return;
        var maxW = ref.clientWidth - 4;
        if (maxW <= 0) return;
        var fs = parseFloat(window.getComputedStyle(el).fontSize);
        if (isNaN(fs)) return;
        var minSize = 6;
        var i = 0;
        while (el.scrollWidth > maxW && fs > minSize && i < 80) {
            fs -= 0.5;
            el.style.fontSize = fs + 'px';
            i++;
        }
    }

    return {
        renderSign: renderSign,
        autoFitAll: autoFitAll,
        autoFitElement: autoFitElement,
        formatPrice: formatPrice,
    };
})();
