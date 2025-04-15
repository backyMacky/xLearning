from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('courses/', views.course_list, name='course_list'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('courses/create/', views.create_course, name='create_course'),
    path('courses/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    path('courses/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    path('courses/<int:course_id>/unenroll/', views.unenroll_course, name='unenroll_course'),
    path('lessons/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('courses/<int:course_id>/lessons/create/', views.create_lesson, name='create_lesson'),
    path('lessons/<int:lesson_id>/edit/', views.edit_lesson, name='edit_lesson'),
    path('resources/', views.resource_list, name='resource_list'),
    path('resources/create/', views.create_resource, name='create_resource'),
]