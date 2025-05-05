from django.urls import path
from .views import (
    # Landing page
    LandingPageView,
    
    # Features
    ContentManagementView,
    LiveSessionsView,
    AssessmentToolsView,
    StudentManagementView,
    BookingPaymentView,
    
    # Contact
    ContactView,
    ContactSuccessView,
    ContactMessageListView,
    SubscriberListView,
    
    # Static pages
    PricingView,
    AboutView,
    FAQView,
    
    # Help center
    HelpCenterHomeView,
    HelpCenterArticleView,
    
    # Legal
    PrivacyPolicyView,
    TermsOfServiceView,
    
    # Blog
    BlogHomeView,
    BlogPostView
)

app_name = 'front_pages'  # Adding namespace

urlpatterns = [
    # Main pages
    path("", LandingPageView.as_view(), name="home"),
    path("pricing/", PricingView.as_view(), name="pricing"),
    path("about/", AboutView.as_view(), name="about"),
    path("faq/", FAQView.as_view(), name="faq"),
    
    # Contact pages
    path("contact/", ContactView.as_view(), name="contact"),
    path("contact/success/", ContactSuccessView.as_view(), name="contact_success"),
    path("admin/contact-messages/", ContactMessageListView.as_view(), name="contact_messages"),
    path("admin/subscribers/", SubscriberListView.as_view(), name="subscribers"),
    
    # Feature pages
    path("features/content-management/", ContentManagementView.as_view(), name="content-management"),
    path("features/live-sessions/", LiveSessionsView.as_view(), name="live-sessions"),
    path("features/assessment-tools/", AssessmentToolsView.as_view(), name="assessment-tools"),
    path("features/student-management/", StudentManagementView.as_view(), name="student-management"),
    path("features/booking-payment/", BookingPaymentView.as_view(), name="booking-payment"),

    # Webinar
    path("webinars/", WebinarView.as_view(), name="webinars"),

    # Community
    path("community/", CommunityView.as_view(), name="community"),

    # Cookie Policy
    path("cookie-policy/", CookiePolicyView.as_view(), name="cookie-policy"),

    # Help center
    path("help/", HelpCenterHomeView.as_view(), name="help-center"),
    path("help/article/<slug:slug>/", HelpCenterArticleView.as_view(), name="help-center-article"),
    
    # Legal pages
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("terms-of-service/", TermsOfServiceView.as_view(), name="terms-of-service"),
    
    # Blog
    path("blog/", BlogHomeView.as_view(), name="blog"),
    path("blog/post/<slug:slug>/", BlogPostView.as_view(), name="blog-post"),
]