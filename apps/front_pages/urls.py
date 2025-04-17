from django.urls import path
from .views import (
    LandingPageView,
    ContentManagementView,
    LiveSessionsView,
    AssessmentToolsView,
    StudentManagementView,
    BookingPaymentView,
    PricingView,
    AboutView,
    FAQView,
    ContactView
)

app_name = 'front_pages'  # Adding namespace

urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
    path("features/content-management/", ContentManagementView.as_view(), name="content-management"),
    path("features/live-sessions/", LiveSessionsView.as_view(), name="live-sessions"),
    path("features/assessment-tools/", AssessmentToolsView.as_view(), name="assessment-tools"),
    path("features/student-management/", StudentManagementView.as_view(), name="student-management"),
    path("features/booking-payment/", BookingPaymentView.as_view(), name="booking-payment"),
    path("pricing/", PricingView.as_view(), name="pricing"),
    path("about/", AboutView.as_view(), name="about"),
    path("faq/", FAQView.as_view(), name="faq"),
    path("contact/", ContactView.as_view(), name="contact"),
]