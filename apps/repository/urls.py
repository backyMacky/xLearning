from django.urls import path
from . import views

app_name = 'repository'

urlpatterns = [
    # Dashboard
    path('', views.RepositoryDashboardView.as_view(), name='dashboard'),
    
    # Student files
    path('files/', views.StudentFilesListView.as_view(), name='file_list'),
    path('files/upload/', views.StudentFileUploadView.as_view(), name='upload_file'),
    path('files/<int:file_id>/', views.StudentFileDetailView.as_view(), name='file_detail'),
    path('files/<int:file_id>/edit/', views.StudentFileEditView.as_view(), name='edit_file'),
    path('files/<int:file_id>/download/', views.FileDownloadView.as_view(), name='download_file'),
    
    # Teacher resources
    path('resources/', views.TeacherResourcesListView.as_view(), name='resource_list'),
    path('resources/upload/', views.TeacherResourceUploadView.as_view(), name='upload_resource'),
    path('resources/<int:resource_id>/', views.ResourceDetailView.as_view(), name='resource_detail'),
    path('resources/<int:resource_id>/edit/', views.TeacherResourceEditView.as_view(), name='edit_resource'),
    path('resources/<int:resource_id>/download/', views.ResourceDownloadView.as_view(), name='download_resource'),
    
    # Collections
    path('collections/create/', views.CollectionCreateView.as_view(), name='create_collection'),
    path('collections/<int:collection_id>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    path('collections/add-items/', views.AddToCollectionView.as_view(), name='add_to_collection'),
    path('collections/remove-item/', views.RemoveFromCollectionView.as_view(), name='remove_from_collection'),
]