---
name: granel_candy_system_context
description: Context and decisions for the weighted bulk candy (granel) system implementation in CHE GOLOSO
type: project
---

Feature: Sistema de venta de gomitas/caramelos a granel con costo ponderado dinámico.

**Why:** The business sells mixed bulk candy from a shared jar. Multiple supplier bags with different costs per gram feed the same retail "commodity" product sold at a fixed price per 100g. They need real margin reporting and shrinkage auditing.

**How to apply:** This is the primary active development feature. All design decisions below are load-bearing for implementation.

## Key design decisions made during exploration (2026-03-30)

### POSTransactionItem.quantity is PositiveIntegerField (blocking issue)
Migration 0003_auto_20260205_0040.py changed it FROM DecimalField TO PositiveIntegerField.
This MUST be reversed (new migration back to DecimalField) before granel sales work.
The model.py shows PositiveIntegerField with MinValueValidator(1) — this truncates decimal quantities.

### Product model already has is_bulk + bulk_unit fields
No need for a new boolean. The granel comodin product sets is_bulk=True, bulk_unit='g'.
The existing POS bulk modal (showBulkQuantityModal in pos-main.js) already handles weight input.

### New fields needed on Product (via stocks migration)
- is_granel: BooleanField (distinguishes granel comodin from regular bulk products)
- granel_price_weight_grams: PositiveIntegerField default=100 (price displayed "per X grams")
- weighted_avg_cost_per_gram: DecimalField(max_digits=12, decimal_places=4) (high precision)
- weight_per_unit_grams: DecimalField(max_digits=10, decimal_places=2) (for source bulk bags — grams per sealed bag)

### New app: granel/
All granel-specific logic lives in a new app, not in stocks/.

### StockManagementService.add_stock already does weighted average
BUT uses cost_price which is decimal_places=2 — insufficient for per-gram costs.
The new weighted_avg_cost_per_gram field handles this separately.

### CheckoutService requires no changes
It deducts stock via deduct_stock() or deduct_stock_with_cascade().
The granel product is just another is_bulk product from POS perspective.

### Transfer workflow maps to StockMovement types
Use transfer_out on source bulk product, transfer_in on granel product.
These types already exist in StockMovement.MOVEMENT_TYPES.

## Architecture summary
- New app: granel/ (models, services, views, urls, admin, forms)
- Migrate stocks: add 4 new fields to Product
- Migrate pos: revert quantity back to DecimalField
- New models in granel: BulkToGranelTransfer, GranelCostHistory, ShrinkageAudit
- New service: GranelService with transfer_bulk_to_granel, recalculate_weighted_cost, perform_shrinkage_audit
- POS changes: update bulk modal to show "per Xg" label for is_granel products
- Navbar: add "Caramelera" dropdown under Inventario
