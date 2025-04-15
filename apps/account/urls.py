from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/<str:username>/', views.profile_view, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('api/profile/', views.get_profile_api, name='profile_api'),
]