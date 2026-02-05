"""
Models for the AI Assistant module.
Stores conversation history and user preferences.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversation(models.Model):
    """
    Represents a conversation session with the AI assistant.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assistant_conversations',
        verbose_name='Usuario'
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Título'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creada'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizada'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )

    class Meta:
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.title or 'Sin título'} ({self.created_at.strftime('%d/%m/%Y')})"

    def get_messages_for_api(self, limit=20):
        """
        Returns messages formatted for OpenAI API.
        """
        messages = self.messages.order_by('-created_at')[:limit]
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in reversed(messages)
        ]


class Message(models.Model):
    """
    Individual message in a conversation.
    """
    ROLE_CHOICES = [
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
        ('system', 'Sistema'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Conversación'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name='Rol'
    )
    content = models.TextField(
        verbose_name='Contenido'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado'
    )
    tokens_used = models.IntegerField(
        default=0,
        verbose_name='Tokens usados'
    )

    class Meta:
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}..."


class AssistantSettings(models.Model):
    """
    Global settings for the AI assistant.
    Singleton pattern - only one record should exist.
    """
    openai_api_key = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='OpenAI API Key',
        help_text='Clave API de OpenAI (sk-...)'
    )
    model = models.CharField(
        max_length=50,
        default='gpt-4o-mini',
        verbose_name='Modelo',
        help_text='Modelo de OpenAI a usar'
    )
    max_tokens = models.IntegerField(
        default=2000,
        verbose_name='Max Tokens',
        help_text='Máximo de tokens por respuesta'
    )
    temperature = models.FloatField(
        default=0.7,
        verbose_name='Temperatura',
        help_text='Creatividad (0.0 - 1.0)'
    )
    system_prompt = models.TextField(
        blank=True,
        verbose_name='Prompt del Sistema',
        help_text='Instrucciones base para el asistente'
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name='Habilitado'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = 'Configuración del Asistente'
        verbose_name_plural = 'Configuración del Asistente'

    def __str__(self):
        return f"Configuración del Asistente ({self.model})"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (only check on creation)
        if not self.pk and AssistantSettings.objects.exists():
            # If trying to create a new instance, get the existing one and update it instead
            existing = AssistantSettings.objects.first()
            self.pk = existing.pk
        self.pk = 1  # Force pk to always be 1
        return super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings_obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'system_prompt': cls.get_default_system_prompt()
            }
        )
        return settings_obj

    @classmethod
    def load(cls):
        """Alias for get_settings() for compatibility."""
        return cls.get_settings()

    @staticmethod
    def get_default_system_prompt():
        return """Eres el asistente virtual de CHE GOLOSO, un sistema de gestión de supermercado argentino.

Tu rol es ayudar al administrador y gerentes con:
- Análisis de ventas y tendencias
- Recomendaciones de negocio basadas en datos
- Gestión de inventario y alertas de stock
- Optimización de promociones
- Análisis de rentabilidad de productos
- Proyecciones y estadísticas

IMPORTANTE:
- Siempre responde en español argentino
- Usa formato de moneda argentina: $1.234,56
- Sé conciso pero informativo
- Cuando des recomendaciones, basalas en los datos disponibles
- Si no tienes suficiente información, pídela amablemente
- Puedes usar emojis para hacer la conversación más amigable
- Siempre menciona el período de tiempo de los datos que analizas

Tienes acceso a datos en tiempo real del sistema incluyendo:
- Ventas y transacciones
- Inventario y stock
- Productos y categorías
- Promociones activas
- Gastos y compras
- Información de la caja"""


class QueryLog(models.Model):
    """
    Logs queries made to the assistant for analytics.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Usuario'
    )
    query = models.TextField(
        verbose_name='Consulta'
    )
    query_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Tipo de consulta'
    )
    response_time_ms = models.IntegerField(
        default=0,
        verbose_name='Tiempo de respuesta (ms)'
    )
    tokens_used = models.IntegerField(
        default=0,
        verbose_name='Tokens usados'
    )
    was_successful = models.BooleanField(
        default=True,
        verbose_name='Exitosa'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Mensaje de error'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha'
    )

    class Meta:
        verbose_name = 'Log de Consulta'
        verbose_name_plural = 'Logs de Consultas'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.query[:50]}... ({self.created_at.strftime('%d/%m/%Y %H:%M')})"
