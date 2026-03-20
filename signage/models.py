import json

from django.db import models
from django.conf import settings


# ─── Diseños pre-armados B&W con logo para impresión ───

LOGO_URL = '/static/img/logo.png'

DEFAULT_LAYOUTS = {
    'simple_50x40': {
        'name': 'Simple Clásico',
        'sign_type': 'simple',
        'width_mm': 50, 'height_mm': 40,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.3,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 1, 'y': 0.5, 'width': 12, 'height': 5, 'zIndex': 20},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 2, 'y': 6, 'width': 46, 'height': 11,
                 'fontFamily': 'Arial Black', 'fontSize': 12, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 7, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'gramaje',
                 'x': 15, 'y': 16.5, 'width': 20, 'height': 4,
                 'fontFamily': 'Arial', 'fontSize': 7, 'fontWeight': 'normal',
                 'fontStyle': 'italic', 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 5, 'zIndex': 10},
                {'id': 'e4', 'type': 'line', 'x': 5, 'y': 21, 'width': 40, 'height': 0.3,
                 'lineColor': '#000000', 'lineWidth': 0.3, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e5', 'type': 'variable', 'variable': 'precio_unitario',
                 'x': 3, 'y': 22, 'width': 44, 'height': 16,
                 'fontFamily': 'Arial Black', 'fontSize': 26, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 14, 'zIndex': 10},
            ]
        }
    },
    'simple_50x30': {
        'name': 'Simple Compacto',
        'sign_type': 'simple',
        'width_mm': 50, 'height_mm': 30,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.3,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 1, 'y': 0.5, 'width': 10, 'height': 4, 'zIndex': 20},
                {'id': 'e1', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 2, 'y': 4.5, 'width': 46, 'height': 8,
                 'fontFamily': 'Arial Black', 'fontSize': 10, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 6, 'zIndex': 10},
                {'id': 'e2', 'type': 'variable', 'variable': 'gramaje',
                 'x': 15, 'y': 12, 'width': 20, 'height': 3.5,
                 'fontFamily': 'Arial', 'fontSize': 6, 'fontWeight': 'normal',
                 'fontStyle': 'italic', 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 5, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'precio_unitario',
                 'x': 3, 'y': 16, 'width': 44, 'height': 12,
                 'fontFamily': 'Arial Black', 'fontSize': 20, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 12, 'zIndex': 10},
            ]
        }
    },
    'promo_70x50': {
        'name': 'Promo Clásico',
        'sign_type': 'promo',
        'width_mm': 70, 'height_mm': 50,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.4,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 1, 'y': 0.5, 'width': 14, 'height': 5.5, 'zIndex': 20},
                {'id': 'e1', 'type': 'variable', 'variable': 'etiqueta_promo',
                 'x': 16, 'y': 0.5, 'width': 52, 'height': 6,
                 'fontFamily': 'Impact', 'fontSize': 12, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
                {'id': 'e1b', 'type': 'line', 'x': 3, 'y': 7, 'width': 64, 'height': 0.3,
                 'lineColor': '#000000', 'lineWidth': 0.3, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 3, 'y': 8, 'width': 64, 'height': 10,
                 'fontFamily': 'Arial Black', 'fontSize': 12, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 7, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'precio_unitario',
                 'x': 3, 'y': 18, 'width': 64, 'height': 7,
                 'fontFamily': 'Arial', 'fontSize': 9, 'fontWeight': 'normal',
                 'textDecoration': 'line-through',
                 'color': '#888888', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 6, 'zIndex': 10},
                {'id': 'e4', 'type': 'shape', 'x': 4, 'y': 26, 'width': 62, 'height': 20,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.3, 'borderRadius': 1, 'zIndex': 3},
                {'id': 'e5', 'type': 'variable', 'variable': 'cantidad_promo',
                 'x': 5, 'y': 27, 'width': 14, 'height': 18,
                 'fontFamily': 'Impact', 'fontSize': 24, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'right', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 14, 'zIndex': 10},
                {'id': 'e6', 'type': 'text', 'content': 'X',
                 'x': 20, 'y': 29, 'width': 8, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 14, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e7', 'type': 'variable', 'variable': 'precio_promo',
                 'x': 28, 'y': 27, 'width': 36, 'height': 18,
                 'fontFamily': 'Impact', 'fontSize': 24, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 14, 'zIndex': 10},
            ]
        }
    },
    'promo_100x70': {
        'name': 'Promo Grande',
        'sign_type': 'promo',
        'width_mm': 100, 'height_mm': 70,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.5,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 2, 'y': 1, 'width': 18, 'height': 7, 'zIndex': 20},
                {'id': 'e1', 'type': 'variable', 'variable': 'etiqueta_promo',
                 'x': 22, 'y': 1, 'width': 74, 'height': 8,
                 'fontFamily': 'Impact', 'fontSize': 16, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 10, 'zIndex': 10},
                {'id': 'e1b', 'type': 'line', 'x': 5, 'y': 10, 'width': 90, 'height': 0.4,
                 'lineColor': '#000000', 'lineWidth': 0.4, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 5, 'y': 12, 'width': 90, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 16, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 9, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'precio_unitario',
                 'x': 10, 'y': 27, 'width': 80, 'height': 8,
                 'fontFamily': 'Arial', 'fontSize': 10, 'fontWeight': 'normal',
                 'textDecoration': 'line-through',
                 'color': '#888888', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 7, 'zIndex': 10},
                {'id': 'e4', 'type': 'shape', 'x': 6, 'y': 37, 'width': 88, 'height': 28,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.4, 'borderRadius': 2, 'zIndex': 3},
                {'id': 'e5', 'type': 'variable', 'variable': 'cantidad_promo',
                 'x': 8, 'y': 39, 'width': 22, 'height': 24,
                 'fontFamily': 'Impact', 'fontSize': 36, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'right', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 18, 'zIndex': 10},
                {'id': 'e6', 'type': 'text', 'content': 'X',
                 'x': 32, 'y': 42, 'width': 12, 'height': 18,
                 'fontFamily': 'Arial Black', 'fontSize': 18, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e7', 'type': 'variable', 'variable': 'precio_promo',
                 'x': 44, 'y': 39, 'width': 48, 'height': 24,
                 'fontFamily': 'Impact', 'fontSize': 36, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 18, 'zIndex': 10},
            ]
        }
    },
    'bulk_100x70': {
        'name': 'Bulto Clásico',
        'sign_type': 'bulk',
        'width_mm': 100, 'height_mm': 70,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.4,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 2, 'y': 1, 'width': 18, 'height': 7, 'zIndex': 20},
                {'id': 'e1b', 'type': 'line', 'x': 5, 'y': 9, 'width': 90, 'height': 0.3,
                 'lineColor': '#000000', 'lineWidth': 0.3, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 4, 'y': 10, 'width': 92, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 14, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 9, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'precio_total',
                 'x': 5, 'y': 26, 'width': 90, 'height': 24,
                 'fontFamily': 'Impact', 'fontSize': 34, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 16, 'zIndex': 10},
                {'id': 'e4', 'type': 'shape', 'x': 15, 'y': 53, 'width': 70, 'height': 13,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.3, 'borderRadius': 1, 'zIndex': 5},
                {'id': 'e5', 'type': 'variable', 'variable': 'tipo_empaque',
                 'x': 17, 'y': 54, 'width': 28, 'height': 11,
                 'fontFamily': 'Arial Black', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'right', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
                {'id': 'e6', 'type': 'variable', 'variable': 'contenido_empaque',
                 'x': 48, 'y': 54, 'width': 35, 'height': 11,
                 'fontFamily': 'Arial Black', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'left', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
            ]
        }
    },
    'bulk_140x100': {
        'name': 'Bulto Grande',
        'sign_type': 'bulk',
        'width_mm': 140, 'height_mm': 100,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.5,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 3, 'y': 2, 'width': 24, 'height': 10, 'zIndex': 20},
                {'id': 'e1b', 'type': 'line', 'x': 8, 'y': 14, 'width': 124, 'height': 0.4,
                 'lineColor': '#000000', 'lineWidth': 0.4, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 6, 'y': 16, 'width': 128, 'height': 20,
                 'fontFamily': 'Arial Black', 'fontSize': 20, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 12, 'zIndex': 10},
                {'id': 'e3', 'type': 'variable', 'variable': 'precio_total',
                 'x': 10, 'y': 40, 'width': 120, 'height': 34,
                 'fontFamily': 'Impact', 'fontSize': 50, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 22, 'zIndex': 10},
                {'id': 'e4', 'type': 'shape', 'x': 20, 'y': 78, 'width': 100, 'height': 18,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.3, 'borderRadius': 2, 'zIndex': 5},
                {'id': 'e5', 'type': 'variable', 'variable': 'tipo_empaque',
                 'x': 24, 'y': 80, 'width': 40, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 14, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'right', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 10, 'zIndex': 10},
                {'id': 'e6', 'type': 'variable', 'variable': 'contenido_empaque',
                 'x': 68, 'y': 80, 'width': 48, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 14, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'left', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 10, 'zIndex': 10},
            ]
        }
    },
    'weight_100x70': {
        'name': 'Peso Clásico',
        'sign_type': 'weight',
        'width_mm': 100, 'height_mm': 70,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.4,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 2, 'y': 1, 'width': 18, 'height': 7, 'zIndex': 20},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 4, 'y': 9, 'width': 92, 'height': 12,
                 'fontFamily': 'Arial Black', 'fontSize': 13, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
                {'id': 'e3', 'type': 'line', 'x': 5, 'y': 22, 'width': 90, 'height': 0.3,
                 'lineColor': '#000000', 'lineWidth': 0.3, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e4', 'type': 'text', 'content': '100 GR',
                 'x': 2, 'y': 24, 'width': 30, 'height': 6,
                 'fontFamily': 'Arial', 'fontSize': 7, 'fontWeight': 'bold',
                 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e5', 'type': 'variable', 'variable': 'precio_100g',
                 'x': 2, 'y': 30, 'width': 30, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 16, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
                {'id': 'e6', 'type': 'text', 'content': '¼ Kg',
                 'x': 35, 'y': 24, 'width': 30, 'height': 6,
                 'fontFamily': 'Arial', 'fontSize': 7, 'fontWeight': 'bold',
                 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e7', 'type': 'variable', 'variable': 'precio_250g',
                 'x': 35, 'y': 30, 'width': 30, 'height': 14,
                 'fontFamily': 'Arial Black', 'fontSize': 16, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 8, 'zIndex': 10},
                {'id': 'e8', 'type': 'shape', 'x': 66, 'y': 23, 'width': 32, 'height': 22,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.3, 'borderRadius': 1, 'zIndex': 3},
                {'id': 'e9', 'type': 'text', 'content': 'Kg',
                 'x': 68, 'y': 24, 'width': 28, 'height': 6,
                 'fontFamily': 'Arial', 'fontSize': 7, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e10', 'type': 'variable', 'variable': 'precio_1kg',
                 'x': 68, 'y': 30, 'width': 28, 'height': 14,
                 'fontFamily': 'Impact', 'fontSize': 20, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 10, 'zIndex': 10},
                {'id': 'e11', 'type': 'line', 'x': 5, 'y': 48, 'width': 90, 'height': 0.3,
                 'lineColor': '#cccccc', 'lineWidth': 0.2, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e12', 'type': 'text', 'content': 'VENTA AL PESO',
                 'x': 20, 'y': 50, 'width': 60, 'height': 16,
                 'fontFamily': 'Arial', 'fontSize': 8, 'fontWeight': 'bold',
                 'color': '#333333', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
            ]
        }
    },
    'weight_140x100': {
        'name': 'Peso Grande',
        'sign_type': 'weight',
        'width_mm': 140, 'height_mm': 100,
        'layout': {
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 0.5,
            'elements': [
                {'id': 'logo', 'type': 'image', 'src': LOGO_URL,
                 'x': 3, 'y': 2, 'width': 24, 'height': 10, 'zIndex': 20},
                {'id': 'e2', 'type': 'variable', 'variable': 'nombre_producto',
                 'x': 6, 'y': 13, 'width': 128, 'height': 16,
                 'fontFamily': 'Arial Black', 'fontSize': 18, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 11, 'zIndex': 10},
                {'id': 'e3', 'type': 'line', 'x': 8, 'y': 31, 'width': 124, 'height': 0.4,
                 'lineColor': '#000000', 'lineWidth': 0.4, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e4', 'type': 'text', 'content': '100 GR',
                 'x': 3, 'y': 34, 'width': 42, 'height': 10,
                 'fontFamily': 'Arial', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e5', 'type': 'variable', 'variable': 'precio_100g',
                 'x': 3, 'y': 44, 'width': 42, 'height': 20,
                 'fontFamily': 'Arial Black', 'fontSize': 22, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 12, 'zIndex': 10},
                {'id': 'e6', 'type': 'text', 'content': '¼ Kg',
                 'x': 49, 'y': 34, 'width': 42, 'height': 10,
                 'fontFamily': 'Arial', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#666666', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e7', 'type': 'variable', 'variable': 'precio_250g',
                 'x': 49, 'y': 44, 'width': 42, 'height': 20,
                 'fontFamily': 'Arial Black', 'fontSize': 22, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 12, 'zIndex': 10},
                {'id': 'e8', 'type': 'shape', 'x': 94, 'y': 33, 'width': 43, 'height': 34,
                 'backgroundColor': '#f0f0f0', 'borderColor': '#000000',
                 'borderWidth': 0.3, 'borderRadius': 2, 'zIndex': 3},
                {'id': 'e9', 'type': 'text', 'content': 'Kg',
                 'x': 96, 'y': 34, 'width': 39, 'height': 10,
                 'fontFamily': 'Arial', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
                {'id': 'e10', 'type': 'variable', 'variable': 'precio_1kg',
                 'x': 96, 'y': 44, 'width': 39, 'height': 20,
                 'fontFamily': 'Impact', 'fontSize': 28, 'fontWeight': 'bold',
                 'color': '#000000', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': True, 'minFontSize': 14, 'zIndex': 10},
                {'id': 'e11', 'type': 'line', 'x': 8, 'y': 70, 'width': 124, 'height': 0.3,
                 'lineColor': '#cccccc', 'lineWidth': 0.2, 'lineStyle': 'solid', 'zIndex': 5},
                {'id': 'e12', 'type': 'text', 'content': 'VENTA AL PESO',
                 'x': 30, 'y': 73, 'width': 80, 'height': 22,
                 'fontFamily': 'Arial', 'fontSize': 11, 'fontWeight': 'bold',
                 'color': '#333333', 'backgroundColor': 'transparent',
                 'textAlign': 'center', 'verticalAlign': 'middle',
                 'autoScale': False, 'zIndex': 10},
            ]
        }
    },
}


def ensure_default_templates():
    """Crea las plantillas predeterminadas si no existen."""
    created = 0
    for key, data in DEFAULT_LAYOUTS.items():
        exists = SignTemplate.objects.filter(
            sign_type=data['sign_type'],
            width_mm=data['width_mm'],
            height_mm=data['height_mm'],
            is_default=True,
        ).exists()
        if not exists:
            SignTemplate.objects.create(
                name=data['name'],
                sign_type=data['sign_type'],
                width_mm=data['width_mm'],
                height_mm=data['height_mm'],
                layout_json=json.dumps(data['layout']),
                is_default=True,
                is_active=True,
            )
            created += 1
    return created


class SignTemplate(models.Model):
    """Plantilla (molde) de cartel para inyectar datos de productos."""

    SIGN_TYPES = [
        ('simple', 'Cartel Simple (Precio Unitario)'),
        ('promo', 'Cartel Promocional (Llevá X por Y)'),
        ('bulk', 'Cartel de Bulto Cerrado (Caja/Bolsa)'),
        ('weight', 'Cartel de Venta al Peso'),
    ]

    PRESET_SIZES = {
        'simple': [
            {'label': '5 × 4 cm', 'width': 50, 'height': 40},
            {'label': '5 × 3 cm', 'width': 50, 'height': 30},
        ],
        'promo': [
            {'label': '7 × 5 cm', 'width': 70, 'height': 50},
            {'label': '10 × 7 cm', 'width': 100, 'height': 70},
        ],
        'bulk': [
            {'label': '10 × 7 cm', 'width': 100, 'height': 70},
            {'label': '14 × 10 cm (A6)', 'width': 140, 'height': 100},
        ],
        'weight': [
            {'label': '10 × 7 cm (apaisado)', 'width': 100, 'height': 70},
            {'label': '14 × 10 cm', 'width': 140, 'height': 100},
        ],
    }

    name = models.CharField('Nombre', max_length=200)
    sign_type = models.CharField('Tipo de Cartel', max_length=20, choices=SIGN_TYPES)
    width_mm = models.PositiveIntegerField('Ancho (mm)')
    height_mm = models.PositiveIntegerField('Alto (mm)')
    layout_json = models.TextField('Diseño (JSON)', default='{}', blank=True)

    @property
    def layout(self):
        try:
            return json.loads(self.layout_json) if self.layout_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @layout.setter
    def layout(self, value):
        self.layout_json = json.dumps(value) if value else '{}'

    is_active = models.BooleanField('Activo', default=True)
    is_default = models.BooleanField('Predeterminado', default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plantilla de Cartel'
        verbose_name_plural = 'Plantillas de Carteles'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.get_sign_type_display()}) - {self.width_mm}×{self.height_mm}mm"

    @property
    def size_label(self):
        w_cm = self.width_mm / 10
        h_cm = self.height_mm / 10
        return f"{w_cm:.0f} × {h_cm:.0f} cm"

    @classmethod
    def get_type_variables(cls, sign_type):
        """Variables disponibles para cada tipo de cartel."""
        VARIABLES = {
            'simple': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'SALADIX'},
                {'key': 'gramaje', 'label': 'Gramaje', 'sample': '100g'},
                {'key': 'precio_unitario', 'label': 'Precio Unitario', 'sample': '$790'},
            ],
            'promo': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'TURRON MISKY'},
                {'key': 'precio_unitario', 'label': 'Precio Unitario', 'sample': '$180'},
                {'key': 'cantidad_promo', 'label': 'Cantidad Promo', 'sample': '3'},
                {'key': 'precio_promo', 'label': 'Precio Promo', 'sample': '$500'},
                {'key': 'etiqueta_promo', 'label': 'Etiqueta (PROMO!!)', 'sample': 'PROMO!!'},
            ],
            'bulk': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'FEELING'},
                {'key': 'precio_total', 'label': 'Precio Total', 'sample': '$11.500'},
                {'key': 'tipo_empaque', 'label': 'Tipo de Empaque', 'sample': 'CAJA'},
                {'key': 'contenido_empaque', 'label': 'Contenido', 'sample': 'X 30U.'},
            ],
            'weight': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'ALMENDRAS PELADAS'},
                {'key': 'precio_100g', 'label': 'Precio 100g', 'sample': '$3.200'},
                {'key': 'precio_250g', 'label': 'Precio ¼ Kg', 'sample': '$7.350'},
                {'key': 'precio_1kg', 'label': 'Precio 1 Kg', 'sample': '$29.400'},
            ],
        }
        return VARIABLES.get(sign_type, [])


