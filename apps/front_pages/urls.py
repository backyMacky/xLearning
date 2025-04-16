from django.urls import path
from .views import (
    LandingPageView, 
    FeaturesPageView,
    TeamPageView,
    FAQPageView,
    ContactPageView,
    PricingPageView, 
    PaymentPageView, 
    CheckoutPageView,
    HelpCenterLandingView,
    HelpCenterArticleView
)

app_name = 'front_pages'  # Adding namespace

urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
    path("features/", FeaturesPageView.as_view(), name="features"),
    path("team/", TeamPageView.as_view(), name="team"),
    path("faq/", FAQPageView.as_view(), name="faq"),
    path("contact/", ContactPageView.as_view(), name="contact"),
    path("pricing/", PricingPageView.as_view(), name="pricing-page"),
    path("payment/", PaymentPageView.as_view(), name="payment-page"),
    path("checkout/", CheckoutPageView.as_view(), name="checkout-page"),
    path("help-center/", HelpCenterLandingView.as_view(), name="help-center-landing"),
    path("help-center/article/", HelpCenterArticleView.as_view(), name="help-center-article"),
]