from django.views.generic import TemplateView, FormView, ListView, CreateView
from django.views.generic.edit import FormView
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.conf import settings
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper

from .models import ContactMessage, Subscriber
from .forms import ContactForm, SubscriberForm

# Base class for all front pages to ensure consistent template handling
class BaseFrontPageView(TemplateView):
    """Base class for all front-facing pages before authentication"""
    
    def get_context_data(self, **kwargs):
        # Initialize the template layout from the base class
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        # Set consistent layout properties for all front pages
        context.update({
            "layout": "front",
            "layout_path": TemplateHelper.set_layout("layout_front.html", context),
            "active_url": self.request.path,
            "is_front": True,
        })
        
        # Map context variables to template variables
        TemplateHelper.map_context(context)
        
        return context

class LandingPageView(BaseFrontPageView):
    """Main landing page for the site"""
    template_name = "landing_page.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Modern Platform for Language Teachers",
            "page_description": "Comprehensive tools for teaching, assessment, and student management.",
            "subscriber_form": SubscriberForm()
        })
        return context
    
    def post(self, request, *args, **kwargs):
        form = SubscriberForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you for subscribing to our newsletter!'
                })
            messages.success(request, 'Thank you for subscribing to our newsletter!')
            return redirect('front_pages:home')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'This email is already subscribed or invalid.'
                })
            messages.error(request, 'This email is already subscribed or invalid.')
            return self.get(request, *args, **kwargs)

class ContentManagementView(BaseFrontPageView):
    """Feature page for content management capabilities"""
    template_name = "front_pages/features/content_management.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Content Management System",
            "page_description": "Create, organize, and share course materials with ease.",
            "active_feature": "content-management"
        })
        return context
    
class LiveSessionsView(BaseFrontPageView):
    """Feature page for live session capabilities"""
    template_name = "front_pages/features/live_sessions.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Live Session Management",
            "page_description": "Schedule and manage online teaching sessions efficiently.",
            "active_feature": "live-sessions"
        })
        return context
    
class AssessmentToolsView(BaseFrontPageView):
    """Feature page for assessment tools"""
    template_name = "front_pages/features/assessment_tools.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Assessment Tools",
            "page_description": "Create and manage custom assessments to track student progress.",
            "active_feature": "assessment-tools"
        })
        return context
    
class StudentManagementView(BaseFrontPageView):
    """Feature page for student management capabilities"""
    template_name = "front_pages/features/student_management.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Student Repositories",
            "page_description": "Organize and track student resources and engagement.",
            "active_feature": "student-management"
        })
        return context
    
class BookingPaymentView(BaseFrontPageView):
    """Feature page for booking and payment capabilities"""
    template_name = "front_pages/features/booking_payment.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Booking & Payment",
            "page_description": "Manage your availability and track teaching hours and payments.",
            "active_feature": "booking-payment"
        })
        return context
    
class PricingView(BaseFrontPageView):
    """Pricing plans page"""
    template_name = "pricing_page.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Pricing Plans",
            "page_description": "Find the perfect plan for your teaching needs."
        })
        return context
    
class AboutView(BaseFrontPageView):
    """About us page"""
    template_name = "about.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "About Us",
            "page_description": "Learn more about the team behind our platform."
        })
        return context
    
class FAQView(BaseFrontPageView):
    """Frequently asked questions page"""
    template_name = "faq.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Frequently Asked Questions",
            "page_description": "Find answers to common questions about our platform."
        })
        return context

class ContactView(BaseFrontPageView, FormView):
    """Contact us page with form handling"""
    template_name = "contact.html"
    form_class = ContactForm
    success_url = reverse_lazy('front_pages:contact_success')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Contact Us",
            "page_description": "Get in touch with our support team."
        })
        return context
    
    def form_valid(self, form):
        # Save the contact message to the database
        contact = form.save()
        
        # Send email notification
        try:
            # Email to admin
            admin_html_message = render_to_string('emails/contact_notification.html', {
                'contact': contact,
                'domain': self.request.get_host(),
            })
            admin_plain_message = strip_tags(admin_html_message)
            
            send_mail(
                subject=f'New Contact Message: {contact.subject}',
                message=admin_plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.EMAIL_HOST_USER],
                html_message=admin_html_message,
                fail_silently=False,
            )
            
            # Confirmation email to the user
            user_html_message = render_to_string('emails/contact_confirmation.html', {
                'contact': contact,
                'domain': self.request.get_host(),
            })
            user_plain_message = strip_tags(user_html_message)
            
            send_mail(
                subject='Thank you for contacting xLearning',
                message=user_plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact.email],
                html_message=user_html_message,
                fail_silently=False,
            )
            
        except Exception as e:
            # Log the error but don't prevent the form submission from completing
            print(f"Email sending failed: {str(e)}")
        
        messages.success(self.request, "Your message has been sent successfully. We'll get back to you soon!")
        return super().form_valid(form)

class ContactSuccessView(BaseFrontPageView):
    """Success page after contact form submission"""
    template_name = "contact_success.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Message Sent",
            "page_description": "Your message has been received."
        })
        return context

