from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Quiz, Question, QuestionOption, Answer
from apps.content.models import Course

@login_required
def quiz_list(request):
    """List all quizzes available to the user"""
    if request.user.is_teacher:
        # Teachers see quizzes they created
        quizzes = Quiz.objects.filter(teacher=request.user)
    else:
        # Students see quizzes from courses they're enrolled in
        enrolled_courses = request.user.enrolled_courses.all()
        quizzes = Quiz.objects.filter(course__in=enrolled_courses)
    
    return render(request, 'assessment/quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_detail(request, quiz_id):
    """View a specific quiz"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Check if user has access to this quiz
    if request.user.is_teacher and quiz.teacher != request.user:
        return redirect('assessment:quiz_list')
    
    if request.user.is_student and quiz.course not in request.user.enrolled_courses.all():
        return redirect('assessment:quiz_list')
    
    # If student has already taken the quiz, show results
    if request.user.is_student:
        taken = Answer.objects.filter(
            question__quiz=quiz,
            student=request.user
        ).exists()
    else:
        taken = False
    
    return render(request, 'assessment/quiz_detail.html', {
        'quiz': quiz,
        'questions': quiz.questions.all(),
        'taken': taken
    })

@login_required
def create_quiz(request, course_id=None):
    """Create a new quiz"""
    if not request.user.is_teacher:
        return redirect('assessment:quiz_list')
    
    if course_id:
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
    else:
        course = None
    
    if request.method == 'POST':
        title = request.POST.get('title')
        course_id = request.POST.get('course_id')
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
        
        quiz = Quiz.objects.create(
            title=title,
            course=course,
            teacher=request.user
        )
        
        return redirect('assessment:edit_quiz', quiz_id=quiz.id)
    
    # GET request
    courses = Course.objects.filter(teacher=request.user)
    return render(request, 'assessment/create_quiz.html', {
        'courses': courses,
        'selected_course': course
    })

@login_required
def edit_quiz(request, quiz_id):
    """Edit an existing quiz"""
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    
    if request.method == 'POST':
        # Handle form submission to update quiz
        quiz.title = request.POST.get('title', quiz.title)
        quiz.save()
        
        return redirect('assessment:quiz_detail', quiz_id=quiz.id)
    
    # GET request
    return render(request, 'assessment/edit_quiz.html', {'quiz': quiz})

@login_required
def add_question(request, quiz_id):
    """Add a question to a quiz"""
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    
    if request.method == 'POST':
        text = request.POST.get('text')
        question_type = request.POST.get('question_type')
        
        question = Question.objects.create(
            quiz=quiz,
            text=text,
            question_type=question_type
        )
        
        # Handle options based on question type
        if question_type in ['multiple_choice', 'true_false']:
            options = request.POST.getlist('options[]')
            correct_option = request.POST.get('correct_option')
            
            for i, option_text in enumerate(options):
                QuestionOption.objects.create(
                    question=question,
                    text=option_text,
                    is_correct=(str(i) == correct_option)
                )
        elif question_type == 'short_answer':
            correct_answers = request.POST.getlist('correct_answers[]')
            for answer in correct_answers:
                QuestionOption.objects.create(
                    question=question,
                    text=answer,
                    is_correct=True
                )
        
        return redirect('assessment:edit_quiz', quiz_id=quiz.id)
    
    # GET request
    return render(request, 'assessment/add_question.html', {'quiz': quiz})

@login_required
def take_quiz(request, quiz_id):
    """Take a quiz (for students)"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Check if student is enrolled in the course
    if quiz.course not in request.user.enrolled_courses.all():
        return redirect('assessment:quiz_list')
    
    # Check if already taken
    taken = Answer.objects.filter(
        question__quiz=quiz,
        student=request.user
    ).exists()
    
    if taken:
        return redirect('assessment:quiz_results', quiz_id=quiz.id)
    
    if request.method == 'POST':
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
        
        return redirect('assessment:quiz_results', quiz_id=quiz.id)
    
    # GET request
    return render(request, 'assessment/take_quiz.html', {
        'quiz': quiz,
        'questions': quiz.questions.all()
    })

@login_required
def quiz_results(request, quiz_id):
    """View quiz results"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Teachers can see any quiz results
    if request.user.is_teacher and quiz.teacher != request.user:
        return redirect('assessment:quiz_list')
    
    # Students can only see their own results
    if request.user.is_student and quiz.course not in request.user.enrolled_courses.all():
        return redirect('assessment:quiz_list')
    
    # Get results
    if request.user.is_student:
        # Student viewing own results
        answers = Answer.objects.filter(
            question__quiz=quiz,
            student=request.user
        )
        results = quiz.grade_quiz(request.user)
    else:
        # Teacher viewing all results
        student_id = request.GET.get('student_id')
        if student_id:
            # Viewing specific student
            student = get_object_or_404(User, id=student_id)
            answers = Answer.objects.filter(
                question__quiz=quiz,
                student=student
            )
            results = quiz.grade_quiz(student)
        else:
            # Show overview of all students
            students = quiz.course.students.all()
            student_results = []
            for student in students:
                grade = quiz.grade_quiz(student)
                student_results.append({
                    'student': student,
                    'results': grade
                })
            return render(request, 'assessment/quiz_results_overview.html', {
                'quiz': quiz,
                'student_results': student_results
            })
    
    return render(request, 'assessment/quiz_results.html', {
        'quiz': quiz,
        'answers': answers,
        'results': results
    })