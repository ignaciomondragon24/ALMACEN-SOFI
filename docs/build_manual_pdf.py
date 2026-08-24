"""
Genera docs/Manual-Lo-de-Josefina.pdf a partir de los .md en docs/manual/.
Uso: python docs/build_manual_pdf.py
"""
import base64
import os
import re
from datetime import datetime
from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parent
MANUAL_DIR = ROOT / 'manual'
IMAGES_DIR = MANUAL_DIR / 'images'
OUT_PDF = ROOT / 'Manual-Lo-de-Josefina.pdf'

MESES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

ORDER = [
    '00-Indice.md',
    '01-Crear-y-modificar-productos.md',
    '02-Compras-y-recepcion.md',
    '03-Vender-por-el-POS.md',
    '04-Venta-por-Peso.md',
    '05-Ajustes-de-stock.md',
    '06-Cierre-de-caja.md',
    '07-Reportes.md',
    '08-Vencimientos.md',
    '09-Promociones.md',
    '10-Medios-de-pago.md',
    '11-Usuarios-y-permisos.md',
]

CSS = """
@page {
    size: A4;
    margin: 2.2cm 2cm 2cm 2cm;
    @frame footer {
        -pdf-frame-content: footerContent;
        left: 2cm; right: 2cm;
        bottom: 1cm; height: 0.7cm;
    }
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1a1a2e;
    line-height: 1.5;
}
.cover {
    text-align: center;
    padding-top: 6cm;
}
.cover h1 {
    font-size: 42pt;
    color: #C33287;
    margin: 0 0 10pt 0;
    border: 0;
}
.cover .sub {
    font-size: 16pt;
    color: #7134B6;
    margin-bottom: 30pt;
}
.cover .meta {
    font-size: 11pt;
    color: #666;
    margin-top: 2cm;
}
h1 {
    color: #C33287;
    font-size: 22pt;
    border-bottom: 2pt solid #C33287;
    padding-bottom: 4pt;
    margin-top: 0;
    -pdf-keep-with-next: true;
}
h2 {
    color: #7134B6;
    font-size: 15pt;
    margin-top: 18pt;
    margin-bottom: 6pt;
    -pdf-keep-with-next: true;
}
h3 {
    color: #7134B6;
    font-size: 12pt;
    margin-top: 12pt;
    margin-bottom: 4pt;
    -pdf-keep-with-next: true;
}
p { margin: 4pt 0 8pt 0; }
ul, ol { margin: 4pt 0 10pt 16pt; }
li { margin-bottom: 3pt; }
strong { color: #7134B6; }
code {
    font-family: Courier, monospace;
    background: #f4f4f8;
    padding: 1pt 4pt;
    border-radius: 2pt;
    font-size: 10pt;
    color: #c7296b;
}
pre {
    background: #f4f4f8;
    border-left: 3pt solid #C33287;
    padding: 8pt 10pt;
    font-family: Courier, monospace;
    font-size: 9.5pt;
    color: #7134B6;
    margin: 8pt 0;
    white-space: pre-wrap;
}
hr {
    border: 0;
    border-top: 1pt solid #ddd;
    margin: 14pt 0;
}
a { color: #C33287; text-decoration: none; }
.page-break { page-break-before: always; }
.footer {
    text-align: center;
    font-size: 8pt;
    color: #999;
}
.tag-regla {
    background: #fff3e0;
    border-left: 3pt solid #F5D050;
    padding: 6pt 10pt;
    margin: 6pt 0;
    font-size: 10pt;
}
.figure {
    margin: 10pt 0 14pt 0;
    text-align: center;
    -pdf-keep-with-next: false;
}
.figure img {
    width: 100%;
    border: 1pt solid #ddd;
    border-radius: 4pt;
}
.figure .caption {
    font-size: 9pt;
    color: #7134B6;
    margin-top: 4pt;
    text-align: center;
}
"""


def md_to_html_body(md_text: str) -> str:
    # Bajar todos los headings un nivel para que h1 sea único por sección.
    html = markdown.markdown(
        md_text,
        extensions=['extra', 'sane_lists'],
    )
    return html


def embed_images(html: str) -> str:
    """Convierte <img src="images/x.jpg" alt="caption"> en una figura con
    la imagen embebida como base64 (sin depender de rutas relativas) y
    su caption debajo, usando el texto alt como leyenda."""

    def _replace(m):
        tag = m.group(0)
        src_m = re.search(r'src="([^"]+)"', tag)
        alt_m = re.search(r'alt="([^"]*)"', tag)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        img_path = IMAGES_DIR / Path(src).name
        if not img_path.exists():
            return m.group(0)
        data = base64.b64encode(img_path.read_bytes()).decode('ascii')
        ext = img_path.suffix.lstrip('.').lower()
        mime = 'jpeg' if ext in ('jpg', 'jpeg') else ext
        caption_html = f'<div class="caption">{alt}</div>' if alt else ''
        # Las capturas angostas (ej: ticket 58mm) no deben estirarse a todo
        # el ancho de la página — se limitan a un tamaño razonable.
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
        style = ' style="width:45%;"' if h > w else ''
        return (
            f'<div class="figure">'
            f'<img src="data:image/{mime};base64,{data}"{style}/>'
            f'{caption_html}'
            f'</div>'
        )

    return re.sub(r'<img[^>]*/?>', _replace, html)


def fix_internal_links(html: str) -> str:
    # Los links entre .md no sirven en PDF; los convertimos a texto plano
    # "(ver sección X)" — más útil que un link roto.
    return re.sub(
        r'<a href="(\d+)-[^"]*\.md"[^>]*>([^<]+)</a>',
        r'<strong>\2</strong>',
        html,
    )


def build_html() -> str:
    sections_html = []

    # Portada
    sections_html.append(f"""
    <div class="cover">
        <h1>LO DE JOSEFINA</h1>
        <div class="sub">Manual de uso del sistema — almacén de barrio</div>
        <div class="meta">Guía práctica para el equipo del local<br/>Versión {MESES_ES[datetime.now().month - 1]} {datetime.now().year}</div>
    </div>
    <div class="page-break"></div>
    """)

    for idx, filename in enumerate(ORDER):
        path = MANUAL_DIR / filename
        md_text = path.read_text(encoding='utf-8')
        html = md_to_html_body(md_text)
        html = fix_internal_links(html)
        html = embed_images(html)
        sections_html.append(html)
        # Salto de página entre secciones (no después de la última)
        if idx < len(ORDER) - 1:
            sections_html.append('<div class="page-break"></div>')

    body = '\n'.join(sections_html)
    footer = '<div id="footerContent" class="footer">Manual LO DE JOSEFINA · página <pdf:pagenumber/></div>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <style>{CSS}</style>
</head>
<body>
    {footer}
    {body}
</body>
</html>
"""


def main() -> int:
    html = build_html()
    with OUT_PDF.open('wb') as f:
        result = pisa.CreatePDF(src=html, dest=f, encoding='utf-8')
    if result.err:
        print(f'ERROR al generar PDF: {result.err}')
        return 1
    print(f'OK PDF generado: {OUT_PDF}')
    print(f'    Tamaño: {OUT_PDF.stat().st_size / 1024:.1f} KB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
