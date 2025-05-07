from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
import json

from .services.ai_service import AITextService

@login_required
@require_POST
@ensure_csrf_cookie
def generate_text(request):
    """API endpoint for generating text content using AI"""
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '')
        tone = data.get('tone', 'professional')
        max_tokens = data.get('max_tokens', 500)
        
        if not prompt:
            return JsonResponse({'error': 'Prompt is required'}, status=400)
        
        generated_text = AITextService.generate_content(prompt, tone, max_tokens)
        
        if generated_text.startswith('Error:'):
            return JsonResponse({'error': generated_text}, status=500)
        
        return JsonResponse({'text': generated_text})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def rephrase_text(request):
    """API endpoint for rephrasing text using AI"""
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        tone = data.get('tone', 'professional')
        max_tokens = data.get('max_tokens', 300)
        
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        
        rephrased_text = AITextService.rephrase_text(text, tone, max_tokens)
        
        if rephrased_text.startswith('Error:'):
            return JsonResponse({'error': rephrased_text}, status=500)
        
        return JsonResponse({'text': rephrased_text})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def generate_suggestions(request):
    """API endpoint for generating multiple text suggestions using AI"""
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        suggestion_count = data.get('suggestion_count', 3)
        max_tokens = data.get('max_tokens', 300)
        
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        
        suggestions = AITextService.generate_suggestions(text, suggestion_count, max_tokens)
        
        if suggestions and suggestions[0].startswith('Error:'):
            return JsonResponse({'error': suggestions[0]}, status=500)
        
        return JsonResponse({'suggestions': suggestions})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)