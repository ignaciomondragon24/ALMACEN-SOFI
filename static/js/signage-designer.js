/**
 * SIGNAGE DESIGNER - Visual Template Editor
 * Handles the interactive template designer with live preview.
 */
(function () {
    'use strict';

    var CFG = window.SIGNAGE_DESIGNER;
    var defaults = JSON.parse(CFG.defaultLayouts);
    var currentType = CFG.templateType || 'simple';
    var layout = CFG.currentLayout || defaults[currentType] || defaults.simple;
    var zoom = 3; // px per mm (≈ 3x zoom for comfortable editing)

    // Seasonal theme presets
    var THEME_PRESETS = {
        none:        { theme: 'none', corner_tl: '', corner_tr: '', corner_bl: '', corner_br: '', bg_watermark: '', bg_watermark_show: false },
        navidad:     { theme: 'navidad',     background_color: '#1a472a', border_color: '#c41e3a', border_width: 3, product_name_color: '#ffffff', price_color: '#FFD700', corner_tl: '❄️', corner_tr: '🎄', corner_bl: '⭐', corner_br: '❄️', bg_watermark: '🎄', bg_watermark_show: false },
        pascua:      { theme: 'pascua',      background_color: '#fff9e6', border_color: '#9b59b6', border_width: 3, product_name_color: '#4a235a', price_color: '#8e44ad', corner_tl: '🐰', corner_tr: '🥚', corner_bl: '🌸', corner_br: '🐣', bg_watermark: '🥚', bg_watermark_show: false },
        san_valentin:{ theme: 'san_valentin',background_color: '#fff0f3', border_color: '#e91e8c', border_width: 3, product_name_color: '#c0392b', price_color: '#e91e8c', corner_tl: '❤️', corner_tr: '💕', corner_bl: '🌹', corner_br: '💝', bg_watermark: '❤️', bg_watermark_show: false },
        dia_madre:   { theme: 'dia_madre',   background_color: '#fce4ec', border_color: '#e91e8c', border_width: 3, product_name_color: '#880e4f', price_color: '#c2185b', corner_tl: '🌸', corner_tr: '💐', corner_bl: '🌷', corner_br: '🌺', bg_watermark: '🌸', bg_watermark_show: false },
        halloween:   { theme: 'halloween',   background_color: '#1a0a00', border_color: '#ff6600', border_width: 3, product_name_color: '#ff6600', price_color: '#ff9900', corner_tl: '🎃', corner_tr: '🕷️', corner_bl: '👻', corner_br: '🦇', bg_watermark: '🎃', bg_watermark_show: false },
        año_nuevo:   { theme: 'año_nuevo',   background_color: '#0a0a2e', border_color: '#FFD700', border_width: 3, product_name_color: '#FFD700', price_color: '#FFD700', corner_tl: '🎆', corner_tr: '✨', corner_bl: '🥂', corner_br: '🎉', bg_watermark: '✨', bg_watermark_show: false },
        patrio:      { theme: 'patrio',      background_color: '#e8f4fc', border_color: '#74acdf', border_width: 3, product_name_color: '#003087', price_color: '#003087', corner_tl: '🎉', corner_tr: '⭐', corner_bl: '🌟', corner_br: '🎊', bg_watermark: '⭐', bg_watermark_show: false },
    };

    var FONTS = [
        ['Arial, sans-serif', 'Arial'],
        ["'Helvetica Neue', Helvetica, sans-serif", 'Helvetica'],
        ['Impact, Charcoal, sans-serif', 'Impact'],
        ["Georgia, 'Times New Roman', serif", 'Georgia'],
        ["'Trebuchet MS', sans-serif", 'Trebuchet MS'],
        ["'Courier New', Courier, monospace", 'Courier New'],
        ["'Comic Sans MS', cursive", 'Comic Sans'],
    ];

    // DOM refs
    var preview, widthInput, heightInput, nameInput, layoutInput;

    // ====================== INIT ======================
    document.addEventListener('DOMContentLoaded', function () {
        preview = document.getElementById('signPreview');
        widthInput = document.getElementById('widthMm');
        heightInput = document.getElementById('heightMm');
        nameInput = document.getElementById('templateName');
        layoutInput = document.getElementById('layoutJsonInput');

        // Read type from URL if new template
        if (!CFG.isEdit) {
            var params = new URLSearchParams(window.location.search);
            var urlType = params.get('type');
            if (urlType && defaults[urlType]) {
                currentType = urlType;
                layout = defaults[urlType];
                var dims = getDefaultDims(urlType);
                widthInput.value = dims[0];
                heightInput.value = dims[1];
                // Check radio
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

        // Update dimension label
        document.getElementById('dimensionLabel').textContent = w + '×' + h + ' mm';

        // Set preview dimensions (scaled)
        preview.style.width = (w * zoom) + 'px';
        preview.style.height = (h * zoom) + 'px';

        // Apply base styles
        preview.style.background = layout.background_color || '#fff';
        preview.style.border = (layout.border_width || 0) + 'px solid ' + (layout.border_color || '#000');
        preview.style.borderRadius = (layout.border_radius || 0) + 'px';
        preview.style.fontFamily = layout.font_family || 'Arial, sans-serif';
        preview.style.display = 'flex';
        preview.style.flexDirection = 'column';
        preview.style.position = 'relative';

        // Clear and rebuild inner content
        preview.innerHTML = '';
        var inner = document.createElement('div');
        inner.className = 'sign-inner';
        inner.style.flex = '1';
        inner.style.minHeight = '0';
        inner.style.width = '100%';
        inner.style.boxSizing = 'border-box';
        inner.style.padding = ((layout.padding || 3) * zoom / 3.78) + 'px';
        inner.style.display = 'flex';
        inner.style.flexDirection = 'column';
        inner.style.justifyContent = 'center';
        inner.style.alignItems = 'center';
        inner.style.textAlign = layout.text_align || 'center';
        inner.style.overflow = 'hidden';
        inner.style.position = 'relative';
        inner.style.zIndex = '1';

        // Scale factor: designer uses px at zoom level, real sign uses mm
        var sf = zoom / 3.78; // ratio to approximate mm-to-px scaling

        if (currentType === 'simple') renderSimplePreview(inner, sf);
        else if (currentType === 'promotional') renderPromotionalPreview(inner, sf);
        else if (currentType === 'bulk') renderBulkPreview(inner, sf);
        else if (currentType === 'weight') renderWeightPreview(inner, sf);

        preview.appendChild(inner);

        // Watermark
        if (layout.bg_watermark_show && layout.bg_watermark) {
            var wm = el('div', 'sign-watermark', layout.bg_watermark);
            wm.setAttribute('aria-hidden', 'true');
            preview.appendChild(wm);
        }
        // Corner icons
        ['tl','tr','bl','br'].forEach(function (pos) {
            var icon = layout['corner_' + pos];
            if (icon) {
                var span = el('span', 'sign-corner-icon sign-corner-' + pos, icon);
                span.setAttribute('aria-hidden', 'true');
                preview.appendChild(span);
            }
        });

        // Auto-fit text in preview
        setTimeout(function () { autoFitPreview(); }, 10);
    }

    function renderSimplePreview(inner, sf) {
        if (layout.show_store_name) {
            var sh = el('div', 'store-header', layout.store_name || 'CHE GOLOSO');
            sh.style.backgroundColor = layout.store_name_bg || '#333';
            sh.style.color = layout.store_name_color || '#fff';
            sh.style.fontSize = ((layout.store_name_size || 8) * sf) + 'px';
            inner.appendChild(sh);
        }

        var name = el('div', 'product-name fit-text-multi', 'SALADIX');
        name.style.fontSize = ((layout.product_name_size || 14) * sf) + 'px';
        name.style.fontWeight = layout.product_name_weight || 'bold';
        name.style.color = layout.product_name_color || '#000';
        inner.appendChild(name);

        if (layout.gramaje_show !== false) {
            var gr = el('div', 'gramaje', '100g');
            gr.style.fontSize = ((layout.gramaje_size || 9) * sf) + 'px';
            gr.style.color = layout.gramaje_color || '#666';
            inner.appendChild(gr);
        }

        var price = el('div', 'price fit-text', '$790');
        price.style.fontSize = ((layout.price_size || 32) * sf) + 'px';
        price.style.fontWeight = layout.price_weight || 'bold';
        price.style.color = layout.price_color || '#27ae60';
        inner.appendChild(price);
    }

    function renderPromotionalPreview(inner, sf) {
        if (layout.promo_label_show !== false) {
            var label = el('div', 'promo-label', layout.promo_label_text || 'PROMO!!');
            label.style.backgroundColor = layout.promo_label_bg || '#FFD700';
            label.style.color = layout.promo_label_color || '#cc0000';
            label.style.fontSize = ((layout.promo_label_size || 12) * sf) + 'px';
            inner.appendChild(label);
        }

        var name = el('div', 'product-name fit-text-multi', 'TURRÓN MISKY');
        name.style.fontSize = ((layout.product_name_size || 12) * sf) + 'px';
        name.style.fontWeight = layout.product_name_weight || 'bold';
        name.style.color = layout.product_name_color || '#fff';
        inner.appendChild(name);

        var up = el('div', 'unit-price', '$180');
        up.style.fontSize = ((layout.unit_price_size || 14) * sf) + 'px';
        up.style.color = layout.unit_price_color || '#fff';
        inner.appendChild(up);

        var badge = el('div', 'promo-badge fit-text', '3 X');
        badge.style.fontSize = ((layout.promo_badge_size || 24) * sf) + 'px';
        badge.style.color = layout.promo_badge_color || '#FFD700';
        inner.appendChild(badge);

        var pp = el('div', 'price fit-text', '$500');
        pp.style.fontSize = ((layout.promo_price_size || 28) * sf) + 'px';
        pp.style.fontWeight = layout.promo_price_weight || 'bold';
        pp.style.color = layout.promo_price_color || '#fff';
        inner.appendChild(pp);
    }

    function renderBulkPreview(inner, sf) {
        var name = el('div', 'product-name fit-text-multi', 'FEELING');
        name.style.fontSize = ((layout.product_name_size || 16) * sf) + 'px';
        name.style.fontWeight = layout.product_name_weight || 'bold';
        name.style.color = layout.product_name_color || '#000';
        inner.appendChild(name);

        var price = el('div', 'price fit-text', '$11.500');
        price.style.fontSize = ((layout.total_price_size || 28) * sf) + 'px';
        price.style.fontWeight = layout.total_price_weight || 'bold';
        price.style.color = layout.total_price_color || '#e74c3c';
        inner.appendChild(price);

        var pkg = el('div', 'package-info fit-text', 'CAJA X 30U.');
        pkg.style.fontSize = ((layout.package_info_size || 12) * sf) + 'px';
        pkg.style.color = layout.package_info_color || '#2c3e50';
        pkg.style.fontWeight = layout.package_info_weight || 'bold';
        inner.appendChild(pkg);
    }

    function renderWeightPreview(inner, sf) {
        var name = el('div', 'product-name fit-text-multi', 'ALMENDRAS PELADAS');
        name.style.fontSize = ((layout.product_name_size || 14) * sf) + 'px';
        name.style.fontWeight = layout.product_name_weight || 'bold';
        name.style.color = layout.product_name_color || '#000';
        inner.appendChild(name);

        if (layout.show_dividers !== false) {
            var div1 = document.createElement('div');
            div1.className = 'divider';
            div1.style.borderColor = layout.divider_color || '#ccc';
            inner.appendChild(div1);
        }

        var row = document.createElement('div');
        row.className = 'weight-row';

        var prices = [
            { val: '$3.200', label: '100 gr', size: layout.price_100g_size || 12, color: layout.price_100g_color || '#000', weight: 'normal' },
            { val: '$7.350', label: '¼ Kg', size: layout.price_250g_size || 14, color: layout.price_250g_color || '#000', weight: 'normal' },
            { val: '$29.400', label: 'Kg', size: layout.price_1kg_size || 20, color: layout.price_1kg_color || '#e74c3c', weight: layout.price_1kg_weight || 'bold' },
        ];

        prices.forEach(function (p) {
            var cell = document.createElement('div');
            cell.className = 'weight-cell';
            cell.innerHTML =
                '<span class="weight-label" style="font-size:' + (p.size * sf * 0.5) + 'px;">' + p.label + '</span>' +
                '<span class="fit-text" style="font-size:' + (p.size * sf) + 'px;color:' + p.color + ';font-weight:' + p.weight + ';">' + p.val + '</span>';
            row.appendChild(cell);
        });

        inner.appendChild(row);
    }

    // ====================== AUTO-FIT TEXT ======================
    function autoFitPreview() {
        preview.querySelectorAll('.fit-text').forEach(function (txt) {
            var parent = txt.closest('.sign-inner') || preview;
            var maxW = parent.clientWidth - 8;
            var fontSize = parseFloat(window.getComputedStyle(txt).fontSize);
            var minSize = 6;
            var iterations = 0;
            while (txt.scrollWidth > maxW && fontSize > minSize && iterations < 50) {
                fontSize -= 0.5;
                txt.style.fontSize = fontSize + 'px';
                iterations++;
            }
        });
    }

    // ====================== ZOOM ======================
    function updateZoom() {
        document.getElementById('zoomLabel').textContent = Math.round(zoom / 3.78 * 100) + '%';
        renderPreview();
    }

    // ====================== HELPERS ======================
    function el(tag, cls, text) {
        var e = document.createElement(tag);
        e.className = cls;
        if (text) e.textContent = text;
        return e;
    }

    function getDefaultDims(type) {
        var dims = {
            simple: [50, 40],
            promotional: [70, 50],
            bulk: [100, 70],
            weight: [100, 70],
        };
        return dims[type] || [50, 40];
    }

})();
