"""
AI Assistant Service for CHE GOLOSO.
Integrates with OpenAI GPT-4 mini and provides business context.
"""
import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from django.db.models import Sum, Count, Avg, F, Q, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, Cast
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class BusinessDataCollector:
    """
    Collects business data from the system to provide context to the AI.
    """
    
    def __init__(self):
        self.today = timezone.now().date()
        self.start_of_month = self.today.replace(day=1)
        self.start_of_week = self.today - timedelta(days=self.today.weekday())
    
    def get_sales_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get sales summary for the specified period."""
        try:
            from pos.models import POSTransaction, POSTransactionItem
            
            start_date = self.today - timedelta(days=days)
            
            transactions = POSTransaction.objects.filter(
                created_at__date__gte=start_date,
                status='completed'
            )
            
            summary = transactions.aggregate(
                total_ventas=Sum('total'),
                cantidad_transacciones=Count('id'),
                ticket_promedio=Avg('total')
            )
            
            # Ventas por día
            daily_sales = transactions.annotate(
                fecha=TruncDate('created_at')
            ).values('fecha').annotate(
                total=Sum('total'),
                cantidad=Count('id')
            ).order_by('-fecha')[:7]
            
            # Top productos
            top_products = POSTransactionItem.objects.filter(
                transaction__created_at__date__gte=start_date,
                transaction__status='completed'
            ).values(
                'product__name'
            ).annotate(
                cantidad_vendida=Sum('quantity'),
                ingresos=Sum('subtotal')
            ).order_by('-ingresos')[:10]
            
            return {
                'periodo': f'Últimos {days} días',
                'total_ventas': float(summary['total_ventas'] or 0),
                'cantidad_transacciones': summary['cantidad_transacciones'] or 0,
                'ticket_promedio': float(summary['ticket_promedio'] or 0),
                'ventas_diarias': list(daily_sales),
                'top_productos': list(top_products)
            }
        except Exception as e:
            logger.error(f"Error getting sales summary: {e}")
            return {'error': str(e)}
    
    def get_inventory_status(self) -> Dict[str, Any]:
        """Get current inventory status and alerts."""
        try:
            from stocks.models import Product
            
            products = Product.objects.filter(is_active=True)
            
            # Stock bajo (menos del mínimo)
            low_stock = products.filter(
                current_stock__lt=F('min_stock')
            ).values('name', 'current_stock', 'min_stock', 'unit_of_measure__abbreviation')[:20]
            
            # Sin stock
            out_of_stock = products.filter(
                current_stock__lte=0
            ).count()
            
            # Valor del inventario
            inventory_value = products.aggregate(
                valor_total=Sum(
                    Cast('current_stock', DecimalField()) * F('cost_price'),
                    output_field=DecimalField()
                )
            )['valor_total'] or 0
            
            # Productos por categoría
            by_category = products.values(
                'category__name'
            ).annotate(
                cantidad=Count('id'),
                valor=Sum(
                    Cast('current_stock', DecimalField()) * F('cost_price'),
                    output_field=DecimalField()
                )
            ).order_by('-valor')
            
            return {
                'total_productos': products.count(),
                'productos_stock_bajo': list(low_stock),
                'cantidad_stock_bajo': len(low_stock),
                'sin_stock': out_of_stock,
                'valor_inventario': float(inventory_value),
                'por_categoria': list(by_category)
            }
        except Exception as e:
            logger.error(f"Error getting inventory status: {e}")
            return {'error': str(e)}
    
    def get_cash_status(self) -> Dict[str, Any]:
        """Get current cash register status."""
        try:
            from cashregister.models import CashRegister, CashShift
            
            # Cajas activas
            active_registers = CashRegister.objects.filter(is_active=True)
            
            # Turnos abiertos
            open_shifts = CashShift.objects.filter(
                status='open'
            ).select_related('cash_register', 'cashier')
            
            shifts_data = []
            for shift in open_shifts:
                shifts_data.append({
                    'caja': shift.cash_register.name,
                    'cajero': shift.cashier.get_full_name() or shift.cashier.username,
                    'inicio': shift.start_time.strftime('%H:%M'),
                    'monto_inicial': float(shift.starting_amount),
                    'ventas': float(shift.total_sales or 0)
                })
            
            return {
                'cajas_activas': active_registers.count(),
                'turnos_abiertos': len(shifts_data),
                'detalle_turnos': shifts_data
            }
        except Exception as e:
            logger.error(f"Error getting cash status: {e}")
            return {'error': str(e)}
    
    def get_promotions_status(self) -> Dict[str, Any]:
        """Get active promotions and their performance."""
        try:
            from promotions.models import Promotion
            
            active_promos = Promotion.objects.filter(
                status='active'
            )
            
            # Filter by date if dates are set
            today = self.today
            active_promos = active_promos.filter(
                Q(start_date__isnull=True) | Q(start_date__lte=today),
                Q(end_date__isnull=True) | Q(end_date__gte=today)
            )
            
            promos_data = []
            for promo in active_promos:
                promos_data.append({
                    'nombre': promo.name,
                    'tipo': promo.get_promo_type_display() if hasattr(promo, 'get_promo_type_display') else promo.promo_type,
                    'descuento': str(promo.discount_percent) if promo.discount_percent else 'N/A',
                    'vence': promo.end_date.strftime('%d/%m/%Y') if promo.end_date else 'Sin fecha'
                })
            
            return {
                'promociones_activas': len(promos_data),
                'detalle': promos_data
            }
        except Exception as e:
            logger.error(f"Error getting promotions status: {e}")
            return {'error': str(e)}
    
    def get_expenses_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get expenses summary."""
        try:
            from expenses.models import Expense
            
            start_date = self.today - timedelta(days=days)
            
            expenses = Expense.objects.filter(
                expense_date__gte=start_date
            )
            
            total = expenses.aggregate(total=Sum('amount'))['total'] or 0
            
            by_category = expenses.values(
                'category__name'
            ).annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            return {
                'periodo': f'Últimos {days} días',
                'total_gastos': float(total),
                'por_categoria': list(by_category)
            }
        except Exception as e:
            logger.error(f"Error getting expenses summary: {e}")
            return {'error': str(e)}
    
    def get_purchases_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get purchases summary."""
        try:
            from purchase.models import Purchase
            
            start_date = self.today - timedelta(days=days)
            
            purchases = Purchase.objects.filter(
                order_date__gte=start_date
            )
            
            summary = purchases.aggregate(
                total=Sum('total'),
                cantidad=Count('id')
            )
            
            by_supplier = purchases.values(
                'supplier__name'
            ).annotate(
                total=Sum('total')
            ).order_by('-total')[:10]
            
            return {
                'periodo': f'Últimos {days} días',
                'total_compras': float(summary['total'] or 0),
                'cantidad_ordenes': summary['cantidad'] or 0,
                'por_proveedor': list(by_supplier)
            }
        except Exception as e:
            logger.error(f"Error getting purchases summary: {e}")
            return {'error': str(e)}
    
    def get_full_context(self) -> str:
        """
        Get full business context as a formatted string for the AI.
        """
        data = {
            'fecha_actual': self.today.strftime('%d/%m/%Y'),
            'ventas': self.get_sales_summary(),
            'inventario': self.get_inventory_status(),
            'caja': self.get_cash_status(),
            'promociones': self.get_promotions_status(),
            'gastos': self.get_expenses_summary(),
            'compras': self.get_purchases_summary()
        }
        
        # Format as readable text
        context_parts = [
            f"📅 DATOS DEL SISTEMA - {data['fecha_actual']}",
            "",
            "💰 VENTAS (últimos 30 días):",
        ]
        
        if 'error' not in data['ventas']:
            v = data['ventas']
            context_parts.extend([
                f"  - Total: ${v['total_ventas']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                f"  - Transacciones: {v['cantidad_transacciones']}",
                f"  - Ticket promedio: ${v['ticket_promedio']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            ])
            if v.get('top_productos'):
                context_parts.append("  - Top 5 productos más vendidos:")
                for i, p in enumerate(v['top_productos'][:5], 1):
                    context_parts.append(f"    {i}. {p['product__name']}: {p['cantidad_vendida']} unidades")
        
        context_parts.extend(["", "📦 INVENTARIO:"])
        if 'error' not in data['inventario']:
            inv = data['inventario']
            context_parts.extend([
                f"  - Total productos activos: {inv['total_productos']}",
                f"  - Productos sin stock: {inv['sin_stock']}",
                f"  - Productos con stock bajo: {inv['cantidad_stock_bajo']}",
                f"  - Valor del inventario: ${inv['valor_inventario']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            ])
            if inv.get('productos_stock_bajo'):
                context_parts.append("  - Alertas de stock bajo:")
                for p in inv['productos_stock_bajo'][:5]:
                    context_parts.append(f"    ⚠️ {p['name']}: {p['current_stock']} {p.get('unit_of_measure__abbreviation', 'u')} (mín: {p['min_stock']})")
        
        context_parts.extend(["", "🏪 ESTADO DE CAJA:"])
        if 'error' not in data['caja']:
            c = data['caja']
            context_parts.extend([
                f"  - Cajas activas: {c['cajas_activas']}",
                f"  - Turnos abiertos: {c['turnos_abiertos']}",
            ])
            for t in c.get('detalle_turnos', []):
                context_parts.append(f"    - {t['caja']}: {t['cajero']} desde {t['inicio']}")
        
        context_parts.extend(["", "🏷️ PROMOCIONES:"])
        if 'error' not in data['promociones']:
            p = data['promociones']
            context_parts.append(f"  - Promociones activas: {p['promociones_activas']}")
            for promo in p.get('detalle', [])[:5]:
                context_parts.append(f"    - {promo['nombre']} ({promo['tipo']}) - Vence: {promo['vence']}")
        
        context_parts.extend(["", "💸 GASTOS (últimos 30 días):"])
        if 'error' not in data['gastos']:
            g = data['gastos']
            context_parts.append(f"  - Total: ${g['total_gastos']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        context_parts.extend(["", "🛒 COMPRAS (últimos 30 días):"])
        if 'error' not in data['compras']:
            co = data['compras']
            context_parts.extend([
                f"  - Total: ${co['total_compras']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                f"  - Órdenes: {co['cantidad_ordenes']}",
            ])
        
        return "\n".join(context_parts)


class AssistantService:
    """
    Main service for the AI Assistant.
    Handles communication with OpenAI and provides business insights.
    """
    
    def __init__(self):
        self.data_collector = BusinessDataCollector()
    
    def _get_openai_client(self):
        """Get OpenAI client with API key from settings."""
        try:
            import openai
            from .models import AssistantSettings
            
            assistant_settings = AssistantSettings.get_settings()
            
            if not assistant_settings.openai_api_key:
                # Try from environment
                api_key = getattr(settings, 'OPENAI_API_KEY', None)
                if not api_key:
                    import os
                    api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("No se ha configurado la API key de OpenAI")
            else:
                api_key = assistant_settings.openai_api_key
            
            return openai.OpenAI(api_key=api_key), assistant_settings
        except ImportError:
            raise ImportError("El paquete 'openai' no está instalado. Ejecute: pip install openai")
    
    def chat(
        self,
        user_message: str,
        conversation=None,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Send a message to the AI assistant and get a response.
        
        Args:
            user_message: The user's message
            conversation: Optional Conversation object for history
            include_context: Whether to include business data context
        
        Returns:
            Dict with response and metadata
        """
        from .models import Message, QueryLog, AssistantSettings
        
        start_time = time.time()
        
        try:
            client, assistant_settings = self._get_openai_client()
            
            if not assistant_settings.is_enabled:
                return {
                    'success': False,
                    'error': 'El asistente está deshabilitado',
                    'response': None
                }
            
            # Build messages array
            messages = []
            
            # System prompt with business context
            system_content = assistant_settings.system_prompt or AssistantSettings.get_default_system_prompt()
            
            if include_context:
                business_context = self.data_collector.get_full_context()
                system_content += f"\n\n--- DATOS ACTUALES DEL NEGOCIO ---\n{business_context}"
            
            messages.append({
                'role': 'system',
                'content': system_content
            })
            
            # Add conversation history if available
            if conversation:
                history = conversation.get_messages_for_api(limit=10)
                messages.extend(history)
            
            # Add current user message
            messages.append({
                'role': 'user',
                'content': user_message
            })
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model=assistant_settings.model,
                messages=messages,
                max_tokens=assistant_settings.max_tokens,
                temperature=assistant_settings.temperature
            )
            
            assistant_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Save messages to conversation
            if conversation:
                Message.objects.create(
                    conversation=conversation,
                    role='user',
                    content=user_message
                )
                Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=assistant_response,
                    tokens_used=tokens_used
                )
                conversation.save()  # Update updated_at
            
            # Log the query
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                'success': True,
                'response': assistant_response,
                'tokens_used': tokens_used,
                'elapsed_ms': elapsed_ms
            }
            
        except Exception as e:
            logger.error(f"Error in assistant chat: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                'success': False,
                'error': str(e),
                'response': None,
                'elapsed_ms': elapsed_ms
            }
    
    def get_quick_insights(self) -> List[Dict[str, str]]:
        """
        Get quick insights/recommendations without calling the AI.
        Based on current data analysis.
        """
        insights = []
        
        # Check stock alerts
        inv = self.data_collector.get_inventory_status()
        if 'error' not in inv:
            if inv['sin_stock'] > 0:
                insights.append({
                    'type': 'warning',
                    'icon': 'fa-box-open',
                    'title': 'Productos sin stock',
                    'message': f"Hay {inv['sin_stock']} productos sin stock disponible"
                })
            if inv['cantidad_stock_bajo'] > 0:
                insights.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation-triangle',
                    'title': 'Stock bajo',
                    'message': f"{inv['cantidad_stock_bajo']} productos están por debajo del stock mínimo"
                })
        
        # Check sales performance
        sales = self.data_collector.get_sales_summary(days=7)
        if 'error' not in sales and sales['cantidad_transacciones'] > 0:
            insights.append({
                'type': 'info',
                'icon': 'fa-chart-line',
                'title': 'Ventas de la semana',
                'message': f"${sales['total_ventas']:,.2f} en {sales['cantidad_transacciones']} transacciones".replace(",", "X").replace(".", ",").replace("X", ".")
            })
        
        return insights
    
    def get_suggested_questions(self) -> List[str]:
        """
        Returns a list of suggested questions for the user.
        """
        return [
            "¿Cuáles fueron los productos más vendidos esta semana?",
            "¿Cómo están las ventas comparadas con el mes anterior?",
            "¿Qué productos necesitan reposición urgente?",
            "Dame un resumen del estado del negocio",
            "¿Cuáles son los horarios de mayor venta?",
            "¿Qué promociones me recomendás crear?",
            "Analizá la rentabilidad de las categorías",
            "¿Cuánto gasté este mes en comparación con los ingresos?",
        ]
