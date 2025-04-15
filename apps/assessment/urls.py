from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/create/<int:course_id>/', views.create_quiz, name='create_course_quiz'),
    path('quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quizzes/<int:quiz_id>/questions/add/', views.add_question, name='add_question'),
    path('quizzes/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),
    path('quizzes/<int:quiz_id>/results/', views.quiz_results, name='quiz_results'),
]