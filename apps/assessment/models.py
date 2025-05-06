
from django.db import models
from django.conf import settings
from apps.content.models import Course

class Quiz(models.Model):
    """Model for quizzes and assessments"""
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    is_ai_generated = models.BooleanField(default=False)  # New field to track AI-generated content
    
    def __str__(self):
        return f"{self.title} ({self.course.title})"
    
    def grade_quiz(self, student):
        """Calculate the total score for a student's quiz submission"""
        # Get all answers from this student for this quiz
        answers = Answer.objects.filter(
            question__quiz=self,
            student=student
        )
        
        total_score = 0
        total_questions = self.questions.count()
        
        for answer in answers:
            if answer.is_correct:
                total_score += 1
                
        if total_questions > 0:
            percentage = (total_score / total_questions) * 100
        else:
            percentage = 0
            
        return {
            'total_score': total_score,
            'total_questions': total_questions,
            'percentage': percentage
        }
    
    class Meta:
        app_label = 'assessment'


class Question(models.Model):
    """Model for questions within quizzes"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=50, choices=[
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ])
    is_ai_generated = models.BooleanField(default=False)  # New field to track AI-generated content
    
    def __str__(self):
        return f"Question: {self.text[:50]}..."
    
    def validate_answer(self, answer_text):
        """Validate if an answer is correct"""
        if self.question_type == 'multiple_choice':
            # For multiple choice, check if the selected option is marked as correct
            try:
                option = self.options.get(text=answer_text)
                return option.is_correct
            except:
                return False
                
        elif self.question_type == 'true_false':
            # For true/false, check if the answer matches the correct answer
            correct_answer = self.options.filter(is_correct=True).first()
            if correct_answer:
                return answer_text.lower() == correct_answer.text.lower()
            return False
            
        elif self.question_type == 'short_answer':
            # For short answer, some logic to check against possible answers
            # This is simplified - in a real app you'd want more sophisticated matching
            correct_answers = self.options.filter(is_correct=True).values_list('text', flat=True)
            return answer_text.lower() in [ans.lower() for ans in correct_answers]
            
        elif self.question_type == 'essay':
            # Essay questions typically need manual grading
            return None
            
        return False
    
    class Meta:
        app_label = 'assessment'

class QuestionOption(models.Model):
    """Model for options in multiple choice and true/false questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"
    
    class Meta:
        app_label = 'assessment'


class Answer(models.Model):
    """Model for storing student answers to questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='question_answers')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('question', 'student')  # Each student can only answer each question once
        app_label = 'assessment'
    
    def __str__(self):
        return f"Answer by {self.student.username} to {self.question}"