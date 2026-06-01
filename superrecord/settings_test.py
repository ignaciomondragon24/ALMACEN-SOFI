"""Settings para el entorno de tests local.

Hereda de settings.py y silencia el check de ImageField/Pillow para que
los tests corran aunque Pillow no esté disponible en el entorno de CI local.
En producción Pillow sí está instalado, así que el check no aplica allá.
"""
from superrecord.settings import *  # noqa: F401, F403

SILENCED_SYSTEM_CHECKS = [
    'fields.E210',  # ImageField sin Pillow
]
