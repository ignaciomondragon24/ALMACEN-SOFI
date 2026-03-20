/**
 * CHE GOLOSO - Visual Sign Designer (Canva-style)
 * Full drag-and-drop editor for creating price sign templates.
 */

/* ============================================================
   CONSTANTS & PRESETS
   ============================================================ */

const PX_PER_MM = 4; // Pixels per mm in designer canvas (bigger = more detail)
const MIN_ELEMENT_SIZE = 3; // mm
const GRID_SNAP = 0.5; // mm
const HANDLE_NAMES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

const DEFAULT_PROPS = {
    text: {
        type: 'text', x: 5, y: 5, width: 30, height: 8,
        content: 'Texto', fontFamily: 'Arial', fontSize: 14,
        fontWeight: 'bold', fontStyle: 'normal', textDecoration: 'none',
        color: '#000000', backgroundColor: 'transparent', textAlign: 'center',
        verticalAlign: 'middle', autoScale: false, minFontSize: 6, zIndex: 10,
    },
    variable: {
        type: 'variable', x: 5, y: 5, width: 35, height: 10,
        variable: '', fontFamily: 'Arial Black', fontSize: 20,
        fontWeight: 'bold', fontStyle: 'normal', textDecoration: 'none',
        color: '#E91E8C', backgroundColor: 'transparent', textAlign: 'center',
        verticalAlign: 'middle', autoScale: true, minFontSize: 6, zIndex: 10,
    },
    shape: {
        type: 'shape', x: 5, y: 5, width: 25, height: 15,
        backgroundColor: '#E91E8C', borderColor: '#000000',
        borderWidth: 0, borderRadius: 0, opacity: 1, zIndex: 5,
    },
    line: {
        type: 'line', x: 5, y: 20, width: 40, height: 0.5,
        lineColor: '#000000', lineWidth: 0.5, lineStyle: 'solid', zIndex: 5,
    },
};

