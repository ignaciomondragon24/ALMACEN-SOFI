/**
 * POS - Fiado: pasa el carrito actual a la cuenta de un cliente.
 * Depende de las constantes globales que define pos_main.html
 * (API_URLS, CSRF_TOKEN, TRANSACTION_ID).
 */
(function () {
    'use strict';

    const btn = document.getElementById('btn-fiado');
    const modalEl = document.getElementById('fiadoModal');
    if (!btn || !modalEl) return;

    const $ = (id) => document.getElementById(id);
    const stepPick = $('fiado-step-pick');
    const stepDone = $('fiado-step-done');
    const footPick = $('fiado-footer-pick');
    const footDone = $('fiado-footer-done');
    const searchInput = $('fiado-search');
    const listEl = $('fiado-list');
    const selectedEl = $('fiado-selected');
    const confirmBtn = $('fiado-confirm');
    const errorEl = $('fiado-error');

    let selected = null;
    let lastResult = null;
    let searchTimer = null;
    let modal = null;

    const money = (n) => '$' + Number(n || 0).toLocaleString('es-AR', { maximumFractionDigits: 2 });
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function showError(msg) {
        errorEl.textContent = msg || '';
        errorEl.classList.toggle('d-none', !msg);
    }

    function setSelected(customer) {
        selected = customer;
        if (customer) {
            selectedEl.innerHTML = '<i class="fas fa-user me-1"></i>Cuenta de <strong>' + esc(customer.name) +
                '</strong> — debe ' + money(customer.balance);
            selectedEl.classList.remove('d-none');
        } else {
            selectedEl.classList.add('d-none');
        }
        confirmBtn.disabled = !customer;
    }

    async function loadCustomers(q) {
        try {
            const resp = await fetch(API_URLS.fiadoCustomers + '?q=' + encodeURIComponent(q || ''));
            const data = await resp.json();
            if (!data.success) throw new Error();
            if (!data.customers.length) {
                listEl.innerHTML = '<div class="list-group-item text-muted" style="background:#0c0c1c;border-color:#2a2a44;">' +
                    'Sin resultados. Podés crear un cliente nuevo abajo.</div>';
                return;
            }
            listEl.innerHTML = data.customers.map((c) =>
                '<button type="button" class="list-group-item list-group-item-action d-flex justify-content-between" ' +
                'style="background:#0c0c1c;color:#eee;border-color:#2a2a44;" data-id="' + c.id + '">' +
                '<span>' + esc(c.name) + (c.phone ? ' <small class="text-muted">' + esc(c.phone) + '</small>' : '') + '</span>' +
                '<span class="' + (c.balance > 0 ? 'text-warning' : 'text-success') + '">' + money(c.balance) + '</span></button>'
            ).join('');
            listEl.querySelectorAll('button').forEach((b, i) => {
                b.addEventListener('click', () => setSelected(data.customers[i]));
            });
        } catch (e) {
            listEl.innerHTML = '<div class="list-group-item text-danger" style="background:#0c0c1c;">No se pudo cargar la lista de clientes.</div>';
        }
    }

    async function openFiado() {
        // El botón COBRAR queda deshabilitado mientras el carrito está vacío.
        const checkout = $('btn-checkout');
        if (checkout && checkout.disabled) {
            alert('El carrito está vacío');
            return;
        }
        document.querySelectorAll('.modal.show').forEach((m) => {
            const inst = bootstrap.Modal.getInstance(m);
            if (inst) inst.hide();
        });

        stepPick.classList.remove('d-none');
        footPick.classList.remove('d-none');
        stepDone.classList.add('d-none');
        footDone.classList.add('d-none');
        searchInput.value = '';
        $('fiado-note').value = '';
        $('fiado-new-name').value = '';
        $('fiado-new-phone').value = '';
        setSelected(null);
        showError('');
        $('fiado-total').textContent = '...';

        modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
        loadCustomers('');

        try {
            const resp = await fetch(API_URLS.getCart);
            const data = await resp.json();
            $('fiado-total').textContent = money(data.totals ? data.totals.total : 0);
        } catch (e) {
            $('fiado-total').textContent = '';
        }
    }

    async function createCustomer() {
        const name = $('fiado-new-name').value.trim();
        if (!name) { showError('Escribí el nombre del cliente'); return; }
        showError('');
        try {
            const resp = await fetch(API_URLS.fiadoCustomerCreate, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify({ name: name, phone: $('fiado-new-phone').value.trim() }),
            });
            const data = await resp.json();
            if (!data.success) { showError(data.error || 'No se pudo crear el cliente'); return; }
            setSelected(data.customer);
            $('fiado-new-name').value = '';
            $('fiado-new-phone').value = '';
            $('fiado-new-box').open = false;
            loadCustomers(searchInput.value);
        } catch (e) {
            showError('Error de conexión');
        }
    }

    async function confirmFiado() {
        if (!selected) return;
        confirmBtn.disabled = true;
        showError('');
        try {
            const resp = await fetch(API_URLS.fiadoChargeSale, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify({
                    transaction_id: TRANSACTION_ID,
                    customer_id: selected.id,
                    note: $('fiado-note').value.trim(),
                }),
            });
            const data = await resp.json();
            if (!data.success) {
                showError(data.error || 'No se pudo fiar la venta');
                confirmBtn.disabled = false;
                return;
            }
            lastResult = data;
            $('fiado-done-title').textContent = 'Anotado en la cuenta de ' + data.customer_name;
            $('fiado-done-detail').textContent = money(data.total) + ' — ahora debe ' + money(data.balance) +
                ' (Ticket ' + data.ticket_number + ')';
            stepPick.classList.add('d-none');
            footPick.classList.add('d-none');
            stepDone.classList.remove('d-none');
            footDone.classList.remove('d-none');
        } catch (e) {
            showError('Error de conexión');
            confirmBtn.disabled = false;
        }
    }

    btn.addEventListener('click', openFiado);
    confirmBtn.addEventListener('click', confirmFiado);
    $('fiado-create-btn').addEventListener('click', createCustomer);
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => loadCustomers(searchInput.value.trim()), 200);
    });
    $('fiado-print').addEventListener('click', () => {
        if (lastResult) window.open('/pos/ticket/' + lastResult.transaction_id + '/', '_blank',
            'width=320,height=500,menubar=no,toolbar=no,location=no,status=no');
        window.location.reload();
    });
    $('fiado-continue').addEventListener('click', () => window.location.reload());
    modalEl.addEventListener('shown.bs.modal', () => searchInput.focus());
    // Si ya se fió y cierran el modal con Esc, el carrito quedó viejo: recargar.
    modalEl.addEventListener('hidden.bs.modal', () => { if (lastResult) window.location.reload(); });
})();
