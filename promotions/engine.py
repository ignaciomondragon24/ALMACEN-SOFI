"""
Promotion Engine - Calculates and applies promotions to cart
"""
from decimal import Decimal
from .models import Promotion


class PromotionEngine:
    """Engine for calculating promotions on cart items."""
    
    @staticmethod
    def calculate_cart(cart_items):
        """
        Calculate promotions applicable to cart items.
        
        Args:
            cart_items: List of dicts with:
                - item_id: ID of POSTransactionItem
                - product_id: Product ID
                - quantity: Quantity
                - unit_price: Unit price
        
        Returns:
            dict with:
                - original_total: Total without discounts
                - discount_total: Total discounts
                - final_total: Total after discounts
                - applied_promotions: List of applied promotions
        """
        if not cart_items:
            return {
                'original_total': 0,
                'discount_total': 0,
                'final_total': 0,
                'applied_promotions': []
            }
        
        # Calculate original total
        original_total = sum(
            Decimal(str(item['unit_price'])) * Decimal(str(item['quantity']))
            for item in cart_items
        )
        
        # Get active promotions
        active_promotions = Promotion.objects.filter(
            status='active'
        ).prefetch_related('products').order_by('-priority')
        
        # Filter valid promotions
        valid_promotions = [p for p in active_promotions if p.is_valid_today()]
        
        applied_promotions = []
        total_discount = Decimal('0.00')
        
        # Track which items have been affected by non-combinable promos
        affected_items = set()
        
        for promo in valid_promotions:
            # Get product IDs in this promotion
            promo_product_ids = set(promo.products.values_list('id', flat=True))
            
            # Find matching items in cart
            matching_items = [
                item for item in cart_items
                if item['product_id'] in promo_product_ids
                and item['item_id'] not in affected_items
            ]
            
            if not matching_items:
                continue
            
            # Apply promotion based on type
            discount_info = None
            
            if promo.promo_type == 'nxm':
                discount_info = PromotionEngine._apply_nxm(matching_items, promo)
            elif promo.promo_type == 'quantity_discount':
                discount_info = PromotionEngine._apply_quantity_discount(matching_items, promo)
            elif promo.promo_type == 'second_unit':
                discount_info = PromotionEngine._apply_second_unit(matching_items, promo)
            elif promo.promo_type == 'simple_discount':
                discount_info = PromotionEngine._apply_simple_discount(matching_items, promo)
            elif promo.promo_type == 'combo':
                discount_info = PromotionEngine._apply_combo(matching_items, promo)
            
            if discount_info and discount_info['discount'] > 0:
                applied_promotions.append({
                    'promotion_id': promo.id,
                    'promotion_name': promo.name,
                    'discount_amount': float(discount_info['discount']),
                    'affected_products': list(promo_product_ids),
                    'item_discounts': discount_info.get('item_discounts', [])
                })
                
                total_discount += discount_info['discount']
                
                # If not combinable, mark items as affected
                if not promo.is_combinable:
                    for item in matching_items:
                        affected_items.add(item['item_id'])
        
        final_total = original_total - total_discount
        
        return {
            'original_total': float(original_total),
            'discount_total': float(total_discount),
            'final_total': float(max(final_total, Decimal('0.00'))),
            'applied_promotions': applied_promotions
        }
    
    @staticmethod
    def _apply_nxm(items, promo):
        """
        Apply NxM promotion (e.g., 2x1, 3x2).
        
        For 2x1: Buy 2, pay 1 → Free the cheapest
        For 3x2: Buy 3, pay 2 → Free the cheapest
        """
        n = promo.quantity_required  # e.g., 2 for 2x1
        m = promo.quantity_charged   # e.g., 1 for 2x1
        free_items = n - m           # e.g., 1 for 2x1
        
        # Calculate total quantity
        total_qty = sum(Decimal(str(item['quantity'])) for item in items)
        
        if total_qty < n:
            return {'discount': Decimal('0.00'), 'item_discounts': []}
        
        # How many complete sets of N items?
        complete_sets = int(total_qty // n)
        
        if complete_sets == 0:
            return {'discount': Decimal('0.00'), 'item_discounts': []}
        
        # Sort items by price (cheapest first - those get discounted)
        sorted_items = sorted(items, key=lambda x: Decimal(str(x['unit_price'])))
        
        # Calculate discount: free_items * complete_sets * price of cheapest
        items_to_discount = free_items * complete_sets
        total_discount = Decimal('0.00')
        item_discounts = []
        
        remaining_discount_qty = items_to_discount
        
        for item in sorted_items:
            if remaining_discount_qty <= 0:
                break
            
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            
            discount_qty = min(qty, remaining_discount_qty)
            item_discount = price * discount_qty
            
            total_discount += item_discount
            remaining_discount_qty -= discount_qty
            
            if item_discount > 0:
                item_discounts.append({
                    'item_id': item['item_id'],
                    'discount': float(item_discount)
                })
        
        return {
            'discount': total_discount,
            'item_discounts': item_discounts
        }
    
    @staticmethod
    def _apply_quantity_discount(items, promo):
        """Apply discount when quantity threshold is met."""
        total_qty = sum(Decimal(str(item['quantity'])) for item in items)
        
        if total_qty < promo.min_quantity:
            return {'discount': Decimal('0.00'), 'item_discounts': []}
        
        total_discount = Decimal('0.00')
        item_discounts = []
        
        for item in items:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            subtotal = price * qty
            
            if promo.discount_percent > 0:
                item_discount = subtotal * (promo.discount_percent / 100)
            else:
                item_discount = min(promo.discount_amount, subtotal)
            
            total_discount += item_discount
            
            if item_discount > 0:
                item_discounts.append({
                    'item_id': item['item_id'],
                    'discount': float(item_discount)
                })
        
        return {
            'discount': total_discount,
            'item_discounts': item_discounts
        }
    
    @staticmethod
    def _apply_second_unit(items, promo):
        """Apply discount on second (and subsequent) units."""
        total_discount = Decimal('0.00')
        item_discounts = []
        
        for item in items:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            
            if qty <= 1:
                continue
            
            # Discount applies to one unit per pair ("segunda unidad")
            discounted_qty = int(qty) // 2
            item_discount = discounted_qty * price * (promo.second_unit_discount / 100)
            
            total_discount += item_discount
            
            if item_discount > 0:
                item_discounts.append({
                    'item_id': item['item_id'],
                    'discount': float(item_discount)
                })
        
        return {
            'discount': total_discount,
            'item_discounts': item_discounts
        }
    
    @staticmethod
    def _apply_simple_discount(items, promo):
        """Apply simple percentage or fixed discount."""
        total_discount = Decimal('0.00')
        item_discounts = []
        
        for item in items:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            subtotal = price * qty
            
            if promo.discount_percent > 0:
                item_discount = subtotal * (promo.discount_percent / 100)
            else:
                item_discount = min(promo.discount_amount, subtotal)
            
            total_discount += item_discount
            
            if item_discount > 0:
                item_discounts.append({
                    'item_id': item['item_id'],
                    'discount': float(item_discount)
                })
        
        return {
            'discount': total_discount,
            'item_discounts': item_discounts
        }
    
    @staticmethod
    def _apply_combo(items, promo):
        """Apply combo pricing (set price for combination of products)."""
        if not promo.final_price:
            return {'discount': Decimal('0.00'), 'item_discounts': []}
        
        # For combo, all required products must be present
        promo_product_ids = set(promo.products.values_list('id', flat=True))
        cart_product_ids = set(item['product_id'] for item in items)
        
        # Check if all combo products are in cart
        if not promo_product_ids.issubset(cart_product_ids):
            return {'discount': Decimal('0.00'), 'item_discounts': []}
        
        # Calculate original total of combo products
        combo_total = sum(
            Decimal(str(item['unit_price'])) * Decimal(str(item['quantity']))
            for item in items
            if item['product_id'] in promo_product_ids
        )
        
        # Discount is the difference between original and combo price
        discount = max(combo_total - promo.final_price, Decimal('0.00'))
        
        # Distribute discount proportionally
        item_discounts = []
        if discount > 0:
            for item in items:
                if item['product_id'] in promo_product_ids:
                    item_subtotal = Decimal(str(item['unit_price'])) * Decimal(str(item['quantity']))
                    proportion = item_subtotal / combo_total
                    item_discount = discount * proportion
                    
                    item_discounts.append({
                        'item_id': item['item_id'],
                        'discount': float(item_discount)
                    })
        
        return {
            'discount': discount,
            'item_discounts': item_discounts
        }