/** Preset layouts for each sign type */
const PRESET_LAYOUTS = {
    simple: {
        background_color: '#FFFFFF',
        border_color: '#333333',
        border_width: 0.3,
        elements: [
            { id: 'el_1', type: 'variable', variable: 'nombre_producto',
              x: 2, y: 2, width: 46, height: 14,
              fontFamily: 'Arial Black', fontSize: 14, fontWeight: 'bold',
              color: '#000000', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 7, zIndex: 10 },
            { id: 'el_2', type: 'variable', variable: 'gramaje',
              x: 15, y: 15, width: 20, height: 5,
              fontFamily: 'Arial', fontSize: 9, fontWeight: 'normal',
              fontStyle: 'italic', color: '#666666', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 6, zIndex: 10 },
            { id: 'el_3', type: 'variable', variable: 'precio_unitario',
              x: 3, y: 21, width: 44, height: 16,
              fontFamily: 'Arial Black', fontSize: 28, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 12, zIndex: 10 },
        ]
    },
    promo: {
        background_color: '#FFFFFF',
        border_color: '#E91E8C',
        border_width: 0.5,
        elements: [
            { id: 'el_1', type: 'variable', variable: 'etiqueta_promo',
              x: 0, y: 0, width: 70, height: 10,
              fontFamily: 'Impact', fontSize: 14, fontWeight: 'bold',
              color: '#FFFFFF', backgroundColor: '#E91E8C',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_2', type: 'variable', variable: 'nombre_producto',
              x: 3, y: 12, width: 64, height: 10,
              fontFamily: 'Arial Black', fontSize: 13, fontWeight: 'bold',
              color: '#000000', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_3', type: 'variable', variable: 'precio_unitario',
              x: 3, y: 22, width: 30, height: 8,
              fontFamily: 'Arial', fontSize: 10, fontWeight: 'normal',
              color: '#666666', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 7, zIndex: 10 },
            { id: 'el_4', type: 'text', content: 'X',
              x: 12, y: 31, width: 8, height: 14,
              fontFamily: 'Arial Black', fontSize: 16, fontWeight: 'bold',
              color: '#2D1E5F', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: false, zIndex: 10 },
            { id: 'el_5', type: 'variable', variable: 'cantidad_promo',
              x: 3, y: 31, width: 12, height: 14,
              fontFamily: 'Impact', fontSize: 26, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'right', verticalAlign: 'middle',
              autoScale: true, minFontSize: 14, zIndex: 10 },
            { id: 'el_6', type: 'variable', variable: 'precio_promo',
              x: 20, y: 31, width: 47, height: 14,
              fontFamily: 'Impact', fontSize: 26, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 14, zIndex: 10 },
        ]
    },
    bulk: {
        background_color: '#FFFFFF',
        border_color: '#F5D000',
        border_width: 0.5,
        elements: [
            { id: 'el_1', type: 'variable', variable: 'nombre_producto',
              x: 3, y: 3, width: 94, height: 16,
              fontFamily: 'Arial Black', fontSize: 16, fontWeight: 'bold',
              color: '#000000', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 9, zIndex: 10 },
            { id: 'el_2', type: 'variable', variable: 'precio_total',
              x: 5, y: 22, width: 90, height: 26,
              fontFamily: 'Impact', fontSize: 36, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 16, zIndex: 10 },
            { id: 'el_3', type: 'shape',
              x: 10, y: 52, width: 80, height: 14,
              backgroundColor: '#F5D000', borderColor: 'transparent',
              borderWidth: 0, borderRadius: 2, zIndex: 5 },
            { id: 'el_4', type: 'variable', variable: 'tipo_empaque',
              x: 12, y: 53, width: 30, height: 12,
              fontFamily: 'Arial Black', fontSize: 12, fontWeight: 'bold',
              color: '#2D1E5F', backgroundColor: 'transparent',
              textAlign: 'right', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_5', type: 'variable', variable: 'contenido_empaque',
              x: 44, y: 53, width: 44, height: 12,
              fontFamily: 'Arial Black', fontSize: 12, fontWeight: 'bold',
              color: '#2D1E5F', backgroundColor: 'transparent',
              textAlign: 'left', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
        ]
    },
    weight: {
        background_color: '#FFFFFF',
        border_color: '#28a745',
        border_width: 0.5,
        elements: [
            { id: 'el_1', type: 'variable', variable: 'nombre_producto',
              x: 3, y: 3, width: 94, height: 14,
              fontFamily: 'Arial Black', fontSize: 14, fontWeight: 'bold',
              color: '#000000', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_2', type: 'line',
              x: 5, y: 18, width: 90, height: 0.5,
              lineColor: '#28a745', lineWidth: 0.3, lineStyle: 'solid', zIndex: 5 },
            { id: 'el_3', type: 'text', content: '100 GR',
              x: 3, y: 20, width: 30, height: 8,
              fontFamily: 'Arial', fontSize: 8, fontWeight: 'bold',
              color: '#666666', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: false, zIndex: 10 },
            { id: 'el_4', type: 'variable', variable: 'precio_100g',
              x: 3, y: 28, width: 30, height: 14,
              fontFamily: 'Arial Black', fontSize: 16, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_5', type: 'text', content: '¼ Kg',
              x: 35, y: 20, width: 30, height: 8,
              fontFamily: 'Arial', fontSize: 8, fontWeight: 'bold',
              color: '#666666', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: false, zIndex: 10 },
            { id: 'el_6', type: 'variable', variable: 'precio_250g',
              x: 35, y: 28, width: 30, height: 14,
              fontFamily: 'Arial Black', fontSize: 16, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 8, zIndex: 10 },
            { id: 'el_7', type: 'text', content: 'Kg',
              x: 67, y: 20, width: 30, height: 8,
              fontFamily: 'Arial', fontSize: 8, fontWeight: 'bold',
              color: '#666666', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: false, zIndex: 10 },
            { id: 'el_8', type: 'variable', variable: 'precio_1kg',
              x: 67, y: 28, width: 30, height: 14,
              fontFamily: 'Impact', fontSize: 20, fontWeight: 'bold',
              color: '#E91E8C', backgroundColor: 'transparent',
              textAlign: 'center', verticalAlign: 'middle',
              autoScale: true, minFontSize: 10, zIndex: 10 },
            { id: 'el_9', type: 'shape',
              x: 66, y: 19, width: 32, height: 24,
              backgroundColor: 'rgba(40,167,69,0.08)', borderColor: '#28a745',
              borderWidth: 0.3, borderRadius: 1, zIndex: 3 },
        ]
    },
};


/* ============================================================
   SignageDesigner CLASS
   ============================================================ */

class SignageDesigner {
    constructor(config) {
        this.config = config;
        this.elements = [];
        this.selectedId = null;
        this.zoom = 1;
        this.isDragging = false;
        this.isResizing = false;
        this.history = [];
        this.historyIdx = -1;
        this.maxHistory = 50;
        this._idCounter = 0;
        this._unsaved = false;

        this.canvas = document.getElementById('canvasSign');
        this.canvasArea = document.getElementById('canvasArea');
        this.wrapper = document.getElementById('canvasWrapper');

        this.init();
    }

    /* ----------------------------------------------------------
       INIT
       ---------------------------------------------------------- */
    init() {
        this._setupCanvas();
        this._setupVariableList();
        this._setupPalette();
        this._setupPropertyListeners();
        this._setupToolbar();
        this._setupKeyboard();
        this._setupSignBgControls();
        this._loadLayout();
        this._fitToView();
    }

    _setupCanvas() {
        const w = this.config.widthMM * PX_PER_MM;
        const h = this.config.heightMM * PX_PER_MM;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';

        // Click on canvas empty space = deselect
        this.canvas.addEventListener('mousedown', e => {
            if (e.target === this.canvas) this.deselectAll();
        });

        // Global mouse events for drag/resize
        document.addEventListener('mousemove', e => this._onMouseMove(e));
        document.addEventListener('mouseup', e => this._onMouseUp(e));
    }

    _setupVariableList() {
        const list = document.getElementById('variableList');
        if (!list) return;
        list.innerHTML = '';
        this.config.variables.forEach(v => {
            const item = document.createElement('div');
            item.className = 'var-item';
            item.innerHTML = `<span class="var-key">{${v.key}}</span> <span>${v.label}</span>`;
            item.addEventListener('click', () => this.addVariable(v.key));
            list.appendChild(item);
        });
    }

    _setupPalette() {
        document.querySelectorAll('.palette-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                if (type === 'variable') {
                    this._showVariablePicker();
                } else {
                    this.addElement(type);
                }
            });
        });
    }

    _showVariablePicker() {
        const list = document.getElementById('variablePickerList');
        if (!list) return;
        list.innerHTML = '';
        this.config.variables.forEach(v => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action';
            item.href = '#';
            item.innerHTML = `<strong>{${v.key}}</strong><br><small class="text-muted">${v.label} — ej: ${v.sample}</small>`;
            item.addEventListener('click', e => {
                e.preventDefault();
                this.addVariable(v.key);
                bootstrap.Modal.getInstance(document.getElementById('variablePickerModal')).hide();
            });
            list.appendChild(item);
        });
        new bootstrap.Modal(document.getElementById('variablePickerModal')).show();
    }

    _setupToolbar() {
        const $ = id => document.getElementById(id);
        $('btnSave').addEventListener('click', () => this.save());
        $('btnUndo').addEventListener('click', () => this.undo());
        $('btnRedo').addEventListener('click', () => this.redo());
        $('btnZoomIn').addEventListener('click', () => this.setZoom(this.zoom + 0.25));
        $('btnZoomOut').addEventListener('click', () => this.setZoom(this.zoom - 0.25));
        $('btnFitView').addEventListener('click', () => this._fitToView());
        $('btnPreview').addEventListener('click', () => this.showPreview());
        $('btnLoadPreset').addEventListener('click', () => this.loadPreset());

        $('btnDuplicate').addEventListener('click', () => this.duplicateSelected());
        $('btnDeleteEl').addEventListener('click', () => this.deleteSelected());
        $('btnBringForward').addEventListener('click', () => this.changeZIndex(1));
        $('btnSendBackward').addEventListener('click', () => this.changeZIndex(-1));
    }

    _setupKeyboard() {
        document.addEventListener('keydown', e => {
            // Don't intercept when editing inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                this.deleteSelected();
            } else if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                this.undo();
            } else if (e.ctrlKey && e.key === 'y') {
                e.preventDefault();
                this.redo();
            } else if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.save();
            } else if (e.ctrlKey && e.key === 'd') {
                e.preventDefault();
                this.duplicateSelected();
            } else if (e.key === 'Escape') {
                this.deselectAll();
            }
            // Arrow keys to nudge
            const sel = this._getSelected();
            if (sel && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                e.preventDefault();
                const step = e.shiftKey ? 5 : 0.5;
                if (e.key === 'ArrowUp') sel.y = Math.max(0, sel.y - step);
                if (e.key === 'ArrowDown') sel.y = Math.min(this.config.heightMM - sel.height, sel.y + step);
                if (e.key === 'ArrowLeft') sel.x = Math.max(0, sel.x - step);
                if (e.key === 'ArrowRight') sel.x = Math.min(this.config.widthMM - sel.width, sel.x + step);
                this._renderElement(sel);
                this._updateProperties();
                this._pushHistory();
            }
        });
    }

    _setupSignBgControls() {
        const bgInput = document.getElementById('propSignBg');
        const borderInput = document.getElementById('propSignBorderWidth');
        if (bgInput) {
            bgInput.addEventListener('input', () => {
                this._signBgColor = bgInput.value;
                this.canvas.style.background = bgInput.value;
                this._pushHistory();
            });
        }
        if (borderInput) {
            borderInput.addEventListener('change', () => {
                this._signBorderWidth = parseFloat(borderInput.value) || 0;
                if (this._signBorderWidth > 0) {
                    this.canvas.style.border = (this._signBorderWidth * PX_PER_MM * this.zoom) + 'px solid ' + (this._signBorderColor || '#333');
                } else {
                    this.canvas.style.border = 'none';
                }
                this._pushHistory();
            });
        }
    }

    /* ----------------------------------------------------------
       ELEMENT MANAGEMENT
       ---------------------------------------------------------- */
    _genId() {
        return 'el_' + Date.now() + '_' + (++this._idCounter);
    }

    addElement(type, overrides = {}) {
        const defaults = JSON.parse(JSON.stringify(DEFAULT_PROPS[type]));
        const el = { ...defaults, id: this._genId(), ...overrides };

        // Center in visible area
        const vw = this.config.widthMM;
        const vh = this.config.heightMM;
        if (!overrides.x) el.x = Math.max(0, (vw - el.width) / 2);
        if (!overrides.y) el.y = Math.max(0, (vh - el.height) / 2);

        el.zIndex = (this.elements.length + 1) * 10;
        this.elements.push(el);
        this._renderElement(el);
        this.selectElement(el.id);
        this._pushHistory();
        this._updateStatus();
        return el;
    }

    addVariable(varKey) {
        const varInfo = this.config.variables.find(v => v.key === varKey);
        if (!varInfo) return;
        return this.addElement('variable', {
            variable: varKey,
            content: varInfo.sample,
        });
    }

    deleteSelected() {
        if (!this.selectedId) return;
        const domEl = this.canvas.querySelector(`[data-id="${this.selectedId}"]`);
        if (domEl) domEl.remove();
        this.elements = this.elements.filter(e => e.id !== this.selectedId);
        this.selectedId = null;
        this._showPropertiesPanel(false);
        this._pushHistory();
        this._updateStatus();
    }

    duplicateSelected() {
        const sel = this._getSelected();
        if (!sel) return;
        const copy = JSON.parse(JSON.stringify(sel));
        copy.id = this._genId();
        copy.x = Math.min(copy.x + 3, this.config.widthMM - copy.width);
        copy.y = Math.min(copy.y + 3, this.config.heightMM - copy.height);
        this.elements.push(copy);
        this._renderElement(copy);
        this.selectElement(copy.id);
        this._pushHistory();
    }

    changeZIndex(delta) {
        const sel = this._getSelected();
        if (!sel) return;
        sel.zIndex = Math.max(1, (sel.zIndex || 10) + delta * 10);
        this._renderElement(sel);
        this._pushHistory();
    }

    /* ----------------------------------------------------------
       RENDERING
       ---------------------------------------------------------- */
    _renderElement(el) {
        let dom = this.canvas.querySelector(`[data-id="${el.id}"]`);
        if (!dom) {
            dom = document.createElement('div');
            dom.className = 'dsg-element';
            dom.dataset.id = el.id;
            dom.dataset.type = el.type;
            this.canvas.appendChild(dom);

            dom.addEventListener('mousedown', e => {
                e.stopPropagation();
                this.selectElement(el.id);
                this._startDrag(el, e);
            });

            dom.addEventListener('dblclick', e => {
                if (el.type === 'text') this._startInlineEdit(el, dom);
            });
        }

        const px = PX_PER_MM;
        dom.style.left = (el.x * px) + 'px';
        dom.style.top = (el.y * px) + 'px';
        dom.style.width = (el.width * px) + 'px';
        dom.style.height = (el.height * px) + 'px';
        dom.style.zIndex = el.zIndex || 10;

        // Render content based on type
        if (el.type === 'text' || el.type === 'variable') {
            dom.className = 'dsg-element dsg-element-text';
            if (this.selectedId === el.id) dom.classList.add('selected');

            let text = el.type === 'variable'
                ? (this.config.variables.find(v => v.key === el.variable) || {}).sample || `{${el.variable}}`
                : (el.content || 'Texto');

            dom.style.fontFamily = el.fontFamily || 'Arial';
            dom.style.fontSize = (el.fontSize || 14) + 'pt';
            dom.style.fontWeight = el.fontWeight || 'normal';
            dom.style.fontStyle = el.fontStyle || 'normal';
            dom.style.textDecoration = el.textDecoration || 'none';
            dom.style.color = el.color || '#000';
            dom.style.textAlign = el.textAlign || 'center';
            dom.style.justifyContent = el.textAlign === 'left' ? 'flex-start' :
                                       el.textAlign === 'right' ? 'flex-end' : 'center';
            dom.style.alignItems = el.verticalAlign === 'top' ? 'flex-start' :
                                   el.verticalAlign === 'bottom' ? 'flex-end' : 'center';

            if (el.backgroundColor && el.backgroundColor !== 'transparent') {
                dom.style.backgroundColor = el.backgroundColor;
            } else {
                dom.style.backgroundColor = 'transparent';
            }

            // Set text content
            let span = dom.querySelector('span');
            if (!span) {
                dom.innerHTML = '';
                span = document.createElement('span');
                dom.appendChild(span);
            }
            span.style.width = '100%';
            span.style.textAlign = el.textAlign || 'center';
            span.style.lineHeight = '1.15';
            span.style.wordBreak = 'break-word';
            span.textContent = text;

        } else if (el.type === 'shape') {
            dom.className = 'dsg-element';
            if (this.selectedId === el.id) dom.classList.add('selected');
            dom.innerHTML = '';
            dom.style.backgroundColor = el.backgroundColor || '#E91E8C';
            if (el.borderWidth > 0) {
                dom.style.border = (el.borderWidth * px) + 'px solid ' + (el.borderColor || '#000');
            } else {
                dom.style.border = 'none';
            }
            dom.style.borderRadius = (el.borderRadius || 0) * px + 'px';
            dom.style.opacity = el.opacity !== undefined ? el.opacity : 1;

        } else if (el.type === 'line') {
            dom.className = 'dsg-element';
            if (this.selectedId === el.id) dom.classList.add('selected');
            dom.innerHTML = '';
            dom.style.backgroundColor = 'transparent';
            dom.style.borderTop = (el.lineWidth || 0.5) * px + 'px ' +
                (el.lineStyle || 'solid') + ' ' + (el.lineColor || '#000');
        }

        // Update resize handles if selected
        if (this.selectedId === el.id) {
            this._showHandles(dom);
        }
    }

    _renderAll() {
        // Clear canvas
        this.canvas.querySelectorAll('.dsg-element').forEach(el => el.remove());
        this.elements.forEach(el => this._renderElement(el));
        // Apply sign background
        this.canvas.style.background = this._signBgColor || '#FFFFFF';
        if (this._signBorderWidth > 0) {
            this.canvas.style.border = (this._signBorderWidth * PX_PER_MM * this.zoom) + 'px solid ' + (this._signBorderColor || '#333');
        }
        if (this.selectedId) {
            const dom = this.canvas.querySelector(`[data-id="${this.selectedId}"]`);
            if (dom) dom.classList.add('selected');
        }
        this._updateStatus();
    }

    /* ----------------------------------------------------------
       SELECTION
       ---------------------------------------------------------- */
    selectElement(id) {
        this.deselectAll();
        this.selectedId = id;
        const dom = this.canvas.querySelector(`[data-id="${id}"]`);
        if (dom) {
            dom.classList.add('selected');
            this._showHandles(dom);
        }
        this._updateProperties();
        this._showPropertiesPanel(true);
        this._updateStatus();
    }

    deselectAll() {
        this.canvas.querySelectorAll('.dsg-element.selected').forEach(el => el.classList.remove('selected'));
        this.canvas.querySelectorAll('.resize-handle').forEach(h => h.remove());
        this.selectedId = null;
        this._showPropertiesPanel(false);
        document.getElementById('statusSelected').textContent = '';
    }

    _getSelected() {
        return this.elements.find(e => e.id === this.selectedId);
    }

    _showHandles(dom) {
        // Remove existing handles
        this.canvas.querySelectorAll('.resize-handle').forEach(h => h.remove());

        HANDLE_NAMES.forEach(name => {
            const h = document.createElement('div');
            h.className = `resize-handle resize-handle-${name}`;
            h.dataset.handle = name;
            h.addEventListener('mousedown', e => {
                e.stopPropagation();
                this._startResize(this._getSelected(), name, e);
            });
            dom.appendChild(h);
        });
    }

    /* ----------------------------------------------------------
       DRAG & DROP
       ---------------------------------------------------------- */
    _startDrag(el, e) {
        this.isDragging = true;
        this._dragEl = el;
        this._dragStartX = e.clientX;
        this._dragStartY = e.clientY;
        this._dragOrigX = el.x;
        this._dragOrigY = el.y;
        document.body.style.cursor = 'move';
    }

    _startResize(el, handle, e) {
        if (!el) return;
        this.isResizing = true;
        this._resizeEl = el;
        this._resizeHandle = handle;
        this._resizeStartX = e.clientX;
        this._resizeStartY = e.clientY;
        this._resizeOrig = { x: el.x, y: el.y, w: el.width, h: el.height };
        document.body.style.cursor = handle + '-resize';
    }

    _onMouseMove(e) {
        if (this.isDragging) {
            const el = this._dragEl;
            const px = PX_PER_MM * this.zoom;
            const dx = (e.clientX - this._dragStartX) / px;
            const dy = (e.clientY - this._dragStartY) / px;

            let newX = this._dragOrigX + dx;
            let newY = this._dragOrigY + dy;

            // Snap to grid
            newX = Math.round(newX / GRID_SNAP) * GRID_SNAP;
            newY = Math.round(newY / GRID_SNAP) * GRID_SNAP;

            // Constrain to canvas
            newX = Math.max(0, Math.min(newX, this.config.widthMM - el.width));
            newY = Math.max(0, Math.min(newY, this.config.heightMM - el.height));

            el.x = newX;
            el.y = newY;
            this._renderElement(el);
            this._updateProperties();

        } else if (this.isResizing) {
            const el = this._resizeEl;
            const px = PX_PER_MM * this.zoom;
            const dx = (e.clientX - this._resizeStartX) / px;
            const dy = (e.clientY - this._resizeStartY) / px;
            const orig = this._resizeOrig;
            const handle = this._resizeHandle;

            let { x, y, w, h } = { x: orig.x, y: orig.y, w: orig.w, h: orig.h };

            if (handle.includes('w')) { x += dx; w -= dx; }
            if (handle.includes('e')) { w += dx; }
            if (handle.includes('n')) { y += dy; h -= dy; }
            if (handle.includes('s')) { h += dy; }

            // Enforce minimums
            if (w < MIN_ELEMENT_SIZE) { w = MIN_ELEMENT_SIZE; if (handle.includes('w')) x = orig.x + orig.w - MIN_ELEMENT_SIZE; }
            if (h < MIN_ELEMENT_SIZE) { h = MIN_ELEMENT_SIZE; if (handle.includes('n')) y = orig.y + orig.h - MIN_ELEMENT_SIZE; }

            // Snap
            x = Math.round(x / GRID_SNAP) * GRID_SNAP;
            y = Math.round(y / GRID_SNAP) * GRID_SNAP;
            w = Math.round(w / GRID_SNAP) * GRID_SNAP;
            h = Math.round(h / GRID_SNAP) * GRID_SNAP;

            // Constrain
            x = Math.max(0, x);
            y = Math.max(0, y);

            el.x = x; el.y = y; el.width = w; el.height = h;
            this._renderElement(el);
            this._updateProperties();
        }
    }

    _onMouseUp(e) {
        if (this.isDragging || this.isResizing) {
            this._pushHistory();
        }
        this.isDragging = false;
        this.isResizing = false;
        this._dragEl = null;
        this._resizeEl = null;
        document.body.style.cursor = '';
    }

    /* ----------------------------------------------------------
       INLINE TEXT EDITING
       ---------------------------------------------------------- */
    _startInlineEdit(el, dom) {
        const span = dom.querySelector('span');
        if (!span) return;
        span.contentEditable = 'true';
        span.focus();

        const finish = () => {
            span.contentEditable = 'false';
            el.content = span.textContent;
            this._updateProperties();
            this._pushHistory();
        };

        span.addEventListener('blur', finish, { once: true });
        span.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); span.blur(); }
            if (e.key === 'Escape') { span.textContent = el.content; span.blur(); }
        });
    }

    /* ----------------------------------------------------------
       PROPERTIES PANEL
       ---------------------------------------------------------- */
    _showPropertiesPanel(show) {
        document.getElementById('noSelection').style.display = show ? 'none' : 'block';
        document.getElementById('elementProperties').style.display = show ? 'block' : 'none';
    }

    _updateProperties() {
        const el = this._getSelected();
        if (!el) return;

        const $ = id => document.getElementById(id);

        // Position
        $('propX').value = el.x.toFixed(1);
        $('propY').value = el.y.toFixed(1);
        $('propW').value = el.width.toFixed(1);
        $('propH').value = el.height.toFixed(1);

        // Show/hide type-specific panels
        const isText = el.type === 'text' || el.type === 'variable';
        $('textProps').style.display = isText ? 'block' : 'none';
        $('variableProps').style.display = el.type === 'variable' ? 'block' : 'none';
        $('shapeProps').style.display = el.type === 'shape' ? 'block' : 'none';
        $('lineProps').style.display = el.type === 'line' ? 'block' : 'none';
        $('contentProps').style.display = el.type === 'text' ? 'block' : 'none';

        if (isText) {
            $('propFontFamily').value = el.fontFamily || 'Arial';
            $('propFontSize').value = el.fontSize || 14;
            $('propMinFontSize').value = el.minFontSize || 6;
            $('propColor').value = el.color || '#000000';

            const bg = el.backgroundColor || 'transparent';
            $('propBgTransparent').checked = bg === 'transparent';
            $('propBgColor').value = bg === 'transparent' ? '#ffffff' : bg;
            $('propBgColor').disabled = bg === 'transparent';

            $('propAutoScale').checked = !!el.autoScale;

            // Toggle buttons
            $('propBold').classList.toggle('active', el.fontWeight === 'bold');
            $('propItalic').classList.toggle('active', el.fontStyle === 'italic');
            $('propUnderline').classList.toggle('active', el.textDecoration === 'underline');

            // Alignment
            document.querySelectorAll('.prop-align').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.align === (el.textAlign || 'center'));
            });

            if (el.type === 'text') {
                $('propContent').value = el.content || '';
            }

            if (el.type === 'variable') {
                const sel = $('propVariable');
                sel.innerHTML = '';
                this.config.variables.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.key;
                    opt.textContent = `${v.label} (${v.key})`;
                    sel.appendChild(opt);
                });
                sel.value = el.variable || '';
            }
        }

        if (el.type === 'shape') {
            $('propShapeBg').value = el.backgroundColor || '#E91E8C';
            $('propShapeBorder').value = el.borderColor || '#000000';
            $('propShapeBorderWidth').value = el.borderWidth || 0;
            $('propShapeRadius').value = el.borderRadius || 0;
        }

        if (el.type === 'line') {
            $('propLineColor').value = el.lineColor || '#000000';
            $('propLineWidth').value = el.lineWidth || 0.5;
        }

        // Status
        const typeLabels = { text: 'Texto', variable: 'Variable', shape: 'Forma', line: 'Línea' };
        document.getElementById('statusSelected').textContent =
            `Selección: ${typeLabels[el.type] || el.type}${el.variable ? ' (' + el.variable + ')' : ''}`;
    }

    _setupPropertyListeners() {
        const $ = id => document.getElementById(id);
        const update = (setter) => {
            const el = this._getSelected();
            if (!el) return;
            setter(el);
            this._renderElement(el);
            this._pushHistory();
        };

        // Position & Size
        ['propX', 'propY', 'propW', 'propH'].forEach(id => {
            $(id).addEventListener('change', () => update(el => {
                if (id === 'propX') el.x = parseFloat($(id).value) || 0;
                if (id === 'propY') el.y = parseFloat($(id).value) || 0;
                if (id === 'propW') el.width = Math.max(MIN_ELEMENT_SIZE, parseFloat($(id).value) || MIN_ELEMENT_SIZE);
                if (id === 'propH') el.height = Math.max(MIN_ELEMENT_SIZE, parseFloat($(id).value) || MIN_ELEMENT_SIZE);
            }));
        });

        // Font
        $('propFontFamily').addEventListener('change', () => update(el => { el.fontFamily = $('propFontFamily').value; }));
        $('propFontSize').addEventListener('change', () => update(el => { el.fontSize = parseInt($('propFontSize').value) || 14; }));
        $('propMinFontSize').addEventListener('change', () => update(el => { el.minFontSize = parseInt($('propMinFontSize').value) || 6; }));
        $('propColor').addEventListener('input', () => update(el => { el.color = $('propColor').value; }));
        $('propBgColor').addEventListener('input', () => update(el => { el.backgroundColor = $('propBgColor').value; }));
        $('propBgTransparent').addEventListener('change', () => update(el => {
            if ($('propBgTransparent').checked) {
                el.backgroundColor = 'transparent';
                $('propBgColor').disabled = true;
            } else {
                el.backgroundColor = $('propBgColor').value || '#ffffff';
                $('propBgColor').disabled = false;
            }
        }));
        $('propAutoScale').addEventListener('change', () => update(el => { el.autoScale = $('propAutoScale').checked; }));

        // Toggle buttons (bold, italic, underline)
        $('propBold').addEventListener('click', () => update(el => {
            el.fontWeight = el.fontWeight === 'bold' ? 'normal' : 'bold';
        }));
        $('propItalic').addEventListener('click', () => update(el => {
            el.fontStyle = el.fontStyle === 'italic' ? 'normal' : 'italic';
        }));
        $('propUnderline').addEventListener('click', () => update(el => {
            el.textDecoration = el.textDecoration === 'underline' ? 'none' : 'underline';
        }));

        // Alignment
        document.querySelectorAll('.prop-align').forEach(btn => {
            btn.addEventListener('click', () => update(el => {
                el.textAlign = btn.dataset.align;
            }));
        });

        // Content
        $('propContent').addEventListener('input', () => update(el => {
            el.content = $('propContent').value;
        }));

        // Variable selection
        $('propVariable').addEventListener('change', () => update(el => {
            el.variable = $('propVariable').value;
        }));

        // Shape props
        $('propShapeBg').addEventListener('input', () => update(el => { el.backgroundColor = $('propShapeBg').value; }));
        $('propShapeBorder').addEventListener('input', () => update(el => { el.borderColor = $('propShapeBorder').value; }));
        $('propShapeBorderWidth').addEventListener('change', () => update(el => { el.borderWidth = parseFloat($('propShapeBorderWidth').value) || 0; }));
        $('propShapeRadius').addEventListener('change', () => update(el => { el.borderRadius = parseInt($('propShapeRadius').value) || 0; }));

        // Line props
        $('propLineColor').addEventListener('input', () => update(el => { el.lineColor = $('propLineColor').value; }));
        $('propLineWidth').addEventListener('change', () => update(el => { el.lineWidth = parseFloat($('propLineWidth').value) || 0.5; }));
    }

    /* ----------------------------------------------------------
       ZOOM
       ---------------------------------------------------------- */
    setZoom(level) {
        this.zoom = Math.max(0.25, Math.min(4, level));
        this.wrapper.style.transform = `scale(${this.zoom})`;
        document.getElementById('zoomLevel').textContent = Math.round(this.zoom * 100) + '%';
    }

    _fitToView() {
        const area = this.canvasArea;
        const aw = area.clientWidth - 60;
        const ah = area.clientHeight - 60;
        const cw = this.config.widthMM * PX_PER_MM;
        const ch = this.config.heightMM * PX_PER_MM;
        const scale = Math.min(aw / cw, ah / ch, 3);
        this.setZoom(scale);
    }

    /* ----------------------------------------------------------
       HISTORY (UNDO/REDO)
       ---------------------------------------------------------- */
    _pushHistory() {
        this._unsaved = true;
        const state = JSON.stringify({
            elements: this.elements,
            bgColor: this._signBgColor,
            borderWidth: this._signBorderWidth,
            borderColor: this._signBorderColor,
        });
        // Remove future states
        this.history = this.history.slice(0, this.historyIdx + 1);
        this.history.push(state);
        if (this.history.length > this.maxHistory) this.history.shift();
        this.historyIdx = this.history.length - 1;
    }

    undo() {
        if (this.historyIdx <= 0) return;
        this.historyIdx--;
        this._restoreHistory();
    }

    redo() {
        if (this.historyIdx >= this.history.length - 1) return;
        this.historyIdx++;
        this._restoreHistory();
    }

    _restoreHistory() {
        const state = JSON.parse(this.history[this.historyIdx]);
        this.elements = state.elements;
        this._signBgColor = state.bgColor;
        this._signBorderWidth = state.borderWidth;
        this._signBorderColor = state.borderColor;
        this.deselectAll();
        this._renderAll();
    }

    /* ----------------------------------------------------------
       SAVE / LOAD
       ---------------------------------------------------------- */
    toJSON() {
        return {
            background_color: this._signBgColor || '#FFFFFF',
            border_color: this._signBorderColor || '#333333',
            border_width: this._signBorderWidth || 0,
            elements: this.elements.map(el => {
                const copy = { ...el };
                return copy;
            }),
        };
    }

    _loadLayout() {
        const layout = this.config.layout;
        if (layout && layout.elements && layout.elements.length > 0) {
            this._signBgColor = layout.background_color || '#FFFFFF';
            this._signBorderColor = layout.border_color || '#333333';
            this._signBorderWidth = layout.border_width || 0;
            this.elements = layout.elements.map(el => ({ ...el }));
        } else {
            this._signBgColor = '#FFFFFF';
            this._signBorderColor = '#333333';
            this._signBorderWidth = 0.3;
            this.elements = [];
        }

        // Set sign bg controls
        const bgInput = document.getElementById('propSignBg');
        if (bgInput) bgInput.value = this._signBgColor;
        const bwInput = document.getElementById('propSignBorderWidth');
        if (bwInput) bwInput.value = this._signBorderWidth;

        this._renderAll();
        this._pushHistory(); // Initial state
    }

    loadPreset() {
        const preset = PRESET_LAYOUTS[this.config.signType];
        if (!preset) return;
        if (this.elements.length > 0 && !confirm('¿Cargar diseño base? Se reemplazarán los elementos actuales.')) return;

        this._signBgColor = preset.background_color || '#FFFFFF';
        this._signBorderColor = preset.border_color || '#333333';
        this._signBorderWidth = preset.border_width || 0;
        this.elements = preset.elements.map(el => ({ ...el, id: this._genId() }));

        const bgInput = document.getElementById('propSignBg');
        if (bgInput) bgInput.value = this._signBgColor;

        this.deselectAll();
        this._renderAll();
        this._pushHistory();
    }

    async save() {
        const btn = document.getElementById('btnSave');
        const origText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Guardando...';
        btn.disabled = true;

        try {
            const name = document.getElementById('templateName').value;
            const body = {
                name: name,
                layout: this.toJSON(),
            };

            const resp = await fetch(this.config.saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.config.csrfToken,
                },
                body: JSON.stringify(body),
            });

            const data = await resp.json();
            if (data.success) {
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Guardado!';
                this._unsaved = false;
                setTimeout(() => { btn.innerHTML = origText; btn.disabled = false; }, 1500);
            } else {
                throw new Error(data.error || 'Error desconocido');
            }
        } catch (err) {
            btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Error';
            setTimeout(() => { btn.innerHTML = origText; btn.disabled = false; }, 2000);
            console.error('Save error:', err);
        }
    }

    /* ----------------------------------------------------------
       PREVIEW
       ---------------------------------------------------------- */
    showPreview() {
        const container = document.getElementById('previewContent');
        container.innerHTML = '';

        const renderer = new SignRenderer();
        const sampleData = renderer.getSampleData(this.config.signType);
        const layout = this.toJSON();

        // Scale to fit modal
        const maxW = 500;
        const maxH = 400;
        const cw = this.config.widthMM * 3.78;
        const ch = this.config.heightMM * 3.78;
        const scale = Math.min(maxW / cw, maxH / ch, 2);

        renderer.render(container, layout, sampleData, this.config.widthMM, this.config.heightMM, scale);

        new bootstrap.Modal(document.getElementById('previewModal')).show();
    }

    /* ----------------------------------------------------------
       UTILS
       ---------------------------------------------------------- */
    _updateStatus() {
        const status = document.getElementById('statusElements');
        if (status) status.textContent = `Elementos: ${this.elements.length}`;
    }
}


/* ============================================================
   INITIALIZATION
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    if (typeof TEMPLATE_CONFIG !== 'undefined') {
        window.designer = new SignageDesigner(TEMPLATE_CONFIG);
    }
});
