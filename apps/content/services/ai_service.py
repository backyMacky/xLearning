import requests
import json
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class AITextService:
    """Service for generating and enhancing text content using AI"""
    
    OPENAI_API_KEY = getattr(settings, 'OPENAI_API_KEY', os.environ.get('OPENAI_API_KEY', ''))
    API_URL = "https://api.openai.com/v1/chat/completions"
    
    TONES = {
        'professional': 'professional and formal',
        'casual': 'casual and conversational',
        'academic': 'academic and scholarly',
        'concise': 'concise and to the point',
        'enthusiastic': 'enthusiastic and engaging',
        'friendly': 'friendly and approachable',
        'technical': 'technical and detailed',
        'simple': 'simple and easy to understand',
    }
    
    @classmethod
    def generate_content(cls, prompt, tone='professional', max_tokens=500):
        """
        Generate content based on a user prompt and specified tone
        
        Args:
            prompt (str): The user's instructions for content generation
            tone (str): The tone of the generated content
            max_tokens (int): Maximum length of the generated content
            
        Returns:
            str: The generated content or error message
        """
        if not cls.OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            return "Error: AI service is not properly configured. Please contact the administrator."
        
        # Get the tone description
        tone_description = cls.TONES.get(tone, cls.TONES['professional'])
        
        # Prepare the message payload
        messages = [
            {"role": "system", "content": f"You are a helpful assistant that generates content in a {tone_description} tone."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = requests.post(
                cls.API_URL,
                headers={
                    "Authorization": f"Bearer {cls.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": max_tokens
                },
                timeout=30  # Set a reasonable timeout
            )
            
            if response.status_code == 200:
                response_data = response.json()
                generated_text = response_data['choices'][0]['message']['content'].strip()
                return generated_text
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return f"Error: Unable to generate content (Status code: {response.status_code})"
                
        except Exception as e:
            logger.exception(f"Exception during AI content generation: {str(e)}")
            return f"Error: {str(e)}"
    
    @classmethod
    def rephrase_text(cls, text, tone='professional', max_tokens=300):
        """
        Rephrase the given text in the specified tone
        
        Args:
            text (str): The text to rephrase
            tone (str): The desired tone for the rephrased text
            max_tokens (int): Maximum length of the rephrased text
            
        Returns:
            str: The rephrased text or error message
        """
        if not cls.OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            return "Error: AI service is not properly configured. Please contact the administrator."
        
        # Get the tone description
        tone_description = cls.TONES.get(tone, cls.TONES['professional'])
        
        # Prepare the prompt
        prompt = f"Rephrase the following text in a {tone_description} tone: \n\n{text}"
        
        # Prepare the message payload
        messages = [
            {"role": "system", "content": "You are a helpful assistant that rephrases text while preserving its meaning."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = requests.post(
                cls.API_URL,
                headers={
                    "Authorization": f"Bearer {cls.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                rephrased_text = response_data['choices'][0]['message']['content'].strip()
                return rephrased_text
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return f"Error: Unable to rephrase text (Status code: {response.status_code})"
                
        except Exception as e:
            logger.exception(f"Exception during AI text rephrasing: {str(e)}")
            return f"Error: {str(e)}"
            
    @classmethod
    def generate_suggestions(cls, text, suggestion_count=3, max_tokens=300):
        """
        Generate multiple alternative versions of the given text
        
        Args:
            text (str): The text to generate alternatives for
            suggestion_count (int): Number of suggestions to generate
            max_tokens (int): Maximum tokens per suggestion
            
        Returns:
            list: A list of text suggestions
        """
        if not cls.OPENAI_API_KEY:
            logger.error("OpenAI API key is not configured")
            return ["Error: AI service is not properly configured. Please contact the administrator."]
        
        # Prepare the prompt
        prompt = f"Generate {suggestion_count} different ways to rephrase the following text, preserving its meaning but varying the style and wording: \n\n{text}\n\nProvide the suggestions in a JSON array format with each suggestion as a string."
        
        # Prepare the message payload
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates multiple paraphrased versions of text."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = requests.post(
                cls.API_URL,
                headers={
                    "Authorization": f"Bearer {cls.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                content = response_data['choices'][0]['message']['content'].strip()
                
                # Try to extract JSON array from response
                try:
                    # Find JSON content in the response
                    start_idx = content.find('[')
                    end_idx = content.rfind(']') + 1
                    
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = content[start_idx:end_idx]
                        suggestions = json.loads(json_str)
                        if isinstance(suggestions, list) and len(suggestions) > 0:
                            return suggestions
                except json.JSONDecodeError:
                    # If we can't parse as JSON, use fallback approach
                    pass
                
                # Fallback: Split by numbered items
                suggestions = []
                lines = content.split('\n')
                current_suggestion = ""
                
                for line in lines:
                    if line.strip().startswith(('1.', '2.', '3.', '4.', '5.')):
                        if current_suggestion:
                            suggestions.append(current_suggestion.strip())
                        current_suggestion = line.split('.', 1)[1].strip()
                    elif current_suggestion:
                        current_suggestion += " " + line.strip()
                
                if current_suggestion:
                    suggestions.append(current_suggestion.strip())
                
                if not suggestions:
                    # Last resort: just split the content into paragraphs
                    suggestions = [p.strip() for p in content.split('\n\n') if p.strip()]
                
                return suggestions[:suggestion_count]
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return [f"Error: Unable to generate suggestions (Status code: {response.status_code})"]
                
        except Exception as e:
            logger.exception(f"Exception during AI suggestion generation: {str(e)}")
            return [f"Error: {str(e)}"]