class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only admin users can access view"""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser or 
            getattr(self.request.user, 'is_admin', False)
        )

class ContactMessageListView(LoginRequiredMixin, AdminRequiredMixin, BaseFrontPageView, ListView):
    """Admin view to list contact messages"""
    model = ContactMessage
    template_name = "admin/contact_message_list.html"
    context_object_name = "messages"
    paginate_by = 10
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Contact Messages",
            "page_description": "View and manage contact form submissions.",
            "layout": "vertical",  # Override to use admin layout
            "layout_path": TemplateHelper.set_layout("layout.html", context),  # Use admin layout template
        })
        return context
    
    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter in dict(ContactMessage.ContactStatus.choices):
            queryset = queryset.filter(status=status_filter)
        return queryset

class SubscriberListView(LoginRequiredMixin, AdminRequiredMixin, BaseFrontPageView, ListView):
    """Admin view to list newsletter subscribers"""
    model = Subscriber
    template_name = "admin/subscriber_list.html"
    context_object_name = "subscribers"
    paginate_by = 20
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Newsletter Subscribers",
            "page_description": "View and manage newsletter subscribers.",
            "layout": "vertical",  # Override to use admin layout
            "layout_path": TemplateHelper.set_layout("layout.html", context),  # Use admin layout template
        })
        return context
    
    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset

class HelpCenterHomeView(BaseFrontPageView):
    """Help center landing page"""
    template_name = "help_center.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Help Center",
            "page_description": "Find help and resources for using our platform."
        })
        return context

class HelpCenterArticleView(BaseFrontPageView):
    """Individual help center article page"""
    template_name = "help_center/article.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # In a real implementation, you would fetch the article details here
        # For now we'll use placeholder content
        article = {
            'title': 'Getting Started with Our Platform',
            'category': 'Beginners Guide',
            'last_updated': '2 weeks ago',
            'content': 'This would be the full article content...'
        }
        
        context.update({
            "page_title": article['title'],
            "page_description": f"Help article in {article['category']}",
            "article": article
        })
        return context

class PrivacyPolicyView(BaseFrontPageView):
    """Privacy policy page"""
    template_name = "privacy_policy.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Privacy Policy",
            "page_description": "Our privacy policy and data handling practices."
        })
        return context

class TermsOfServiceView(BaseFrontPageView):
    """Terms of service page"""
    template_name = "terms_of_service.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Terms of Service",
            "page_description": "Terms and conditions for using our platform."
        })
        return context

class BlogHomeView(BaseFrontPageView):
    """Blog homepage"""
    template_name = "blog.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Mock blog posts - in a real implementation these would come from a database
        blog_posts = [
            {
                'title': 'Effective Strategies for Online Language Teaching',
                'excerpt': 'Learn how to engage students in virtual classrooms...',
                'date': '2023-04-10',
                'author': 'Maria Rodriguez',
                'slug': 'effective-strategies-online-teaching'
            },
            {
                'title': 'Using Technology to Enhance Language Learning',
                'excerpt': 'Discover new tools and techniques for modern language instruction...',
                'date': '2023-03-25',
                'author': 'John Chen',
                'slug': 'technology-enhance-language-learning'
            },
            {
                'title': 'Best Practices for Student Assessment',
                'excerpt': 'How to create fair and effective assessments for language learners...',
                'date': '2023-03-12',
                'author': 'Sarah Johnson',
                'slug': 'best-practices-student-assessment'
            }
        ]
        
        context.update({
            "page_title": "Language Teaching Blog",
            "page_description": "Articles, tips and resources for language teachers.",
            "blog_posts": blog_posts
        })
        return context

class BlogPostView(BaseFrontPageView):
    """Individual blog post page"""
    template_name = "blog_post.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # In a real implementation, you would fetch the post by slug from kwargs
        # For now we'll use placeholder content
        post = {
            'title': 'Effective Strategies for Online Language Teaching',
            'content': 'This would be the full blog post content...',
            'date': '2023-04-10',
            'author': 'Maria Rodriguez',
            'slug': 'effective-strategies-online-teaching'
        }
        
        context.update({
            "page_title": post['title'],
            "page_description": f"Blog post by {post['author']}",
            "post": post
        })
        return context



class WebinarView(BaseFrontPageView):
    """Webinar page view"""
    template_name = "webinar.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Language Teaching Webinars",
            "page_description": "Professional development webinars for language educators.",
            "active_menu": "resources"
        })
        return context

class CommunityView(BaseFrontPageView):
    """Community page view"""
    template_name = "community.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Language Teacher Community",
            "page_description": "Connect with educators worldwide and share teaching resources.",
            "active_menu": "community"
        })
        return context

class CookiePolicyView(BaseFrontPageView):
    """Cookie policy page view"""
    template_name = "cookie_policy.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Cookie Policy",
            "page_description": "Learn how we use cookies to enhance your experience.",
            "active_menu": "legal"
        })
        return context
