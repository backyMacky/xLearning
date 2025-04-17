from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    # Quiz lists
    path('quizzes/', views.QuizListView.as_view(), name='quiz_list'),
    
    # Quiz detail and operations
    path('quizzes/<int:quiz_id>/', views.QuizDetailView.as_view(), name='quiz_detail'),
    path('quizzes/create/', views.QuizCreateView.as_view(), name='create_quiz'),
    path('quizzes/create/<int:course_id>/', views.QuizCreateView.as_view(), name='create_course_quiz'),
    path('quizzes/<int:quiz_id>/edit/', views.QuizUpdateView.as_view(), name='edit_quiz'),
    path('quizzes/<int:quiz_id>/delete/', views.QuizDeleteView.as_view(), name='delete_quiz'),
    
    # Question operations
    path('quizzes/<int:quiz_id>/questions/add/', views.QuestionCreateView.as_view(), name='add_question'),
    path('questions/<int:question_id>/edit/', views.QuestionUpdateView.as_view(), name='edit_question'),
    path('questions/<int:question_id>/delete/', views.QuestionDeleteView.as_view(), name='delete_question'),
    
    # Quiz taking and results
    path('quizzes/<int:quiz_id>/take/', views.TakeQuizView.as_view(), name='take_quiz'),
    path('quizzes/<int:quiz_id>/results/', views.QuizResultsView.as_view(), name='quiz_results'),
    
    # Student results view
    path('results/', views.StudentResultsView.as_view(), name='student_results'),
    
    # API endpoints
    path('api/quizzes/<int:quiz_id>/questions/', views.get_quiz_questions, name='api_quiz_questions'),
    path('api/quizzes/<int:quiz_id>/order/', views.update_question_order, name='api_update_question_order'),
]