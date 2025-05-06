
import os
import requests
import json
from django.conf import settings

class AIContentService:
    """Service for interacting with AI APIs for content generation and enhancement"""
    
    @staticmethod
    def rewrite_text(text, style=None):
        """
        Rewrite text using ChatGPT 4o-mini API
        
        Args:
            text (str): The text to rewrite
            style (str, optional): The style to use for rewriting (formal, casual, concise, etc.)
            
        Returns:
            dict: Response containing suggestions and status
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "message": "API key not configured",
                "suggestions": []
            }
            
        api_url = "https://api.openai.com/v1/chat/completions"
        
        # Prepare the prompt based on style
        if style:
            prompt = f"Rewrite the following text in a {style} style. Provide 3 alternatives:\n\n{text}"
        else:
            prompt = f"Rewrite the following text to improve clarity and readability. Provide 3 alternatives:\n\n{text}"
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful writing assistant. Your task is to rewrite text to improve clarity and match the requested style. Always provide exactly 3 distinct rewrite options."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            response_data = response.json()
            assistant_message = response_data["choices"][0]["message"]["content"]
            
            # Parse the response to extract the suggestions
            # This is a simple parser that assumes the response has numbered options
            suggestions = []
            lines = assistant_message.split("\n")
            current_suggestion = ""
            
            for line in lines:
                if line.strip().startswith(("1.", "2.", "3.")):
                    if current_suggestion and current_suggestion not in suggestions:
                        suggestions.append(current_suggestion.strip())
                    current_suggestion = line.split(".", 1)[1].strip()
                elif current_suggestion:
                    current_suggestion += " " + line.strip()
            
            # Add the last suggestion if it exists
            if current_suggestion and current_suggestion not in suggestions:
                suggestions.append(current_suggestion.strip())
            
            # If we couldn't parse properly, just return the raw response
            if not suggestions:
                suggestions = [assistant_message]
            
            return {
                "success": True,
                "message": "Successfully generated suggestions",
                "suggestions": suggestions
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"API request failed: {str(e)}",
                "suggestions": []
            }
            
    @staticmethod
    def generate_quiz_questions(topic, num_questions=5, difficulty="medium"):
        """
        Generate quiz questions using ChatGPT 4o-mini API
        
        Args:
            topic (str): The topic to generate questions about
            num_questions (int): Number of questions to generate
            difficulty (str): Difficulty level (easy, medium, hard)
            
        Returns:
            dict: Response containing generated questions and status
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "message": "API key not configured",
                "questions": []
            }
            
        api_url = "https://api.openai.com/v1/chat/completions"
        
        # Prepare the prompt
        prompt = f"Generate {num_questions} {difficulty} multiple-choice quiz questions about {topic}. For each question, provide 4 options and indicate the correct answer. Format the response as a JSON array of objects with 'question', 'options' (array), and 'correct_option' (index) fields."
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful education assistant. Your task is to generate high-quality quiz questions in JSON format."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            response_data = response.json()
            assistant_message = response_data["choices"][0]["message"]["content"]
            
            # Parse the JSON response
            try:
                parsed_data = json.loads(assistant_message)
                
                # If the response is not in the expected format, try to extract questions
                if "questions" in parsed_data:
                    questions = parsed_data["questions"]
                else:
                    questions = parsed_data
                
                return {
                    "success": True,
                    "message": "Successfully generated questions",
                    "questions": questions
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "message": "Failed to parse response JSON",
                    "questions": []
                }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"API request failed: {str(e)}",
                "questions": []
            }