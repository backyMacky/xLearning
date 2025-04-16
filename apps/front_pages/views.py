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
    template_name = "landing_page.html"  # This one works because it already exists

# Temporary redirects for pages without templates
from django.views.generic import RedirectView

class FeaturesPageView(RedirectView):
    url = 'front_pages/features'  # Redirect to homepage for now
    
class TeamPageView(RedirectView):
    url = '/'  # Redirect to homepage for now
    
class FAQPageView(RedirectView):
    url = '/'  # Redirect to homepage for now
    
class ContactPageView(RedirectView):
    url = '/'  # Redirect to homepage for now

# Regular views for existing templates
class PricingPageView(BaseFrontPageView):
    template_name = "pricing_page.html"

class PaymentPageView(BaseFrontPageView):
    template_name = "payment_page.html"

class CheckoutPageView(BaseFrontPageView):
    template_name = "checkout_page.html"

class HelpCenterLandingView(BaseFrontPageView):
    template_name = "help_center_landing.html"

class HelpCenterArticleView(BaseFrontPageView):
    template_name = "help_center_article.html"