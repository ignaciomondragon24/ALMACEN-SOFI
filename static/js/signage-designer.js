/**
 * SIGNAGE DESIGNER v3 — Visual Template Editor
 * Uses SignageRenderer (signage-render.js) for preview rendering.
 */
(function () {
    'use strict';

    var CFG = window.SIGNAGE_DESIGNER;
    // defaultLayouts is already a JS object (rendered via |safe in template)
    var defaults = CFG.defaultLayouts || {};
    var currentType = CFG.templateType || 'simple';
    var layout = CFG.currentLayout || defaults[currentType] || defaults.simple || {};
    var zoom = 3;

    var THEME_PRESETS = {
        none:         { theme: 'none', corner_tl: '', corner_tr: '', corner_bl: '', corner_br: '', bg_watermark: '', bg_watermark_show: false },
        navidad:      { theme: 'navidad',      background_color: '#1a472a', border_color: '#c41e3a', border_width: 3, product_name_color: '#ffffff', price_color: '#FFD700', corner_tl: '❄️', corner_tr: '🎄', corner_bl: '⭐', corner_br: '❄️', bg_watermark: '🎄', bg_watermark_show: false },
        pascua:       { theme: 'pascua',       background_color: '#fff9e6', border_color: '#9b59b6', border_width: 3, product_name_color: '#4a235a', price_color: '#8e44ad', corner_tl: '🐰', corner_tr: '🥚', corner_bl: '🌸', corner_br: '🐣', bg_watermark: '🥚', bg_watermark_show: false },
        san_valentin: { theme: 'san_valentin', background_color: '#fff0f3', border_color: '#e91e8c', border_width: 3, product_name_color: '#c0392b', price_color: '#e91e8c', corner_tl: '❤️', corner_tr: '💕', corner_bl: '🌹', corner_br: '💝', bg_watermark: '❤️', bg_watermark_show: false },
        dia_madre:    { theme: 'dia_madre',    background_color: '#fce4ec', border_color: '#e91e8c', border_width: 3, product_name_color: '#880e4f', price_color: '#c2185b', corner_tl: '🌸', corner_tr: '💐', corner_bl: '🌷', corner_br: '🌺', bg_watermark: '🌸', bg_watermark_show: false },
        halloween:    { theme: 'halloween',    background_color: '#1a0a00', border_color: '#ff6600', border_width: 3, product_name_color: '#ff6600', price_color: '#ff9900', corner_tl: '🎃', corner_tr: '🕷️', corner_bl: '👻', corner_br: '🦇', bg_watermark: '🎃', bg_watermark_show: false },
        anio_nuevo:   { theme: 'anio_nuevo',   background_color: '#0a0a2e', border_color: '#FFD700', border_width: 3, product_name_color: '#FFD700', price_color: '#FFD700', corner_tl: '🎆', corner_tr: '✨', corner_bl: '🥂', corner_br: '🎉', bg_watermark: '✨', bg_watermark_show: false },
        patrio:       { theme: 'patrio',       background_color: '#e8f4fc', border_color: '#74acdf', border_width: 3, product_name_color: '#003087', price_color: '#003087', corner_tl: '🎉', corner_tr: '⭐', corner_bl: '🌟', corner_br: '🎊', bg_watermark: '⭐', bg_watermark_show: false },
    };

    var FONTS = [
        ['Arial, sans-serif', 'Arial'],
        ["'Helvetica Neue', Helvetica, sans-serif", 'Helvetica'],
        ['Impact, Charcoal, sans-serif', 'Impact'],
        ["Georgia, 'Times New Roman', serif", 'Georgia'],
        ["'Trebuchet MS', sans-serif", 'Trebuchet MS'],
        ["'Courier New', Courier, monospace", 'Courier New'],
        ["'Fredoka', sans-serif", 'Fredoka'],
        ["'Baloo 2', sans-serif", 'Baloo 2'],
        ["'Nunito', sans-serif", 'Nunito'],
    ];

    // DOM refs
    var preview, widthInput, heightInput, nameInput, layoutInput;

    /* ── SAMPLE DATA for preview per type ───────────────────── */
    var SAMPLE = {
        simple:      { name: 'SALADIX QUESO', price: '890', gramaje: '100g' },
        promotional: { name: 'TURRÓN MISKY', price: '180', promoQty: '3', promoPrice: '500' },
        bulk:        { name: 'FEELING PREMIUM', price: '11500', packageType: 'CAJA', packageQty: '30U.' },
        weight:      { name: 'ALMENDRAS PELADAS', price100g: '3200', price250g: '7350', price1kg: '29400' },
    };

    // ====================== INIT ======================
    document.addEventListener('DOMContentLoaded', function () {
        preview     = document.getElementById('signPreview');
        widthInput  = document.getElementById('widthMm');
        heightInput = document.getElementById('heightMm');
        nameInput   = document.getElementById('templateName');
        layoutInput = document.getElementById('layoutJsonInput');

        if (!CFG.isEdit) {
            var params = new URLSearchParams(window.location.search);
            var urlType = params.get('type');
            if (urlType && defaults[urlType]) {
                currentType = urlType;
                layout = defaults[urlType];
                var dims = getDefaultDims(urlType);
                widthInput.value = dims[0];
                heightInput.value = dims[1];
                var radio = document.querySelector('input[name="template_type"][value="' + urlType + '"]');
                if (radio) {
                    radio.checked = true;
                    radio.closest('.type-option').classList.add('active');
                }
            }
        }

        bindEvents();
        buildElementControls();
        syncControlsFromLayout();
        renderPreview();
    });

    // ====================== EVENTS ======================
    function bindEvents() {
        // Type selection
        document.querySelectorAll('.type-option').forEach(function (opt) {
            opt.addEventListener('click', function () {
                document.querySelectorAll('.type-option').forEach(function (o) { o.classList.remove('active'); });
                opt.classList.add('active');
                var radio = opt.querySelector('input');
                radio.checked = true;
                currentType = radio.value;
                layout = defaults[currentType];
                var dims = getDefaultDims(currentType);
                widthInput.value = dims[0];
                heightInput.value = dims[1];
                buildElementControls();
                syncControlsFromLayout();
                renderPreview();
            });
        });

        // Dimensions
        widthInput.addEventListener('input', renderPreview);
        heightInput.addEventListener('input', renderPreview);

        // Preset sizes
        document.querySelectorAll('.preset-size').forEach(function (btn) {
            btn.addEventListener('click', function () {
                widthInput.value = btn.dataset.w;
                heightInput.value = btn.dataset.h;
                renderPreview();
            });
        });

        // Global style controls
        ['bgColor', 'borderColor'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () {
                layout[el.dataset.prop] = el.value;
                renderPreview();
            });
        });

        ['borderWidth', 'borderRadius'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.addEventListener('input', function () {
                layout[el.dataset.prop] = parseInt(el.value);
                document.getElementById(id + 'Val').textContent = el.value + 'px';
                renderPreview();
            });
        });

        // Zoom controls
        document.getElementById('zoomOut').addEventListener('click', function () {
            zoom = Math.max(1, zoom - 0.5);
            updateZoom();
        });
        document.getElementById('zoomIn').addEventListener('click', function () {
            zoom = Math.min(8, zoom + 0.5);
            updateZoom();
        });
        document.getElementById('zoomFit').addEventListener('click', function () {
            var vp = document.getElementById('canvasViewport');
            var w = parseInt(widthInput.value) || 50;
            var h = parseInt(heightInput.value) || 40;
            var zx = (vp.clientWidth - 40) / w;
            var zy = (vp.clientHeight - 40) / h;
            zoom = Math.min(zx, zy, 8);
            zoom = Math.max(zoom, 1);
            updateZoom();
        });

        // Form submission — serialize layout
        document.getElementById('designerForm').addEventListener('submit', function () {
            layoutInput.value = JSON.stringify(layout);
        });

        // Theme buttons
        document.querySelectorAll('.theme-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyTheme(btn.dataset.theme);
                document.querySelectorAll('.theme-btn').forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
            });
        });
    }

    function applyTheme(themeName) {
        var preset = THEME_PRESETS[themeName];
        if (!preset) return;
        Object.keys(preset).forEach(function (k) { layout[k] = preset[k]; });
        syncControlsFromLayout();
        renderPreview();
    }

    // ====================== ELEMENT CONTROLS ======================
    function buildElementControls() {
        var container = document.getElementById('elementControls');
        container.innerHTML = '';

        var groups;
        if (currentType === 'simple') {
            groups = [
                {
                    title: '🏷️ Encabezado Tienda', controls: [
                        { type: 'check', prop: 'show_store_name', label: 'Mostrar nombre tienda' },
                        { type: 'text', prop: 'store_name', label: 'Nombre', placeholder: 'CHE GOLOSO' },
                        { type: 'color', prop: 'store_name_bg', label: 'Fondo' },
                        { type: 'color', prop: 'store_name_color', label: 'Color texto' },
                        { type: 'range', prop: 'store_name_size', label: 'Tamaño', min: 4, max: 20 },
                    ]
                },
                {
                    title: '📝 Nombre Producto', controls: [
                        { type: 'range', prop: 'product_name_size', label: 'Tamaño', min: 6, max: 40 },
                        { type: 'select', prop: 'product_name_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'product_name_color', label: 'Color' },
                    ]
                },
                {
                    title: '📐 Gramaje', controls: [
                        { type: 'check', prop: 'gramaje_show', label: 'Mostrar gramaje' },
                        { type: 'range', prop: 'gramaje_size', label: 'Tamaño', min: 4, max: 20 },
                        { type: 'color', prop: 'gramaje_color', label: 'Color' },
                    ]
                },
                {
                    title: '💲 Precio', controls: [
                        { type: 'range', prop: 'price_size', label: 'Tamaño', min: 10, max: 80 },
                        { type: 'select', prop: 'price_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'price_color', label: 'Color' },
                        { type: 'check', prop: 'price_show_currency', label: 'Mostrar $' },
                    ]
                },
            ];
        } else if (currentType === 'promotional') {
            groups = [
                {
                    title: '🔥 Etiqueta Promo', controls: [
                        { type: 'check', prop: 'promo_label_show', label: 'Mostrar etiqueta' },
                        { type: 'text', prop: 'promo_label_text', label: 'Texto', placeholder: 'PROMO!!' },
                        { type: 'color', prop: 'promo_label_bg', label: 'Fondo' },
                        { type: 'color', prop: 'promo_label_color', label: 'Color texto' },
                        { type: 'range', prop: 'promo_label_size', label: 'Tamaño', min: 6, max: 30 },
                    ]
                },
                {
                    title: '📝 Nombre Producto', controls: [
                        { type: 'range', prop: 'product_name_size', label: 'Tamaño', min: 6, max: 30 },
                        { type: 'select', prop: 'product_name_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'product_name_color', label: 'Color' },
                    ]
                },
                {
                    title: '💲 Precio Unitario', controls: [
                        { type: 'range', prop: 'unit_price_size', label: 'Tamaño', min: 6, max: 40 },
                        { type: 'color', prop: 'unit_price_color', label: 'Color' },
                    ]
                },
                {
                    title: '🏷️ Badge Promo (ej: 3 X)', controls: [
                        { type: 'range', prop: 'promo_badge_size', label: 'Tamaño', min: 10, max: 60 },
                        { type: 'color', prop: 'promo_badge_color', label: 'Color' },
                    ]
                },
                {
                    title: '💰 Precio Promo', controls: [
                        { type: 'range', prop: 'promo_price_size', label: 'Tamaño', min: 10, max: 60 },
                        { type: 'select', prop: 'promo_price_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'promo_price_color', label: 'Color' },
                        { type: 'check', prop: 'price_show_currency', label: 'Mostrar $' },
                    ]
                },
            ];
        } else if (currentType === 'bulk') {
            groups = [
                {
                    title: '📝 Nombre Producto', controls: [
                        { type: 'range', prop: 'product_name_size', label: 'Tamaño', min: 6, max: 40 },
                        { type: 'select', prop: 'product_name_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'product_name_color', label: 'Color' },
                    ]
                },
                {
                    title: '💲 Precio Total', controls: [
                        { type: 'range', prop: 'total_price_size', label: 'Tamaño', min: 10, max: 60 },
                        { type: 'select', prop: 'total_price_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'total_price_color', label: 'Color' },
                        { type: 'check', prop: 'price_show_currency', label: 'Mostrar $' },
                    ]
                },
                {
                    title: '📦 Info Empaque', controls: [
                        { type: 'range', prop: 'package_info_size', label: 'Tamaño', min: 6, max: 30 },
                        { type: 'select', prop: 'package_info_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'package_info_color', label: 'Color' },
                    ]
                },
            ];
        } else if (currentType === 'weight') {
            groups = [
                {
                    title: '📝 Nombre Producto', controls: [
                        { type: 'range', prop: 'product_name_size', label: 'Tamaño', min: 6, max: 30 },
                        { type: 'select', prop: 'product_name_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'product_name_color', label: 'Color' },
                    ]
                },
                {
                    title: '⚖️ Precio 100g', controls: [
                        { type: 'range', prop: 'price_100g_size', label: 'Tamaño', min: 6, max: 30 },
                        { type: 'color', prop: 'price_100g_color', label: 'Color' },
                    ]
                },
                {
                    title: '⚖️ Precio ¼ Kg', controls: [
                        { type: 'range', prop: 'price_250g_size', label: 'Tamaño', min: 6, max: 30 },
                        { type: 'color', prop: 'price_250g_color', label: 'Color' },
                    ]
                },
                {
                    title: '⚖️ Precio Kg', controls: [
                        { type: 'range', prop: 'price_1kg_size', label: 'Tamaño', min: 10, max: 40 },
                        { type: 'select', prop: 'price_1kg_weight', label: 'Grosor', options: [['normal', 'Normal'], ['bold', 'Negrita']] },
                        { type: 'color', prop: 'price_1kg_color', label: 'Color' },
                        { type: 'check', prop: 'price_show_currency', label: 'Mostrar $' },
                    ]
                },
                {
                    title: '➖ Divisores', controls: [
                        { type: 'check', prop: 'show_dividers', label: 'Mostrar divisores' },
                        { type: 'color', prop: 'divider_color', label: 'Color' },
                    ]
                },
            ];
        }

        if (!groups) return;
        // Common groups for ALL types
        groups.push({
            title: '🔤 Tipografía',
            controls: [
                { type: 'font',   prop: 'font_family', label: 'Fuente' },
                { type: 'select', prop: 'text_align',  label: 'Alineación', options: [['center', '▼ Centrado'], ['left', '◄ Izquierda'], ['right', '► Derecha']] },
            ]
        });
        groups.push({
            title: '✨ Decoraciones / Iconos',
            controls: [
                { type: 'text',  prop: 'corner_tl', label: '↖ Sup. izquierda', placeholder: '❄️' },
                { type: 'text',  prop: 'corner_tr', label: '↗ Sup. derecha',    placeholder: '🎄' },
                { type: 'text',  prop: 'corner_bl', label: '↙ Inf. izquierda', placeholder: '⭐' },
                { type: 'text',  prop: 'corner_br', label: '↘ Inf. derecha',   placeholder: '❄️' },
                { type: 'text',  prop: 'bg_watermark',      label: '🖼 Marca de agua (emoji)', placeholder: '🎄' },
                { type: 'check', prop: 'bg_watermark_show', label: 'Mostrar marca de agua' },
            ]
        });
        groups.forEach(function (g) {
            var div = document.createElement('div');
            div.className = 'element-control-group';
            var html = '<h6>' + g.title + '</h6><div class="row g-1">';
            g.controls.forEach(function (c) {
                html += buildControl(c);
            });
            html += '</div>';
            div.innerHTML = html;
            container.appendChild(div);
        });

        // Bind dynamically created controls
        container.querySelectorAll('[data-prop]').forEach(function (el) {
            el.addEventListener('input', function () {
                var prop = el.dataset.prop;
                if (el.type === 'checkbox') {
                    layout[prop] = el.checked;
                } else if (el.type === 'range' || el.type === 'number') {
                    layout[prop] = parseInt(el.value);
                    var valSpan = el.parentElement.querySelector('.range-val');
                    if (valSpan) valSpan.textContent = el.value;
                } else {
                    layout[prop] = el.value;
                }
                renderPreview();
            });
        });
    }

    function buildControl(c) {
        var val = layout[c.prop];
        var colClass = (c.type === 'text' || c.type === 'check' || c.type === 'font') ? 'col-12' : 'col-6';
        var html = '<div class="' + colClass + '">';
        html += '<label class="form-label mb-0">' + c.label + '</label>';

        if (c.type === 'font') {
            html += '<select class="form-select form-select-sm" data-prop="' + c.prop + '" style="font-family:' + (val || 'Arial') + '">';
            FONTS.forEach(function (f) {
                html += '<option value="' + f[0] + '"' + (val === f[0] ? ' selected' : '') + ' style="font-family:' + f[0] + '">' + f[1] + '</option>';
            });
            html += '</select>';
        } else if (c.type === 'color') {
            html += '<input type="color" class="form-control form-control-sm form-control-color" data-prop="' + c.prop + '" value="' + (val || '#000000') + '">';
        } else if (c.type === 'range') {
            var min = c.min || 4, max = c.max || 60;
            html += '<input type="range" class="form-range" data-prop="' + c.prop + '" min="' + min + '" max="' + max + '" step="1" value="' + (val || min) + '">';
            html += '<small class="text-muted range-val">' + (val || min) + '</small>';
        } else if (c.type === 'check') {
            html += '<div class="form-check"><input type="checkbox" class="form-check-input" data-prop="' + c.prop + '"' + (val !== false ? ' checked' : '') + '>';
            html += '<label class="form-check-label small">' + c.label + '</label></div>';
        } else if (c.type === 'select') {
            html += '<select class="form-select form-select-sm" data-prop="' + c.prop + '">';
            (c.options || []).forEach(function (o) {
                html += '<option value="' + o[0] + '"' + (val === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
            });
            html += '</select>';
        } else if (c.type === 'text') {
            html += '<input type="text" class="form-control form-control-sm" data-prop="' + c.prop + '" value="' + (val || '') + '" placeholder="' + (c.placeholder || '') + '">';
        }

        html += '</div>';
        return html;
    }

    // ====================== SYNC CONTROLS ======================
    function syncControlsFromLayout() {
        // Global controls
        setVal('bgColor', layout.background_color);
        setVal('borderColor', layout.border_color);
        setVal('borderWidth', layout.border_width);
        setVal('borderRadius', layout.border_radius);
        setText('borderWidthVal', (layout.border_width || 0) + 'px');
        setText('borderRadiusVal', (layout.border_radius || 0) + 'px');

        // Dynamic controls
        document.querySelectorAll('#elementControls [data-prop]').forEach(function (el) {
            var val = layout[el.dataset.prop];
            if (el.type === 'checkbox') {
                el.checked = val !== false;
            } else if (val !== undefined) {
                el.value = val;
                var valSpan = el.parentElement.querySelector('.range-val');
                if (valSpan) valSpan.textContent = val;
            }
        });
        // Sync active theme button
        var curTheme = layout.theme || 'none';
        document.querySelectorAll('.theme-btn').forEach(function (btn) {
            btn.classList.toggle('active', btn.dataset.theme === curTheme);
        });
    }

    function setVal(id, val) {
        var el = document.getElementById(id);
        if (el && val !== undefined) el.value = val;
    }
    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    // ====================== PREVIEW RENDERING ======================
    function renderPreview() {
        var w = parseInt(widthInput.value) || 50;
        var h = parseInt(heightInput.value) || 40;

        document.getElementById('dimensionLabel').textContent = w + '\u00d7' + h + ' mm';

        preview.style.width  = (w * zoom) + 'px';
        preview.style.height = (h * zoom) + 'px';

        // Build a temporary element with sample data attributes
        var sample = SAMPLE[currentType] || SAMPLE.simple;
        preview.dataset.name       = sample.name  || '';
        preview.dataset.price      = sample.price || '';
        preview.dataset.gramaje    = sample.gramaje || '';
        preview.dataset.promoQty   = sample.promoQty || '';
        preview.dataset.promoPrice = sample.promoPrice || '';
        preview.dataset.packageType= sample.packageType || '';
        preview.dataset.packageQty = sample.packageQty || '';
        preview.dataset.price100g  = sample.price100g || '';
        preview.dataset.price250g  = sample.price250g || '';
        preview.dataset.price1kg   = sample.price1kg || '';

        // Use the shared renderer — it sets all styles on the element
        SignageRenderer.renderSign(preview, layout, currentType);

        // Scale internal fonts for designer zoom (renderer uses mm, we use px zoom)
        var sf = zoom / 3.78;
        preview.querySelectorAll('.sign-inner *').forEach(function (child) {
            var fs = parseFloat(child.style.fontSize);
            if (fs) child.style.fontSize = (fs * sf) + 'px';
        });
        // Scale padding
        var inner = preview.querySelector('.sign-inner');
        if (inner) {
            inner.style.padding = ((layout.padding || 3) * zoom / 3.78) + 'px';
        }

        setTimeout(function () {
            preview.querySelectorAll('.fit-text').forEach(function (txt) {
                var ref = txt.closest('.sign-inner') || preview;
                var maxW = ref.clientWidth - 8;
                var fs = parseFloat(window.getComputedStyle(txt).fontSize);
                var i = 0;
                while (txt.scrollWidth > maxW && fs > 6 && i < 50) {
                    fs -= 0.5;
                    txt.style.fontSize = fs + 'px';
                    i++;
                }
            });
        }, 10);
    }

    // ====================== ZOOM ======================
    function updateZoom() {
        document.getElementById('zoomLabel').textContent = Math.round(zoom / 3.78 * 100) + '%';
        renderPreview();
    }

    // ====================== HELPERS ======================
    function getDefaultDims(type) {
        var dims = { simple: [50, 40], promotional: [70, 50], bulk: [100, 70], weight: [100, 70] };
        return dims[type] || [50, 40];
    }

})();
