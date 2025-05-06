from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Count, Q, Avg, Sum
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper
from web_project.ai_services import AIContentService
import json
from .models import Quiz, Question, QuestionOption, Answer
from apps.content.models import Course

# Base class for assessment views with common functionality
class AssessmentBaseView(LoginRequiredMixin):
    """Base class for assessment views with common template functionality"""
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set active menu attributes for assessment section
        context['active_menu'] = 'assessment'
        context['active_submenu'] = 'assessment-quizzes'
        
        # Set the layout path using TemplateHelper
        context['layout_path'] = TemplateHelper.set_layout("layout_vertical.html", context)
        TemplateHelper.map_context(context)
        
        return context

class QuizListView(AssessmentBaseView, ListView):
    """View to list all quizzes available to the user"""
    model = Quiz
    template_name = 'quiz_list.html'
    context_object_name = 'quizzes'
    paginate_by = 10
    
    def get_queryset(self):
        if self.request.user.is_teacher:
            # Teachers see quizzes they created
            return Quiz.objects.filter(teacher=self.request.user).select_related('course')
        else:
            # Students see quizzes from courses they're enrolled in
            enrolled_courses = self.request.user.enrolled_courses.all()
            return Quiz.objects.filter(course__in=enrolled_courses).select_related('course')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add counts for different quiz statuses for teachers
        if self.request.user.is_teacher:
            context['total_quizzes'] = self.get_queryset().count()
            
            # Get student performance metrics for teacher's quizzes
            quiz_ids = self.get_queryset().values_list('id', flat=True)
            
            # Calculate average scores across all quizzes
            total_correct = Answer.objects.filter(
                question__quiz_id__in=quiz_ids,
                is_correct=True
            ).count()
            
            total_answers = Answer.objects.filter(
                question__quiz_id__in=quiz_ids
            ).count()
            
            if total_answers > 0:
                context['avg_score'] = round((total_correct / total_answers) * 100)
            else:
                context['avg_score'] = 0
                
            # Get total number of students who have taken the quizzes
            context['student_count'] = Answer.objects.filter(
                question__quiz_id__in=quiz_ids
            ).values('student').distinct().count()
            
        # For students, get their quiz statistics
        else:
            # Get completed quizzes (where student has at least one answer)
            student_answers = Answer.objects.filter(student=self.request.user)
            completed_quiz_ids = student_answers.values_list('question__quiz', flat=True).distinct()
            context['completed_quizzes'] = completed_quiz_ids.count()
            
            # Calculate average score
            correct_answers = student_answers.filter(is_correct=True).count()
            if student_answers.count() > 0:
                context['avg_score'] = round((correct_answers / student_answers.count()) * 100)
            else:
                context['avg_score'] = 0
            
            # Get available quizzes count
            context['available_quizzes'] = self.get_queryset().exclude(id__in=completed_quiz_ids).count()
            
        return context

class QuizDetailView(AssessmentBaseView, DetailView):
    """View a specific quiz details"""
    model = Quiz
    template_name = 'quiz_detail.html'
    context_object_name = 'quiz'
    pk_url_kwarg = 'quiz_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz = self.get_object()
        
        # Check if user has access to this quiz
        if self.request.user.is_teacher and quiz.teacher != self.request.user:
            return redirect('assessment:quiz_list')
        
        if self.request.user.is_student and quiz.course not in self.request.user.enrolled_courses.all():
            return redirect('assessment:quiz_list')
        
        # Get all questions for this quiz
        context['questions'] = quiz.questions.all().prefetch_related('options')
        
        # If student has already taken the quiz, show results
        if self.request.user.is_student:
            taken = Answer.objects.filter(
                question__quiz=quiz,
                student=self.request.user
            ).exists()
            context['taken'] = taken
            
            if taken:
                # Get student's results
                results = quiz.grade_quiz(self.request.user)
                context['results'] = results
                
                # Get student's answers
                context['answers'] = Answer.objects.filter(
                    question__quiz=quiz,
                    student=self.request.user
                ).select_related('question')
        else:
            # For teachers, show stats about quiz performance
            context['taken'] = False
            
            # Get quiz statistics
            total_submissions = Answer.objects.filter(
                question__quiz=quiz
            ).values('student').distinct().count()
            
            context['total_submissions'] = total_submissions
            
            if total_submissions > 0:
                # Calculate average score
                correct_answers = Answer.objects.filter(
                    question__quiz=quiz,
                    is_correct=True
                ).count()
                
                total_answers = Answer.objects.filter(
                    question__quiz=quiz
                ).count()
                
                if total_answers > 0:
                    context['avg_score'] = round((correct_answers / total_answers) * 100)
                else:
                    context['avg_score'] = 0
                    
                # Get students who took the quiz
                context['students'] = Answer.objects.filter(
                    question__quiz=quiz
                ).values('student__username', 'student__id').distinct()
        
        return context

