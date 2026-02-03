# CHE GOLOSO - Sistema de Gestión de Supermercado

## Descripción del Proyecto
Sistema integral de gestión para supermercados pequeños y medianos que integra:
- Punto de Venta (POS) moderno con dark mode
- Control de inventario en tiempo real
- Gestión de caja y turnos
- Sistema de promociones avanzado (2x1, combos, descuentos)
- Reportes y estadísticas
- Control de gastos y compras
- Gestión de cartelería

## Stack Tecnológico
- **Backend**: Python 3.8+, Django 3.0.5, Django REST Framework
- **Base de Datos**: SQLite (desarrollo) / PostgreSQL (producción)
- **Frontend**: HTML5, CSS3 (Bootstrap 5), JavaScript ES6+
- **Iconos**: Font Awesome 6.0
- **PDFs**: ReportLab, xhtml2pdf

## Estructura de Apps Django
- `superrecord/` - Proyecto principal (settings, urls, wsgi)
- `accounts/` - Usuarios, roles, permisos, login, dashboard
- `cashregister/` - Cajas registradoras, turnos, movimientos
- `pos/` - Punto de venta, transacciones, carrito, checkout
- `stocks/` - Productos, categorías, unidades, movimientos de stock
- `promotions/` - Motor de promociones (2x1, combos, descuentos)
- `signage/` - Cartelería y generación de PDFs
- `purchase/` - Compras y proveedores
- `expenses/` - Gastos operativos
- `sales/` - Ventas (legacy)
- `company/` - Datos de la empresa

## Convenciones de Código
- Usar formato de moneda argentina: $1.234,56
- Dark mode en POS (#1a1a2e background)
- Código de barras EAN-13
- Ticket format: CAJA-XX-YYYYMMDD-NNNN

## Comandos Útiles
```bash
# Activar entorno virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Ejecutar servidor
python manage.py runserver

# Tests
python manage.py test
```

## Roles de Usuario
- **Admin**: Acceso total
- **Manager**: Gestión operativa
- **Cashier**: Solo POS y caja
- **Stock Manager**: Solo inventario
