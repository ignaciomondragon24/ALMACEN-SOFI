# CHE GOLOSO - Sistema de Gestión de Supermercado

Sistema integral de gestión para supermercados pequeños y medianos desarrollado con Django.

## 🚀 Características

- **Punto de Venta (POS)** moderno con dark mode
- **Control de Inventario** en tiempo real
- **Gestión de Caja y Turnos** completa
- **Sistema de Promociones** avanzado (2x1, combos, descuentos)
- **Reportes y Estadísticas** detalladas
- **Control de Gastos y Compras**
- **Gestión de Cartelería** para precios
- **Múltiples Roles de Usuario** (Admin, Manager, Cajero, Stock Manager)

## 📋 Requisitos Previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Git (opcional)

## 🛠️ Instalación

### 1. Clonar o descargar el proyecto

```bash
cd "ruta/a/tu/carpeta"
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar entorno virtual

**Windows:**
```bash
.\venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar variables de entorno

Copiar el archivo de ejemplo y editar:
```bash
copy .env.example .env
```

Editar `.env` con tus configuraciones:
```
DEBUG=True
SECRET_KEY=tu-clave-secreta-aqui
DATABASE_URL=sqlite:///db.sqlite3
```

### 6. Aplicar migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Crear superusuario

```bash
python manage.py createsuperuser
```

### 8. Cargar datos iniciales (opcional)

```bash
python manage.py loaddata initial_data.json
```

### 9. Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

El sistema estará disponible en: http://localhost:8000

## 📁 Estructura del Proyecto

```
che-goloso/
├── accounts/           # Usuarios, roles, permisos, login
├── cashregister/       # Cajas registradoras, turnos, movimientos
├── company/            # Datos de la empresa
├── decorators/         # Decoradores personalizados
├── expenses/           # Gastos operativos
├── helpers/            # Utilidades y generación de PDFs
├── pos/                # Punto de venta, transacciones
├── promotions/         # Motor de promociones
├── purchase/           # Compras y proveedores
├── sales/              # Ventas (legacy)
├── signage/            # Cartelería y PDFs
├── stocks/             # Productos, categorías, inventario
├── superrecord/        # Configuración del proyecto Django
├── templates/          # Plantillas HTML
├── static/             # Archivos estáticos (CSS, JS, imágenes)
├── manage.py           # Script de gestión de Django
└── requirements.txt    # Dependencias del proyecto
```

## 👥 Roles de Usuario

| Rol | Descripción |
|-----|-------------|
| **Admin** | Acceso total al sistema |
| **Manager** | Gestión operativa completa |
| **Cashier** | Solo POS y caja |
| **Stock Manager** | Solo inventario |

## 🔧 Comandos Útiles

```bash
# Ejecutar tests
python manage.py test

# Crear migraciones para una app específica
python manage.py makemigrations nombre_app

# Ejecutar shell de Django
python manage.py shell

# Recolectar archivos estáticos (producción)
python manage.py collectstatic

# Crear datos de prueba
python manage.py seed_data
```

## 🖥️ Atajos de Teclado (POS)

| Tecla | Acción |
|-------|--------|
| F2 | Enfocar búsqueda |
| F3 | Vaciar carrito |
| F8 | Ir a cobrar |
| Escape | Cancelar/Cerrar |
| Enter | Agregar producto (en búsqueda) |

## 💰 Formato de Moneda

El sistema usa formato argentino:
- Separador de miles: `.`
- Separador decimal: `,`
- Ejemplo: `$1.234,56`

## 📊 Formato de Ticket

```
CAJA-XX-YYYYMMDD-NNNN
```
Ejemplo: `CAJA-01-20241215-0001`

## 🚀 Despliegue en Producción

1. Configurar `DEBUG=False` en `.env`
2. Configurar una base de datos PostgreSQL
3. Configurar servidor web (Nginx/Apache)
4. Usar Gunicorn o uWSGI como servidor WSGI
5. Configurar HTTPS con certificado SSL

## 📝 Licencia

Este proyecto es propietario. Todos los derechos reservados.

## 👨‍💻 Soporte

Para soporte técnico, contactar al equipo de desarrollo.

---

**CHE GOLOSO** - Sistema de Gestión de Supermercado
© 2024 - Todos los derechos reservados