class QuizCreateView(AssessmentBaseView, UserPassesTestMixin, CreateView):
    """Create a new quiz (for teachers)"""
    model = Quiz
    template_name = 'quiz_form.html'
    fields = ['title', 'course']
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter courses to only show courses taught by this teacher
        form.fields['course'].queryset = Course.objects.filter(teacher=self.request.user)
        return form
    
    def form_valid(self, form):
        form.instance.teacher = self.request.user
        
        # Check if this is an AI-generated quiz
        generated_questions = self.request.POST.get('generated_questions')
        if generated_questions:
            form.instance.is_ai_generated = True
        
        response = super().form_valid(form)
        
        # If AI-generated questions are included, add them
        if generated_questions:
            try:
                questions_data = json.loads(generated_questions)
                
                for q_data in questions_data:
                    # Create question
                    question = Question.objects.create(
                        quiz=self.object,
                        text=q_data['question'],
                        question_type='multiple_choice',
                        is_ai_generated=True
                    )
                    
                    # Create options
                    for i, option_text in enumerate(q_data['options']):
                        QuestionOption.objects.create(
                            question=question,
                            text=option_text,
                            is_correct=(i == q_data['correct_option'])
                        )
            except Exception as e:
                messages.error(self.request, f"Error adding AI-generated questions: {str(e)}")
        
        return response
    
    def get_success_url(self):
        return reverse('assessment:edit_quiz', kwargs={'quiz_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Set course if provided in URL
        course_id = self.kwargs.get('course_id')
        if course_id:
            course = get_object_or_404(Course, id=course_id, teacher=self.request.user)
            context['selected_course'] = course
            
        context['title'] = 'Create New Quiz'
        context['submit_text'] = 'Create Quiz'
        
        return context

class QuizUpdateView(AssessmentBaseView, UserPassesTestMixin, UpdateView):
    """Edit an existing quiz (for teachers)"""
    model = Quiz
    template_name = 'quiz_form.html'
    context_object_name = 'quiz'
    fields = ['title', 'course']
    pk_url_kwarg = 'quiz_id'
    
    def test_func(self):
        quiz = self.get_object()
        return self.request.user == quiz.teacher or self.request.user.is_superuser
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter courses to only show courses taught by this teacher
        form.fields['course'].queryset = Course.objects.filter(teacher=self.request.user)
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        quiz = self.get_object()
        context['questions'] = quiz.questions.all().prefetch_related('options')
        context['title'] = f'Edit Quiz: {quiz.title}'
        context['submit_text'] = 'Update Quiz'
        
        return context
    
    def get_success_url(self):
        return reverse('assessment:quiz_detail', kwargs={'quiz_id': self.object.id})

class QuizDeleteView(AssessmentBaseView, UserPassesTestMixin, DeleteView):
    """Delete a quiz (for teachers)"""
    model = Quiz
    template_name = 'quiz_confirm_delete.html'
    context_object_name = 'quiz'
    pk_url_kwarg = 'quiz_id'
    success_url = reverse_lazy('assessment:quiz_list')
    
    def test_func(self):
        quiz = self.get_object()
        return self.request.user == quiz.teacher or self.request.user.is_superuser

class QuestionCreateView(AssessmentBaseView, UserPassesTestMixin, CreateView):
    """Add a question to a quiz (for teachers)"""
    model = Question
    template_name = 'question_form.html'
    fields = ['text', 'question_type']
    
    def test_func(self):
        quiz = get_object_or_404(Quiz, id=self.kwargs.get('quiz_id'))
        return self.request.user == quiz.teacher or self.request.user.is_superuser
    
    def form_valid(self, form):
        quiz = get_object_or_404(Quiz, id=self.kwargs.get('quiz_id'))
        form.instance.quiz = quiz
        
        # Save the question first
        response = super().form_valid(form)
        
        # Handle options based on question type
        question = self.object
        question_type = question.question_type
        
        if question_type in ['multiple_choice', 'true_false']:
            # For multiple choice, create option placeholders
            if question_type == 'multiple_choice':
                # Create 4 default options
                for i in range(4):
                    is_correct = (i == 0)  # Make the first option correct by default
                    QuestionOption.objects.create(
                        question=question,
                        text=f"Option {i+1}",
                        is_correct=is_correct
                    )
            # For true/false, create True and False options
            elif question_type == 'true_false':
                QuestionOption.objects.create(
                    question=question,
                    text="True",
                    is_correct=True
                )
                QuestionOption.objects.create(
                    question=question,
                    text="False",
                    is_correct=False
                )
        
        # For short answer, create a placeholder correct answer
        elif question_type == 'short_answer':
            QuestionOption.objects.create(
                question=question,
                text="Correct Answer",
                is_correct=True
            )
        
        # Redirect to edit the question to complete setup
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        quiz = get_object_or_404(Quiz, id=self.kwargs.get('quiz_id'))
        context['quiz'] = quiz
        context['title'] = f'Add Question to {quiz.title}'
        context['submit_text'] = 'Create Question'
        
        return context
    
    def get_success_url(self):
        return reverse('assessment:edit_question', kwargs={'question_id': self.object.id})

class QuestionUpdateView(AssessmentBaseView, UserPassesTestMixin, UpdateView):
    """Edit a question with its options (for teachers)"""
    model = Question
    template_name = 'question_form.html'
    context_object_name = 'question'
    fields = ['text', 'question_type']
    pk_url_kwarg = 'question_id'
    
    def test_func(self):
        question = self.get_object()
        return self.request.user == question.quiz.teacher or self.request.user.is_superuser
    
    def form_valid(self, form):
        # Save the question
        response = super().form_valid(form)
        
        # Handle options updates from POST data
        question = self.object
        question_type = question.question_type
        
        if question_type in ['multiple_choice', 'true_false']:
            # Get option texts and correct option from POST
            option_texts = self.request.POST.getlist('options[]')
            correct_option = self.request.POST.get('correct_option')
            
            # Get existing options
            existing_options = list(question.options.all())
            
            # Update or create options
            for i, option_text in enumerate(option_texts):
                is_correct = (str(i) == correct_option)
                
                # If we have an existing option, update it
                if i < len(existing_options):
                    option = existing_options[i]
                    option.text = option_text
                    option.is_correct = is_correct
                    option.save()
                else:
                    # Create new option
                    QuestionOption.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=is_correct
                    )
            
            # Delete any excess options
            if len(existing_options) > len(option_texts):
                for option in existing_options[len(option_texts):]:
                    option.delete()
        
        elif question_type == 'short_answer':
            # Handle short answer correct responses
            correct_answers = self.request.POST.getlist('correct_answers[]')
            
            # Delete existing options
            question.options.all().delete()
            
            # Create new options for each correct answer
            for answer in correct_answers:
                if answer.strip():  # Skip empty answers
                    QuestionOption.objects.create(
                        question=question,
                        text=answer,
                        is_correct=True
                    )
        
        # For essay questions, no options needed
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        question = self.get_object()
        context['quiz'] = question.quiz
        context['options'] = question.options.all()
        context['title'] = f'Edit Question: {question.text[:30]}...'
        context['submit_text'] = 'Update Question'
        
        return context
    
    def get_success_url(self):
        question = self.get_object()
        return reverse('assessment:edit_quiz', kwargs={'quiz_id': question.quiz.id})

class QuestionDeleteView(AssessmentBaseView, UserPassesTestMixin, DeleteView):
    """Delete a question (for teachers)"""
    model = Question
    template_name = 'question_confirm_delete.html'
    context_object_name = 'question'
    pk_url_kwarg = 'question_id'
    
    def test_func(self):
        question = self.get_object()
        return self.request.user == question.quiz.teacher or self.request.user.is_superuser
    
    def get_success_url(self):
        quiz_id = self.object.quiz.id
        return reverse('assessment:edit_quiz', kwargs={'quiz_id': quiz_id})

class TakeQuizView(AssessmentBaseView, UserPassesTestMixin, DetailView):
    """View for students to take a quiz"""
    model = Quiz
    template_name = 'take_quiz.html'
    context_object_name = 'quiz'
    pk_url_kwarg = 'quiz_id'
    
    def test_func(self):
        quiz = self.get_object()
        
        # Only students can take quizzes
        if not self.request.user.is_student:
            return False
            
        # Student must be enrolled in the course
        if quiz.course not in self.request.user.enrolled_courses.all():
            return False
            
        # Check if already taken
        already_taken = Answer.objects.filter(
            question__quiz=quiz,
            student=self.request.user
        ).exists()
        
        # If already taken, redirect to results instead
        if already_taken:
            return False
            
        return True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        quiz = self.get_object()
        context['questions'] = quiz.questions.all().prefetch_related('options')
        
        return context
    
    def post(self, request, *args, **kwargs):
        quiz = self.get_object()
        
        # Check if already taken
        already_taken = Answer.objects.filter(
            question__quiz=quiz,
            student=request.user
        ).exists()
        
        if already_taken:
            messages.error(request, "You've already taken this quiz.")
            return redirect('assessment:quiz_results', quiz_id=quiz.id)
        
        # Process answers
        for question in quiz.questions.all():
            answer_text = request.POST.get(f'question_{question.id}')
            
            # Skip if no answer provided
            if not answer_text:
                continue
            
            # Check if answer is correct
            is_correct = question.validate_answer(answer_text)
            
            # Save answer
            Answer.objects.create(
                question=question,
                student=request.user,
                text=answer_text,
                is_correct=is_correct if is_correct is not None else False
            )
        
        messages.success(request, "Quiz submitted successfully!")
        return redirect('assessment:quiz_results', quiz_id=quiz.id)

class QuizResultsView(AssessmentBaseView, DetailView):
    """View quiz results (for students or teachers)"""
    model = Quiz
    template_name = 'quiz_results.html'
    context_object_name = 'quiz'
    pk_url_kwarg = 'quiz_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz = self.get_object()
        
        # Check permissions
        if self.request.user.is_teacher and quiz.teacher != self.request.user:
            return redirect('assessment:quiz_list')
            
        if self.request.user.is_student and quiz.course not in self.request.user.enrolled_courses.all():
            return redirect('assessment:quiz_list')
        
        # Get results
        if self.request.user.is_student:
            # Student viewing own results
            context['answers'] = Answer.objects.filter(
                question__quiz=quiz,
                student=self.request.user
            ).select_related('question')
            
            context['results'] = quiz.grade_quiz(self.request.user)
        else:
            # Teacher viewing
            student_id = self.request.GET.get('student_id')
            
            if student_id:
                # Viewing specific student
                from django.contrib.auth.models import User
                student = get_object_or_404(User, id=student_id)
                
                context['answers'] = Answer.objects.filter(
                    question__quiz=quiz,
                    student=student
                ).select_related('question')
                
                context['results'] = quiz.grade_quiz(student)
                context['student'] = student
            else:
                # Show overview of all students
                students = quiz.course.students.all()
                student_results = []
                
                for student in students:
                    # Check if student has taken the quiz
                    has_taken = Answer.objects.filter(
                        question__quiz=quiz, 
                        student=student
                    ).exists()
                    
                    if has_taken:
                        grade = quiz.grade_quiz(student)
                        student_results.append({
                            'student': student,
                            'results': grade,
                            'submission_date': Answer.objects.filter(
                                question__quiz=quiz,
                                student=student
                            ).latest('id').id  # Using ID as proxy for date in this demo
                        })
                
                context['student_results'] = student_results
                
                # Change template for overview
                self.template_name = 'quiz_results_overview.html'
        
        return context

class StudentResultsView(AssessmentBaseView, ListView):
    """View for students to see all their quiz results"""
    template_name = 'student_results.html'
    context_object_name = 'results'
    
    def get_queryset(self):
        # Get all quizzes the student has taken
        taken_quizzes = Quiz.objects.filter(
            questions__answers__student=self.request.user
        ).distinct()
        
        # Prepare results
        results = []
        for quiz in taken_quizzes:
            grade = quiz.grade_quiz(self.request.user)
            
            # Get submission date (using latest answer as proxy)
            latest_answer = Answer.objects.filter(
                question__quiz=quiz,
                student=self.request.user
            ).latest('id')
            
            results.append({
                'quiz': quiz,
                'course': quiz.course,
                'score': grade['percentage'],
                'correct': grade['total_score'],
                'total': grade['total_questions'],
                'submission_date': latest_answer.id  # Using ID as proxy for date in this demo
            })
        
        # Sort by submission date, newest first
        results.sort(key=lambda x: x['submission_date'], reverse=True)
        
        return results
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate statistics
        results = self.get_queryset()
        
        if results:
            total_score = sum(result['score'] for result in results)
            avg_score = total_score / len(results)
            context['avg_score'] = round(avg_score)
            
            # Best and worst performance
            results_by_score = sorted(results, key=lambda x: x['score'])
            context['lowest_score'] = results_by_score[0]
            context['highest_score'] = results_by_score[-1]
        
        return context


def get_quiz_questions(request, quiz_id):
    """API to get questions for a quiz or add AI-generated questions"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # Check permissions
    if request.user.is_teacher and quiz.teacher != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    if request.user.is_student and quiz.course not in request.user.enrolled_courses.all():
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # Handle POST request for adding AI-generated questions
    if request.method == 'POST' and request.user.is_teacher:
        try:
            selected_questions_json = request.POST.get('selected_questions')

            if selected_questions_json:
                selected_questions = json.loads(selected_questions_json)
                # Add each question to the quiz
                for q_data in selected_questions:
                    # Create question
                    question = Question.objects.create(
                        quiz=quiz,
                        text=q_data['question'],
                        question_type='multiple_choice',
                        is_ai_generated=True
                    )
                    # Create options
                    for i, option_text in enumerate(q_data['options']):
                        QuestionOption.objects.create(
                            question=question,
                            text=option_text,
                            is_correct=(i == q_data['correct_option'])
                        )
                return JsonResponse({
                    'success': True,
                    'message': f'Added {len(selected_questions)} questions to the quiz'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'No questions selected'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    # Handle GET request for getting quiz questions
    questions = []
    for question in quiz.questions.all().order_by('id'):
        q = {
            'id': question.id,
            'text': question.text,
            'type': question.question_type,
            'is_ai_generated': question.is_ai_generated
        }
        # Include options for multiple choice and true/false
        if question.question_type in ['multiple_choice', 'true_false']:
            q['options'] = list(question.options.values('id', 'text', 'is_correct'))
        questions.append(q)
    return JsonResponse(questions, safe=False)

def update_question_order(request, quiz_id):
    """API to update question order"""
    if not request.user.is_authenticated or not request.user.is_teacher:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)

    if request.method == 'POST':
        try:
            question_order = request.POST.getlist('question_order[]')
            # Update order of questions
            for i, question_id in enumerate(question_order):
                question = Question.objects.get(id=question_id, quiz=quiz)
                question.order = i
                question.save(update_fields=['order'])
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request'}, status=400)


class GenerateQuizQuestionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View for generating quiz questions using AI"""
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            topic = data.get('topic', '')
            num_questions = data.get('num_questions', 5)
            difficulty = data.get('difficulty', 'medium')
            
            if not topic:
                return JsonResponse({'success': False, 'message': 'Topic is required'})
                
            # Limit the number of questions to 10 to prevent abuse
            num_questions = min(num_questions, 10)
            
            # Generate questions using AI service
            result = AIContentService.generate_quiz_questions(topic, num_questions, difficulty)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class AIEnhancedQuizCreateView(AssessmentBaseView, UserPassesTestMixin, CreateView):
    """Create a new quiz with AI-generated questions (for teachers)"""
    model = Quiz
    template_name = 'ai_quiz_form.html'
    fields = ['title', 'course']
    
    def test_func(self):
        return self.request.user.is_teacher or self.request.user.is_superuser
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter courses to only show courses taught by this teacher
        form.fields['course'].queryset = Course.objects.filter(teacher=self.request.user)
        return form
    
    def form_valid(self, form):
        form.instance.teacher = self.request.user
        form.instance.is_ai_generated = True
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('assessment:edit_quiz', kwargs={'quiz_id': self.object.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Set course if provided in URL
        course_id = self.kwargs.get('course_id')
        if course_id:
            course = get_object_or_404(Course, id=course_id, teacher=self.request.user)
            context['selected_course'] = course
            
        context['title'] = 'Create AI-Enhanced Quiz'
        context['submit_text'] = 'Create Quiz'
        
        return context


class TextRewriteView(LoginRequiredMixin, View):
    """View for rewriting text using AI"""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            style = data.get('style', None)
            
            if not text:
                return JsonResponse({'success': False, 'message': 'Text is required'})
                
            # Rewrite text using AI service
            result = AIContentService.rewrite_text(text, style)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})