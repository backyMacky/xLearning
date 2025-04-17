from django.views import View
from django.views.generic import TemplateView
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

# Base class for all front pages to avoid repetition
class BaseFrontPageView(TemplateView):
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        context.update({
            "layout": "front",
            "layout_path": TemplateHelper.set_layout("layout_front.html", context),
            "active_url": self.request.path,
        })
        TemplateHelper.map_context(context)
        return context

class LandingPageView(BaseFrontPageView):
    template_name = "landing_page.html"
    
class ContentManagementView(BaseFrontPageView):
    template_name = "features/content_management.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Content Management System",
            "page_description": "Create, organize, and share course materials with ease."
        })
        return context
    
class LiveSessionsView(BaseFrontPageView):
    template_name = "features/live_sessions.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Live Session Management",
            "page_description": "Schedule and manage online teaching sessions efficiently."
        })
        return context
    
class AssessmentToolsView(BaseFrontPageView):
    template_name = "features/assessment_tools.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Assessment Tools",
            "page_description": "Create and manage custom assessments to track student progress."
        })
        return context
    
class StudentManagementView(BaseFrontPageView):
    template_name = "features/student_management.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Student Repositories",
            "page_description": "Organize and track student resources and engagement."
        })
        return context
    
class BookingPaymentView(BaseFrontPageView):
    template_name = "features/booking_payment.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Booking & Payment",
            "page_description": "Manage your availability and track teaching hours and payments."
        })
        return context
    
class PricingView(BaseFrontPageView):
    template_name = "pricing.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Pricing Plans",
            "page_description": "Find the perfect plan for your teaching needs."
        })
        return context
    
class AboutView(TemplateView):
    template_name = "about.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "About Us",
            "page_description": "Learn more about the team behind EduTeach."
        })
        return context
    
class FAQView(TemplateView):
    template_name = "faq.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Frequently Asked Questions",
            "page_description": "Find answers to common questions about EduTeach."
        })
        return context
    
class ContactView(BaseFrontPageView):
    template_name = "contact.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Contact Us",
            "page_description": "Get in touch with our support team."
        })
        return context