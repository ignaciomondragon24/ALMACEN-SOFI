"""
Management Command to initialize default data for CHE GOLOSO
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.models import Role
from cashregister.models import PaymentMethod, CashRegister
from stocks.models import UnitOfMeasure, ProductCategory


class Command(BaseCommand):
    help = 'Initialize default data for CHE GOLOSO system'

    def handle(self, *args, **options):
        self.stdout.write('Initializing CHE GOLOSO data...\n')
        
        # Create roles
        self.create_roles()
        
        # Create payment methods
        self.create_payment_methods()
        
        # Create cash registers
        self.create_cash_registers()
        
        # Create units of measure
        self.create_units()
        
        # Create categories
        self.create_categories()
        

        self.stdout.write(self.style.SUCCESS('\n✅ Data initialization complete!'))

    def create_roles(self):
        """Create default roles with permissions."""
        self.stdout.write('Creating roles...')
        
        roles = [
            ('Admin', 'Administrador - Acceso total'),
            ('Manager', 'Gerente - Gestión operativa'),
            ('Cashier', 'Cajero - POS y caja'),
            ('Stock Manager', 'Encargado de Stock - Inventario'),
        ]
        
        for name, description in roles:
            role, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f'  ✓ Created role: {name}')
            else:
                self.stdout.write(f'  - Role exists: {name}')

    def create_payment_methods(self):
        """Create default payment methods."""
        self.stdout.write('Creating payment methods...')
        
        methods = [
            {'code': 'cash', 'name': 'Efectivo', 'is_cash': True, 'icon': 'fas fa-money-bill-wave', 'position': 1},
            {'code': 'debit', 'name': 'Débito', 'is_cash': False, 'icon': 'fas fa-credit-card', 'position': 2},
            {'code': 'credit', 'name': 'Crédito', 'is_cash': False, 'icon': 'fas fa-credit-card', 'position': 3},
            {'code': 'transfer', 'name': 'Transferencia', 'is_cash': False, 'icon': 'fas fa-building-columns', 'position': 4},
            {'code': 'mercadopago', 'name': 'MercadoPago', 'is_cash': False, 'icon': 'fas fa-wallet', 'position': 5},
        ]
        
        for method_data in methods:
            method, created = PaymentMethod.objects.get_or_create(
                code=method_data['code'],
                defaults=method_data
            )
            if created:
                self.stdout.write(f'  ✓ Created payment method: {method.name}')
            else:
                # Fix icons on existing methods if they're wrong/missing prefix
                if method.icon != method_data['icon']:
                    method.icon = method_data['icon']
                    method.save(update_fields=['icon'])
                    self.stdout.write(f'  ↻ Updated icon for: {method.name}')
                else:
                    self.stdout.write(f'  - Payment method exists: {method.name}')

    def create_cash_registers(self):
        """Create default cash registers."""
        self.stdout.write('Creating cash registers...')
        
        registers = [
            {'code': 'CAJA-01', 'name': 'Caja Principal', 'location': 'Entrada'},
            {'code': 'CAJA-02', 'name': 'Caja Secundaria', 'location': 'Pasillo Central'},
        ]
        
        for register_data in registers:
            register, created = CashRegister.objects.get_or_create(
                code=register_data['code'],
                defaults=register_data
            )
            if created:
                self.stdout.write(f'  ✓ Created cash register: {register.code}')
            else:
                self.stdout.write(f'  - Cash register exists: {register.code}')

    def create_units(self):
        """Create default units of measure."""
        self.stdout.write('Creating units of measure...')
        
        units = [
            {'name': 'Unidad', 'abbreviation': 'u', 'symbol': 'u', 'unit_type': 'unit'},
            {'name': 'Kilogramo', 'abbreviation': 'kg', 'symbol': 'kg', 'unit_type': 'weight'},
            {'name': 'Gramo', 'abbreviation': 'g', 'symbol': 'g', 'unit_type': 'weight'},
            {'name': 'Litro', 'abbreviation': 'L', 'symbol': 'L', 'unit_type': 'volume'},
            {'name': 'Mililitro', 'abbreviation': 'ml', 'symbol': 'ml', 'unit_type': 'volume'},
            {'name': 'Metro', 'abbreviation': 'm', 'symbol': 'm', 'unit_type': 'length'},
            {'name': 'Centímetro', 'abbreviation': 'cm', 'symbol': 'cm', 'unit_type': 'length'},
            {'name': 'Docena', 'abbreviation': 'doc', 'symbol': 'doc', 'unit_type': 'unit'},
            {'name': 'Paquete', 'abbreviation': 'paq', 'symbol': 'paq', 'unit_type': 'unit'},
            {'name': 'Caja', 'abbreviation': 'caja', 'symbol': 'caja', 'unit_type': 'unit'},
        ]
        
        for unit_data in units:
            unit, created = UnitOfMeasure.objects.get_or_create(
                name=unit_data['name'],
                defaults=unit_data
            )
            if created:
                self.stdout.write(f'  ✓ Created unit: {unit.name}')
            else:
                self.stdout.write(f'  - Unit exists: {unit.name}')

    def create_categories(self):
        """Create default product categories."""
        self.stdout.write('  - Categorías: se crean desde el sistema, no por defecto.')
