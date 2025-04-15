from django.urls import path
from . import views

app_name = 'repository'

urlpatterns = [
    path('', views.file_dashboard, name='dashboard'),
    path('files/upload/', views.upload_student_file, name='upload_file'),
    path('resources/upload/', views.upload_teacher_resource, name='upload_resource'),
    path('files/<int:file_id>/download/', views.download_file, name='download_file'),
    path('resources/<int:resource_id>/download/', views.download_resource, name='download_resource'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('collections/<int:collection_id>/', views.collection_detail, name='collection_detail'),
    path('collections/add-items/', views.add_to_collection, name='add_to_collection'),
]