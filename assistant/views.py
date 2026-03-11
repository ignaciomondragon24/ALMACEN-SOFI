"""
Views for the AI Assistant module.
"""
import json
import logging
import os

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings as django_settings

from .models import Conversation, Message, AssistantSettings, QueryLog
from .services import AssistantService
from decorators.decorators import group_required

logger = logging.getLogger(__name__)


@login_required
def assistant_home(request):
    """
    Main assistant page with chat interface.
    """
    # Get or create active conversation for the user
    conversation = Conversation.objects.filter(
        user=request.user,
        is_active=True
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(
            user=request.user,
            title='Nueva conversación'
        )
    
    # Get conversation history
    messages_list = conversation.messages.order_by('created_at')
    
    # Get service for insights and suggestions
    service = AssistantService()
    insights = service.get_quick_insights()
    suggested_questions = service.get_suggested_questions()
    
    # Check if assistant is configured
    settings_obj = AssistantSettings.get_settings()
    is_configured = bool(settings_obj.openai_api_key) or bool(getattr(django_settings, 'GEMINI_API_KEY', None)) or bool(os.getenv('GEMINI_API_KEY'))
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'insights': insights,
        'suggested_questions': suggested_questions,
        'is_configured': is_configured,
        'settings': settings_obj,
    }
    
    return render(request, 'assistant/chat.html', context)


@login_required
@require_POST
def send_message(request):
    """
    API endpoint to send a message to the assistant.
    Returns JSON response.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'El mensaje no puede estar vacío'
            }, status=400)
        
        # Get or create conversation
        if conversation_id:
            conversation = get_object_or_404(
                Conversation,
                id=conversation_id,
                user=request.user
            )
        else:
            conversation = Conversation.objects.create(
                user=request.user,
                title=user_message[:50] + '...' if len(user_message) > 50 else user_message
            )
        
        # Get response from assistant
        service = AssistantService()
        result = service.chat(
            user_message=user_message,
            conversation=conversation,
            include_context=True
        )
        
        # Log the query
        QueryLog.objects.create(
            user=request.user,
            query=user_message,
            response_time_ms=result.get('elapsed_ms', 0),
            tokens_used=result.get('tokens_used', 0),
            was_successful=result['success'],
            error_message=result.get('error', '')
        )
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'response': result['response'],
                'conversation_id': conversation.id,
                'tokens_used': result.get('tokens_used', 0)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error desconocido')
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato de datos inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_message: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST  
def new_conversation(request):
    """
    Start a new conversation.
    """
    # Deactivate current conversations
    Conversation.objects.filter(
        user=request.user,
        is_active=True
    ).update(is_active=False)
    
    # Create new conversation
    conversation = Conversation.objects.create(
        user=request.user,
        title='Nueva conversación'
    )
    
    return JsonResponse({
        'success': True,
        'conversation_id': conversation.id
    })


@login_required
@require_GET
def conversation_history(request):
    """
    Get list of past conversations.
    """
    conversations = Conversation.objects.filter(
        user=request.user
    ).order_by('-updated_at')[:20]
    
    data = [{
        'id': c.id,
        'title': c.title,
        'created_at': c.created_at.strftime('%d/%m/%Y %H:%M'),
        'updated_at': c.updated_at.strftime('%d/%m/%Y %H:%M'),
        'is_active': c.is_active,
        'message_count': c.messages.count()
    } for c in conversations]
    
    return JsonResponse({
        'success': True,
        'conversations': data
    })


@login_required
@require_GET
def load_conversation(request, conversation_id):
    """
    Load a specific conversation.
    """
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=request.user
    )
    
    # Set this as active and deactivate others
    Conversation.objects.filter(
        user=request.user,
        is_active=True
    ).update(is_active=False)
    
    conversation.is_active = True
    conversation.save()
    
    messages_data = [{
        'role': m.role,
        'content': m.content,
        'created_at': m.created_at.strftime('%H:%M')
    } for m in conversation.messages.order_by('created_at')]
    
    return JsonResponse({
        'success': True,
        'conversation': {
            'id': conversation.id,
            'title': conversation.title,
            'messages': messages_data
        }
    })


@login_required
@require_GET
def get_insights(request):
    """
    Get quick insights without AI call.
    """
    service = AssistantService()
    insights = service.get_quick_insights()
    
    return JsonResponse({
        'success': True,
        'insights': insights
    })


@login_required
@group_required('Admin', 'Manager')
def assistant_settings(request):
    """
    Settings page for the assistant (admin only).
    """
    settings_obj = AssistantSettings.get_settings()
    
    if request.method == 'POST':
        settings_obj.openai_api_key = request.POST.get('openai_api_key', '')
        settings_obj.model = request.POST.get('model', 'gemini-2.0-flash')
        
        # Validate numeric fields
        try:
            max_tokens = request.POST.get('max_tokens', '2000').strip()
            settings_obj.max_tokens = int(max_tokens) if max_tokens else 2000
        except ValueError:
            settings_obj.max_tokens = 2000
        
        try:
            temperature = request.POST.get('temperature', '0.7').strip()
            settings_obj.temperature = float(temperature) if temperature else 0.7
        except ValueError:
            settings_obj.temperature = 0.7
        
        settings_obj.system_prompt = request.POST.get('system_prompt', '')
        settings_obj.is_enabled = request.POST.get('is_enabled') == 'on'
        settings_obj.save()
        
        messages.success(request, 'Configuración guardada correctamente')
        return redirect('assistant:settings')
    
    # Get usage stats
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    usage_stats = QueryLog.objects.filter(
        created_at__gte=thirty_days_ago
    ).aggregate(
        total_queries=Count('id'),
        total_tokens=Sum('tokens_used'),
        avg_response_time=Avg('response_time_ms')
    )
    
    context = {
        'settings': settings_obj,
        'usage_stats': usage_stats,
        'available_models': [
            ('gemini-2.5-flash', 'Gemini 2.5 Flash (Recomendado)'),
            ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
            ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
            ('gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite'),
        ]
    }
    
    return render(request, 'assistant/settings.html', context)


@login_required
@group_required('Admin')
def query_logs(request):
    """
    View query logs (admin only).
    """
    logs = QueryLog.objects.select_related('user').order_by('-created_at')
    
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    context = {
        'logs': logs_page,
    }
    
    return render(request, 'assistant/logs.html', context)


# Import Count and Avg for the settings view
from django.db.models import Count, Avg
