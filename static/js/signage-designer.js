/**
 * SIGNAGE DESIGNER v5 — Complete rewrite.
 * Visual Template Editor — "Canva-style" sign designer.
 * Uses SignageRenderer.renderSign() with unit:'px' for live preview.
 */
(function () {
    'use strict';

    /* ── Config from Django template ─────────────────────────── */
    var CFG = window.SIGNAGE_DESIGNER || {};
    var defaults = CFG.defaultLayouts || {};
    var currentType = CFG.templateType || 'simple';
    var layout = _deepClone(CFG.currentLayout || defaults[currentType] || defaults.simple || {});
    // Pixels-per-mm zoom factor. 3.78 ≈ 1mm on a 96dpi screen.
    var PX_PER_MM = 3.78;
    var zoomLevel = 1.0; // 1.0 = real size on screen

    /* ── Theme presets ───────────────────────────────────────── */
    var THEMES = {
        none:         { theme:'none', corner_tl:'', corner_tr:'', corner_bl:'', corner_br:'', bg_watermark:'', bg_watermark_show:false },
        navidad:      { theme:'navidad', background_color:'#1a472a', border_color:'#c41e3a', border_width:3, product_name_color:'#ffffff', price_color:'#FFD700', corner_tl:'❄️', corner_tr:'🎄', corner_bl:'⭐', corner_br:'❄️', bg_watermark:'🎄', bg_watermark_show:false },
        pascua:       { theme:'pascua', background_color:'#fff9e6', border_color:'#9b59b6', border_width:3, product_name_color:'#4a235a', price_color:'#8e44ad', corner_tl:'🐰', corner_tr:'🥚', corner_bl:'🌸', corner_br:'🐣', bg_watermark:'🥚', bg_watermark_show:false },
        san_valentin: { theme:'san_valentin', background_color:'#fff0f3', border_color:'#e91e8c', border_width:3, product_name_color:'#c0392b', price_color:'#e91e8c', corner_tl:'❤️', corner_tr:'💕', corner_bl:'🌹', corner_br:'💝', bg_watermark:'❤️', bg_watermark_show:false },
        dia_madre:    { theme:'dia_madre', background_color:'#fce4ec', border_color:'#e91e8c', border_width:3, product_name_color:'#880e4f', price_color:'#c2185b', corner_tl:'🌸', corner_tr:'💐', corner_bl:'🌷', corner_br:'🌺', bg_watermark:'🌸', bg_watermark_show:false },
        halloween:    { theme:'halloween', background_color:'#1a0a00', border_color:'#ff6600', border_width:3, product_name_color:'#ff6600', price_color:'#ff9900', corner_tl:'🎃', corner_tr:'🕷️', corner_bl:'👻', corner_br:'🦇', bg_watermark:'🎃', bg_watermark_show:false },
        anio_nuevo:   { theme:'anio_nuevo', background_color:'#0a0a2e', border_color:'#FFD700', border_width:3, product_name_color:'#FFD700', price_color:'#FFD700', corner_tl:'🎆', corner_tr:'✨', corner_bl:'🥂', corner_br:'🎉', bg_watermark:'✨', bg_watermark_show:false },
        patrio:       { theme:'patrio', background_color:'#e8f4fc', border_color:'#74acdf', border_width:3, product_name_color:'#003087', price_color:'#003087', corner_tl:'🎉', corner_tr:'⭐', corner_bl:'🌟', corner_br:'🎊', bg_watermark:'⭐', bg_watermark_show:false },
    };

    var FONTS = [
        ['Arial, sans-serif','Arial'], ["'Helvetica Neue', Helvetica, sans-serif",'Helvetica'],
        ['Impact, Charcoal, sans-serif','Impact'], ["Georgia, 'Times New Roman', serif",'Georgia'],
        ["'Trebuchet MS', sans-serif",'Trebuchet MS'], ["'Courier New', Courier, monospace",'Courier New'],
        ["'Fredoka', sans-serif",'Fredoka'], ["'Baloo 2', sans-serif",'Baloo 2'], ["'Nunito', sans-serif",'Nunito'],
    ];

    /* ── Sample data per type (for designer preview) ─────────── */
    var SAMPLE = {
        simple:      { name:'SALADIX QUESO', price:'890', gramaje:'100g' },
        promotional: { name:'TURRÓN MISKY', price:'180', promoQty:'3', promoPrice:'500' },
        bulk:        { name:'FEELING PREMIUM', price:'11500', packageType:'CAJA', packageQty:'30U.' },
        weight:      { name:'ALMENDRAS PELADAS', price100g:'3200', price250g:'7350', price1kg:'29400' },
    };

    /* ── Default dimensions per type (mm) ────────────────────── */
    var DEFAULT_DIMS = { simple:[50,40], promotional:[70,50], bulk:[100,70], weight:[100,70] };

    /* ── DOM refs ─────────────────────────────────────────────── */
    var preview, widthInput, heightInput, nameInput, layoutInput;

    // ═══════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', function () {
        preview     = document.getElementById('signPreview');
        widthInput  = document.getElementById('widthMm');
        heightInput = document.getElementById('heightMm');
        nameInput   = document.getElementById('templateName');
        layoutInput = document.getElementById('layoutJsonInput');

        // For new templates, check URL ?type= param
        if (!CFG.isEdit) {
            var urlType = new URLSearchParams(window.location.search).get('type');
            if (urlType && defaults[urlType]) {
                currentType = urlType;
                layout = _deepClone(defaults[urlType]);
                var dims = DEFAULT_DIMS[urlType] || [50, 40];
                widthInput.value = dims[0];
                heightInput.value = dims[1];
                _activateTypeRadio(urlType);
            }
        }

        _bindEvents();
        _buildControls();
        _syncControls();
        _render();
    });

    // ═══════════════════════════════════════════════════════════
    // EVENT BINDING
    // ═══════════════════════════════════════════════════════════
    function _bindEvents() {
        // --- Type selector ---
        document.querySelectorAll('.type-option').forEach(function (opt) {
            opt.addEventListener('click', function () {
                document.querySelectorAll('.type-option').forEach(function (o) { o.classList.remove('active'); });
                opt.classList.add('active');
                opt.querySelector('input').checked = true;
                currentType = opt.querySelector('input').value;
                layout = _deepClone(defaults[currentType] || {});
                var dims = DEFAULT_DIMS[currentType] || [50, 40];
                widthInput.value = dims[0];
                heightInput.value = dims[1];
                _buildControls();
                _syncControls();
                _render();
            });
        });

        // --- Dimension inputs ---
        widthInput.addEventListener('input', _render);
        heightInput.addEventListener('input', _render);

        // --- Preset size buttons ---
        document.querySelectorAll('.preset-size').forEach(function (btn) {
            btn.addEventListener('click', function () {
                widthInput.value = btn.dataset.w;
                heightInput.value = btn.dataset.h;
                _render();
            });
        });

        // --- Global style controls (bg, border) ---
        ['bgColor', 'borderColor'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () {
                layout[el.dataset.prop] = el.value;
                _render();
            });
        });
        ['borderWidth', 'borderRadius'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () {
                layout[el.dataset.prop] = parseInt(el.value);
                var lab = document.getElementById(id + 'Val');
                if (lab) lab.textContent = el.value + 'px';
                _render();
            });
        });

        // --- Zoom ---
        document.getElementById('zoomOut').addEventListener('click', function () {
            zoomLevel = Math.max(0.3, zoomLevel - 0.15);
            _render();
        });
        document.getElementById('zoomIn').addEventListener('click', function () {
            zoomLevel = Math.min(3, zoomLevel + 0.15);
            _render();
        });
        document.getElementById('zoomFit').addEventListener('click', function () {
            var vp = document.getElementById('canvasViewport');
            var wMm = parseInt(widthInput.value) || 50;
            var hMm = parseInt(heightInput.value) || 40;
            var zx = (vp.clientWidth - 40) / (wMm * PX_PER_MM);
            var zy = (vp.clientHeight - 40) / (hMm * PX_PER_MM);
            zoomLevel = Math.max(0.3, Math.min(Math.min(zx, zy), 3));
            _render();
        });

        // --- Theme buttons ---
        document.querySelectorAll('.theme-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var t = THEMES[btn.dataset.theme];
                if (!t) return;
                Object.keys(t).forEach(function (k) { layout[k] = t[k]; });
                document.querySelectorAll('.theme-btn').forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                _syncControls();
                _render();
            });
        });

        // --- Form submit ---
        document.getElementById('designerForm').addEventListener('submit', function () {
            layoutInput.value = JSON.stringify(layout);
        });
    }

    // ═══════════════════════════════════════════════════════════
    // ELEMENT CONTROLS (per-type control panel)
    // ═══════════════════════════════════════════════════════════
    function _buildControls() {
        var c = document.getElementById('elementControls');
        c.innerHTML = '';

        var groups = _controlGroupsForType(currentType);
        // Append shared groups
        groups.push({
            title: '🔤 Tipografía', controls: [
                { type:'font', prop:'font_family', label:'Fuente' },
                { type:'select', prop:'text_align', label:'Alineación', opts:[['center','▼ Centrado'],['left','◄ Izquierda'],['right','► Derecha']] },
            ]
        });
        groups.push({
            title: '✨ Decoraciones', controls: [
                { type:'text', prop:'corner_tl', label:'↖ Sup. izq', ph:'❄️' },
                { type:'text', prop:'corner_tr', label:'↗ Sup. der', ph:'🎄' },
                { type:'text', prop:'corner_bl', label:'↙ Inf. izq', ph:'⭐' },
                { type:'text', prop:'corner_br', label:'↘ Inf. der', ph:'❄️' },
                { type:'text', prop:'bg_watermark', label:'Marca de agua', ph:'🎄' },
                { type:'check', prop:'bg_watermark_show', label:'Mostrar marca de agua' },
            ]
        });

        groups.forEach(function (g) {
            var div = document.createElement('div');
            div.className = 'element-control-group';
            var html = '<h6>' + g.title + '</h6><div class="row g-1">';
            g.controls.forEach(function (ctrl) { html += _ctrlHtml(ctrl); });
            html += '</div>';
            div.innerHTML = html;
            c.appendChild(div);
        });

        // Bind dynamic controls
        c.querySelectorAll('[data-prop]').forEach(function (el) {
            el.addEventListener('input', function () {
                var p = el.dataset.prop;
                if (el.type === 'checkbox') layout[p] = el.checked;
                else if (el.type === 'range' || el.type === 'number') {
                    layout[p] = parseInt(el.value);
                    var s = el.parentElement.querySelector('.range-val');
                    if (s) s.textContent = el.value;
                } else layout[p] = el.value;
                _render();
            });
        });
    }

    function _controlGroupsForType(type) {
        if (type === 'simple') return [
            { title:'🏷️ Encabezado Tienda', controls:[
                { type:'check', prop:'show_store_name', label:'Mostrar nombre tienda' },
                { type:'text', prop:'store_name', label:'Nombre', ph:'CHE GOLOSO' },
                { type:'color', prop:'store_name_bg', label:'Fondo' },
                { type:'color', prop:'store_name_color', label:'Color texto' },
                { type:'range', prop:'store_name_size', label:'Tamaño', min:4, max:20 },
            ]},
            { title:'📝 Nombre Producto', controls:[
                { type:'range', prop:'product_name_size', label:'Tamaño', min:6, max:40 },
                { type:'select', prop:'product_name_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'product_name_color', label:'Color' },
            ]},
            { title:'📐 Gramaje', controls:[
                { type:'check', prop:'gramaje_show', label:'Mostrar gramaje' },
                { type:'range', prop:'gramaje_size', label:'Tamaño', min:4, max:20 },
                { type:'color', prop:'gramaje_color', label:'Color' },
            ]},
            { title:'💲 Precio', controls:[
                { type:'range', prop:'price_size', label:'Tamaño', min:10, max:80 },
                { type:'select', prop:'price_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'price_color', label:'Color' },
            ]},
        ];
        if (type === 'promotional') return [
            { title:'🔥 Etiqueta Promo', controls:[
                { type:'check', prop:'promo_label_show', label:'Mostrar etiqueta' },
                { type:'text', prop:'promo_label_text', label:'Texto', ph:'PROMO!!' },
                { type:'color', prop:'promo_label_bg', label:'Fondo' },
                { type:'color', prop:'promo_label_color', label:'Color texto' },
                { type:'range', prop:'promo_label_size', label:'Tamaño', min:6, max:30 },
            ]},
            { title:'📝 Nombre Producto', controls:[
                { type:'range', prop:'product_name_size', label:'Tamaño', min:6, max:30 },
                { type:'select', prop:'product_name_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'product_name_color', label:'Color' },
            ]},
            { title:'💲 Precio Unitario', controls:[
                { type:'range', prop:'unit_price_size', label:'Tamaño', min:6, max:40 },
                { type:'color', prop:'unit_price_color', label:'Color' },
            ]},
            { title:'🏷️ Badge (ej: LLEVA 3)', controls:[
                { type:'range', prop:'promo_badge_size', label:'Tamaño', min:10, max:60 },
                { type:'color', prop:'promo_badge_color', label:'Color' },
            ]},
            { title:'💰 Precio Promo', controls:[
                { type:'range', prop:'promo_price_size', label:'Tamaño', min:10, max:60 },
                { type:'select', prop:'promo_price_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'promo_price_color', label:'Color' },
            ]},
        ];
        if (type === 'bulk') return [
            { title:'📝 Nombre Producto', controls:[
                { type:'range', prop:'product_name_size', label:'Tamaño', min:6, max:40 },
                { type:'select', prop:'product_name_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'product_name_color', label:'Color' },
            ]},
            { title:'💲 Precio Total', controls:[
                { type:'range', prop:'total_price_size', label:'Tamaño', min:10, max:60 },
                { type:'select', prop:'total_price_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'total_price_color', label:'Color' },
            ]},
            { title:'📦 Info Empaque', controls:[
                { type:'range', prop:'package_info_size', label:'Tamaño', min:6, max:30 },
                { type:'select', prop:'package_info_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'package_info_color', label:'Color' },
            ]},
        ];
        if (type === 'weight') return [
            { title:'📝 Nombre Producto', controls:[
                { type:'range', prop:'product_name_size', label:'Tamaño', min:6, max:30 },
                { type:'select', prop:'product_name_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'product_name_color', label:'Color' },
            ]},
            { title:'⚖️ Precio 100g', controls:[
                { type:'range', prop:'price_100g_size', label:'Tamaño', min:6, max:30 },
                { type:'color', prop:'price_100g_color', label:'Color' },
            ]},
            { title:'⚖️ Precio ¼ Kg', controls:[
                { type:'range', prop:'price_250g_size', label:'Tamaño', min:6, max:30 },
                { type:'color', prop:'price_250g_color', label:'Color' },
            ]},
            { title:'⚖️ Precio Kg', controls:[
                { type:'range', prop:'price_1kg_size', label:'Tamaño', min:10, max:40 },
                { type:'select', prop:'price_1kg_weight', label:'Grosor', opts:[['normal','Normal'],['bold','Negrita']] },
                { type:'color', prop:'price_1kg_color', label:'Color' },
            ]},
            { title:'➖ Divisores', controls:[
                { type:'check', prop:'show_dividers', label:'Mostrar divisores' },
                { type:'color', prop:'divider_color', label:'Color' },
            ]},
        ];
        return [];
    }

    function _ctrlHtml(c) {
        var v = layout[c.prop];
        var col = (c.type === 'text' || c.type === 'check' || c.type === 'font') ? 'col-12' : 'col-6';
        var h = '<div class="' + col + '">';
        h += '<label class="form-label mb-0">' + c.label + '</label>';
        if (c.type === 'font') {
            h += '<select class="form-select form-select-sm" data-prop="' + c.prop + '">';
            FONTS.forEach(function (f) {
                h += '<option value="' + f[0] + '"' + (v === f[0] ? ' selected' : '') + ' style="font-family:' + f[0] + '">' + f[1] + '</option>';
            });
            h += '</select>';
        } else if (c.type === 'color') {
            h += '<input type="color" class="form-control form-control-sm form-control-color" data-prop="' + c.prop + '" value="' + (v || '#000000') + '">';
        } else if (c.type === 'range') {
            var mn = c.min || 4, mx = c.max || 60;
            h += '<input type="range" class="form-range" data-prop="' + c.prop + '" min="' + mn + '" max="' + mx + '" step="1" value="' + (v || mn) + '">';
            h += '<small class="text-muted range-val">' + (v || mn) + '</small>';
        } else if (c.type === 'check') {
            h += '<div class="form-check"><input type="checkbox" class="form-check-input" data-prop="' + c.prop + '"' + (v !== false ? ' checked' : '') + '>';
            h += '<label class="form-check-label small">' + c.label + '</label></div>';
        } else if (c.type === 'select') {
            h += '<select class="form-select form-select-sm" data-prop="' + c.prop + '">';
            (c.opts || []).forEach(function (o) { h += '<option value="' + o[0] + '"' + (v === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; });
            h += '</select>';
        } else if (c.type === 'text') {
            h += '<input type="text" class="form-control form-control-sm" data-prop="' + c.prop + '" value="' + _escAttr(v || '') + '" placeholder="' + _escAttr(c.ph || '') + '">';
        }
        h += '</div>';
        return h;
    }

    // ═══════════════════════════════════════════════════════════
    // SYNC CONTROLS FROM LAYOUT
    // ═══════════════════════════════════════════════════════════
    function _syncControls() {
        _setVal('bgColor', layout.background_color);
        _setVal('borderColor', layout.border_color);
        _setVal('borderWidth', layout.border_width);
        _setVal('borderRadius', layout.border_radius);
        _setText('borderWidthVal', (layout.border_width || 0) + 'px');
        _setText('borderRadiusVal', (layout.border_radius || 0) + 'px');

        document.querySelectorAll('#elementControls [data-prop]').forEach(function (el) {
            var val = layout[el.dataset.prop];
            if (el.type === 'checkbox') el.checked = val !== false;
            else if (val !== undefined) {
                el.value = val;
                var s = el.parentElement.querySelector('.range-val');
                if (s) s.textContent = val;
            }
        });

        var cur = layout.theme || 'none';
        document.querySelectorAll('.theme-btn').forEach(function (b) {
            b.classList.toggle('active', b.dataset.theme === cur);
        });
    }

    // ═══════════════════════════════════════════════════════════
    // PREVIEW RENDERING
    // ═══════════════════════════════════════════════════════════
    function _render() {
        var wMm = parseInt(widthInput.value) || 50;
        var hMm = parseInt(heightInput.value) || 40;
        var scale = PX_PER_MM * zoomLevel;

        // Update dimension label
        _setText('dimensionLabel', wMm + '\u00d7' + hMm + ' mm');
        _setText('zoomLabel', Math.round(zoomLevel * 100) + '%');

        // Size the preview element in px
        preview.style.width  = Math.round(wMm * scale) + 'px';
        preview.style.height = Math.round(hMm * scale) + 'px';

        // Inject sample data attributes
        var sample = SAMPLE[currentType] || SAMPLE.simple;
        Object.keys(sample).forEach(function (k) { preview.dataset[k] = sample[k]; });

        // Build a scaled layout where font sizes are converted from "design points"
        // to actual pixels at the current zoom. The renderer with unit:'px' will
        // use these values directly.
        var scaledLayout = _deepClone(layout);
        var fontScale = scale * 0.35; // 0.35 is the mm-per-point factor from render.js sz()
        var sizeProps = [
            'store_name_size', 'product_name_size', 'gramaje_size', 'price_size',
            'promo_label_size', 'unit_price_size', 'promo_badge_size', 'promo_price_size',
            'total_price_size', 'package_info_size',
            'price_100g_size', 'price_250g_size', 'price_1kg_size',
        ];
        sizeProps.forEach(function (p) {
            if (scaledLayout[p]) scaledLayout[p] = Math.round(scaledLayout[p] * fontScale);
        });
        // Scale padding too
        if (scaledLayout.padding) scaledLayout.padding = Math.round(scaledLayout.padding * scale);

        SignageRenderer.renderSign(preview, scaledLayout, currentType, { unit: 'px' });

        // Auto-fit text after a brief layout settle
        setTimeout(function () { SignageRenderer.autoFitAll(preview); }, 20);
    }

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════
    function _activateTypeRadio(type) {
        var radio = document.querySelector('input[name="template_type"][value="' + type + '"]');
        if (radio) {
            radio.checked = true;
            document.querySelectorAll('.type-option').forEach(function (o) { o.classList.remove('active'); });
            radio.closest('.type-option').classList.add('active');
        }
    }
    function _setVal(id, val)   { var e = document.getElementById(id); if (e && val !== undefined) e.value = val; }
    function _setText(id, text) { var e = document.getElementById(id); if (e) e.textContent = text; }
    function _escAttr(s)        { return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    function _deepClone(o)      { return JSON.parse(JSON.stringify(o)); }

})();