class SignBatch(models.Model):
    """Lote de carteles generados."""

    PAPER_SIZES = [
        ('A4', 'A4 (210 × 297 mm)'),
        ('A3', 'A3 (297 × 420 mm)'),
        ('letter', 'Carta (216 × 279 mm)'),
    ]

    name = models.CharField('Nombre', max_length=200, blank=True)
    template = models.ForeignKey(
        SignTemplate, on_delete=models.CASCADE,
        related_name='batches', verbose_name='Plantilla'
    )
    paper_size = models.CharField(
        'Tamaño de Papel', max_length=10,
        choices=PAPER_SIZES, default='A4'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lote de Carteles'
        verbose_name_plural = 'Lotes de Carteles'
        ordering = ['-created_at']

    def __str__(self):
        return f"Lote #{self.pk} - {self.template.name} ({self.created_at:%d/%m/%Y})"

    @property
    def total_signs(self):
        return sum(item.copies for item in self.items.all())


class SignItem(models.Model):
    """Item individual en un lote de carteles."""

    batch = models.ForeignKey(
        SignBatch, on_delete=models.CASCADE,
        related_name='items', verbose_name='Lote'
    )
    product = models.ForeignKey(
        'stocks.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Producto'
    )
    data_json = models.TextField('Datos (JSON)', default='{}', blank=True)

    @property
    def data(self):
        try:
            return json.loads(self.data_json) if self.data_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value) if value else '{}'
    copies = models.PositiveIntegerField('Copias', default=1)
    order = models.PositiveIntegerField('Orden', default=0)

    class Meta:
        verbose_name = 'Item de Cartel'
        verbose_name_plural = 'Items de Carteles'
        ordering = ['order']

    def __str__(self):
        name = self.data.get('nombre_producto', f'Item #{self.pk}')
        return f"{name} ×{self.copies}"
