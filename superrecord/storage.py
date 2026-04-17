"""
Storage custom para WhiteNoise: usa hash en el nombre de archivo
(pos-dark.a3f5b2.css) para que cada deploy invalide la cache del navegador
automaticamente sin requerir Ctrl+Shift+R.

manifest_strict=False evita que un referencia a un archivo inexistente
(por ejemplo un url() en un CSS apuntando a una imagen que ya no esta)
tire abajo todo el collectstatic.
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
