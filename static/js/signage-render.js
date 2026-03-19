/**
 * SIGNAGE RENDERER v5 — Complete rewrite.
 *
 * Renders sign cards for preview, print AND the designer canvas.
 * Every sign element gets font sizes in mm so they scale proportionally
 * when the card is sized in mm (print) or px (designer zoom).
 *
 * Public API:
 *   SignageRenderer.renderSign(el, layout, type, opts)
 *   SignageRenderer.autoFitAll(root)
 *   SignageRenderer.formatPrice(val)
 */
var SignageRenderer = (function () {
    'use strict';

    // ─── Helpers ─────────────────────────────────────────────
    function formatPrice(val) {
        if (val === '' || val === null || val === undefined) return '';
        var n = parseFloat(String(val).replace(',', '.'));
        if (isNaN(n)) return '';
        var parts = n.toFixed(2).split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        var cents = parts[1];
        return '$' + parts[0] + (cents !== '00' ? ',' + cents : '');
    }

    function el(tag, cls, txt) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (txt != null) e.textContent = txt;
        return e;
    }

    /** Read a dataset value from camelCase or kebab-case key */
    function ds(d, key, alt) {
        return d[key] || d[alt] || '';
    }

    // ─── Main Entry ─────────────────────────────────────────
    /**
     * @param {HTMLElement} card   - Container element (must already have width/height set)
     * @param {Object}      layout - Layout config object
     * @param {string}      type   - simple|promotional|bulk|weight
     * @param {Object}      opts   - { unit:'mm'|'px' } — mm for print, px for designer
     */
    function renderSign(card, layout, type, opts) {
        var L = (layout && typeof layout === 'object') ? layout : {};
        var d = card.dataset;
        var u = (opts && opts.unit) || 'mm'; // default mm for print/preview

        card.innerHTML = '';

        // Outer styles
        card.style.background  = L.background_color || '#fff';
        card.style.border      = (L.border_width || 2) + 'px solid ' + (L.border_color || '#000');
        card.style.borderRadius = (L.border_radius || 0) + 'px';
        card.style.fontFamily  = L.font_family || 'Arial, sans-serif';
        card.style.overflow    = 'hidden';
        card.style.display     = 'flex';
        card.style.flexDirection = 'column';
        card.style.position    = 'relative';
        card.style.boxSizing   = 'border-box';

        if (L.text_align) card.style.textAlign = L.text_align;

        // Inner container
        var inner = el('div', 'sign-inner');
        var pad = (L.padding || 3);
        inner.style.cssText =
            'flex:1;min-height:0;width:100%;box-sizing:border-box;' +
            'padding:' + pad + u + ';' +
            'display:flex;flex-direction:column;justify-content:center;align-items:center;' +
            'text-align:' + (L.text_align || 'center') + ';overflow:hidden;position:relative;z-index:1;';

        // Dispatch
        var fn = { simple: _simple, promotional: _promo, bulk: _bulk, weight: _weight }[type] || _simple;
        fn(inner, d, L, u);

        card.appendChild(inner);
        _decorate(card, L, u);
    }

    // ─── SIMPLE ─────────────────────────────────────────────
    function _simple(inner, d, L, u) {
        if (L.show_store_name) {
            var sh = el('div', 'store-header', L.store_name || 'CHE GOLOSO');
            sh.style.cssText =
                'width:100%;padding:0.5' + u + ' 1' + u + ';text-align:center;font-weight:700;' +
                'letter-spacing:0.5px;text-transform:uppercase;margin-bottom:0.5' + u + ';' +
                'font-size:' + sz(L.store_name_size, 8, u) + ';' +
                'background:' + (L.store_name_bg || '#333') + ';' +
                'color:' + (L.store_name_color || '#fff') + ';border-radius:1px;';
            inner.appendChild(sh);
        }

        var name = el('div', 'product-name sign-fit', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 0.5' + u + ';text-transform:uppercase;line-height:1.15;' +
            'font-size:' + sz(L.product_name_size, 14, u) + ';' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';' +
            'overflow:hidden;word-break:break-word;';
        inner.appendChild(name);

        if (L.gramaje_show !== false && d.gramaje) {
            var gr = el('div', 'gramaje', d.gramaje);
            gr.style.cssText =
                'width:100%;font-size:' + sz(L.gramaje_size, 9, u) + ';' +
                'color:' + (L.gramaje_color || '#666') + ';margin:0.3' + u + ' 0;';
            inner.appendChild(gr);
        }

        var price = el('div', 'price sign-fit', formatPrice(d.price));
        price.style.cssText =
            'width:100%;line-height:1;' +
            'font-size:' + sz(L.price_size, 32, u) + ';' +
            'font-weight:' + (L.price_weight || 'bold') + ';' +
            'color:' + (L.price_color || '#27ae60') + ';';
        inner.appendChild(price);
    }

    // ─── PROMOTIONAL ────────────────────────────────────────
    function _promo(inner, d, L, u) {
        if (L.promo_label_show !== false) {
            var lbl = el('div', 'promo-label', L.promo_label_text || 'PROMO!!');
            lbl.style.cssText =
                'display:inline-block;padding:0.5' + u + ' 1.5' + u + ';border-radius:3px;font-weight:800;' +
                'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.5' + u + ';' +
                'font-size:' + sz(L.promo_label_size, 12, u) + ';' +
                'background:' + (L.promo_label_bg || '#FFD700') + ';' +
                'color:' + (L.promo_label_color || '#cc0000') + ';';
            inner.appendChild(lbl);
        }

        var name = el('div', 'product-name sign-fit', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 0.5' + u + ';text-transform:uppercase;line-height:1.15;' +
            'font-size:' + sz(L.product_name_size, 12, u) + ';' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#fff') + ';overflow:hidden;word-break:break-word;';
        inner.appendChild(name);

        if (d.price) {
            var up = el('div', 'unit-price sign-fit', 'c/u ' + formatPrice(d.price));
            up.style.cssText =
                'width:100%;text-decoration:line-through;opacity:.75;' +
                'font-size:' + sz(L.unit_price_size, 14, u) + ';' +
                'color:' + (L.unit_price_color || '#fff') + ';';
            inner.appendChild(up);
        }

        var qty = ds(d, 'promoQty', 'promo-qty');
        if (qty) {
            var badge = el('div', 'promo-badge sign-fit', 'LLEV\u00c1 ' + qty);
            badge.style.cssText =
                'width:100%;font-weight:900;line-height:1;' +
                'font-size:' + sz(L.promo_badge_size, 24, u) + ';' +
                'color:' + (L.promo_badge_color || '#FFD700') + ';';
            inner.appendChild(badge);
        }

        var pp = ds(d, 'promoPrice', 'promo-price');
        if (pp) {
            var pEl = el('div', 'price sign-fit', formatPrice(pp));
            pEl.style.cssText =
                'width:100%;line-height:1;' +
                'font-size:' + sz(L.promo_price_size, 28, u) + ';' +
                'font-weight:' + (L.promo_price_weight || 'bold') + ';' +
                'color:' + (L.promo_price_color || '#fff') + ';';
            inner.appendChild(pEl);
        }
    }

    // ─── BULK ───────────────────────────────────────────────
    function _bulk(inner, d, L, u) {
        var name = el('div', 'product-name sign-fit', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 0.5' + u + ';text-transform:uppercase;line-height:1.15;' +
            'font-size:' + sz(L.product_name_size, 16, u) + ';' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';overflow:hidden;word-break:break-word;';
        inner.appendChild(name);

        var price = el('div', 'price sign-fit', formatPrice(d.price));
        price.style.cssText =
            'width:100%;line-height:1;' +
            'font-size:' + sz(L.total_price_size, 28, u) + ';' +
            'font-weight:' + (L.total_price_weight || 'bold') + ';' +
            'color:' + (L.total_price_color || '#e74c3c') + ';';
        inner.appendChild(price);

        var pt = ds(d, 'packageType', 'package-type');
        var pq = ds(d, 'packageQty', 'package-qty');
        var parts = [];
        if (pt) parts.push(pt.toUpperCase());
        if (pq) parts.push('\u00d7 ' + pq);
        if (parts.length) {
            var pkg = el('div', 'package-info sign-fit', parts.join(' '));
            pkg.style.cssText =
                'width:100%;text-transform:uppercase;margin-top:0.3' + u + ';' +
                'font-size:' + sz(L.package_info_size, 12, u) + ';' +
                'font-weight:' + (L.package_info_weight || 'bold') + ';' +
                'color:' + (L.package_info_color || '#2c3e50') + ';';
            inner.appendChild(pkg);
        }
    }

    // ─── WEIGHT ─────────────────────────────────────────────
    function _weight(inner, d, L, u) {
        var name = el('div', 'product-name sign-fit', d.name || 'PRODUCTO');
        name.style.cssText =
            'width:100%;padding:0 0.5' + u + ';text-transform:uppercase;line-height:1.15;' +
            'font-size:' + sz(L.product_name_size, 14, u) + ';' +
            'font-weight:' + (L.product_name_weight || 'bold') + ';' +
            'color:' + (L.product_name_color || '#000') + ';overflow:hidden;word-break:break-word;';
        inner.appendChild(name);

        if (L.show_dividers !== false) {
            var dv = el('div', 'divider');
            dv.style.cssText =
                'width:80%;height:0;border-top:1px solid ' +
                (L.divider_color || '#ccc') + ';margin:0.5' + u + ' auto;';
            inner.appendChild(dv);
        }

        var row = el('div', 'weight-row');
        row.style.cssText =
            'width:100%;display:flex;justify-content:space-around;' +
            'align-items:baseline;gap:0.5' + u + ';padding:0 0.5' + u + ';';

        var p100 = ds(d, 'price100g', 'price-100g');
        var p250 = ds(d, 'price250g', 'price-250g');
        var p1kg = ds(d, 'price1kg', 'price-1kg');

        var tiers = [
            { val: p100, lbl: '100g', s: L.price_100g_size || 12, c: L.price_100g_color || '#000', w: 'normal' },
            { val: p250, lbl: '\u00bcKg', s: L.price_250g_size || 14, c: L.price_250g_color || '#000', w: 'normal' },
            { val: p1kg, lbl: '1Kg', s: L.price_1kg_size || 20, c: L.price_1kg_color || '#e74c3c', w: L.price_1kg_weight || 'bold' },
        ];

        tiers.forEach(function (t) {
            if (!t.val) return;
            var cell = el('div', 'weight-cell');
            cell.style.cssText = 'text-align:center;flex:1;';
            var lb = el('span', 'weight-label', t.lbl);
            lb.style.cssText = 'display:block;font-size:60%;opacity:.7;text-transform:uppercase;';
            var pr = el('span', 'sign-fit', formatPrice(t.val));
            pr.style.cssText = 'display:block;font-size:' + sz(t.s, 12, u) + ';color:' + t.c + ';font-weight:' + t.w + ';';
            cell.appendChild(lb);
            cell.appendChild(pr);
            row.appendChild(cell);
        });
        inner.appendChild(row);
    }

    // ─── Font size with unit ────────────────────────────────
    /** Convert a layout font-size number to a CSS value with the right unit.
     *  For 'mm' we use mm directly (print context).
     *  For 'px' we use px directly (designer zoom context — designer converts). */
    function sz(val, fallback, unit) {
        var v = val || fallback;
        if (unit === 'px') return v + 'px';
        // Convert pt-like value to mm: layout stores values as "visual points"
        // 1 visual-point ≈ 0.35mm gives nice results at typical sign sizes
        return (v * 0.35) + 'mm';
    }

    // ─── Theme Decorations ──────────────────────────────────
    var THEME_COLORS = {
        navidad: '#c41e3a', pascua: '#9b59b6', san_valentin: '#e91e8c',
        dia_madre: '#c2185b', halloween: '#ff6600', anio_nuevo: '#FFD700', patrio: '#74acdf',
    };

    function _decorate(card, L, u) {
        if (L.theme && L.theme !== 'none' && THEME_COLORS[L.theme]) {
            var stripe = document.createElement('div');
            stripe.style.cssText =
                'position:absolute;top:0;left:0;right:0;height:1' + u + ';' +
                'background:' + THEME_COLORS[L.theme] + ';z-index:3;pointer-events:none;';
            card.appendChild(stripe);
        }
        if (L.bg_watermark_show && L.bg_watermark) {
            var wm = el('div', 'sign-watermark', L.bg_watermark);
            wm.style.cssText =
                'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
                'font-size:3em;opacity:.08;pointer-events:none;z-index:0;user-select:none;';
            card.appendChild(wm);
        }
        var POS = { tl: 'top:0.5'+u+';left:0.5'+u, tr: 'top:0.5'+u+';right:0.5'+u,
                    bl: 'bottom:0.5'+u+';left:0.5'+u, br: 'bottom:0.5'+u+';right:0.5'+u };
        ['tl', 'tr', 'bl', 'br'].forEach(function (p) {
            var ico = L['corner_' + p];
            if (!ico) return;
            var sp = el('span', 'sign-corner-icon', ico);
            sp.style.cssText =
                'position:absolute;font-size:1em;line-height:1;pointer-events:none;z-index:4;' + POS[p] + ';';
            card.appendChild(sp);
        });
    }

    // ─── Auto-fit text ──────────────────────────────────────
    /** Shrink .sign-fit elements so they don't overflow their container.
     *  Call after rendering and after the elements are laid out in the DOM. */
    function autoFitAll(root) {
        var scope = root || document;
        scope.querySelectorAll('.sign-fit').forEach(function (txt) {
            var ref = txt.closest('.sign-inner');
            if (!ref) return;
            var maxW = ref.clientWidth - 4;
            if (maxW <= 0) return;
            var fs = parseFloat(window.getComputedStyle(txt).fontSize);
            if (isNaN(fs) || fs <= 0) return;
            var tries = 0;
            while (txt.scrollWidth > maxW && fs > 4 && tries < 100) {
                fs -= 0.5;
                txt.style.fontSize = fs + 'px';
                tries++;
            }
        });
    }

    return { renderSign: renderSign, autoFitAll: autoFitAll, formatPrice: formatPrice };
})();
