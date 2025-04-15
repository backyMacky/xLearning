"""
URL configuration for web_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from web_project.views import SystemView

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Front pages (public pages)
    path("", include("apps.front_pages.urls")),
    
    # App URLs (authenticated access)
    path("account/", include(("apps.account.urls", "account"), namespace="account")),
    path("content/", include(("apps.content.urls", "content"), namespace="content")),
    path("meetings/", include(("apps.meetings.urls", "meetings"), namespace="meetings")),
    path("assessment/", include(("apps.assessment.urls", "assessment"), namespace="assessment")),
    path("repository/", include(("apps.repository.urls", "repository"), namespace="repository")),
    path("booking/", include(("apps.booking.urls", "booking"), namespace="booking")),
    path("dashboard/", include(("apps.dashboards.urls", "dashboards"), namespace="dashboards")),
]

# Add media files serving in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers
handler404 = SystemView.as_view(template_name="pages_misc_error.html", status=404)
handler403 = SystemView.as_view(template_name="pages_misc_not_authorized.html", status=403)
handler400 = SystemView.as_view(template_name="pages_misc_error.html", status=400)
handler500 = SystemView.as_view(template_name="pages_misc_error.html", status=500)