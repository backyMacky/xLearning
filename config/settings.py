"""
Django settings for the learning platform project.
"""
import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from .template import TEMPLATE_CONFIG, THEME_LAYOUT_DIR, THEME_VARIABLES

load_dotenv()  # take environment variables from .env.

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", default='')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", 'True').lower() in ['true', 'yes', '1']

# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]

# Current DJANGO_ENVIRONMENT
ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", default="local")

# Application definition

INSTALLED_APPS = [
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third-party apps
    "whitenoise.runserver_nostatic",  # For serving static files in development
    "storages",  # For handling file storage
    
    # Local apps - core functionality
    "apps.account.apps.AccountConfig",  # Renamed from 'auth'
    "apps.content.apps.ContentConfig",  # Renamed from 'academy'
    "apps.meetings.apps.MeetingsConfig",  # Renamed from 'my_calendar'
    "apps.assessment.apps.AssessmentConfig",  # New app
    "apps.repository.apps.RepositoryConfig",  # New app
    "apps.booking.apps.BookingConfig",  # New app
    
    # Local apps - auxiliary
    "apps.dashboards.apps.DashboardsConfig",
    "apps.front_pages.apps.FrontPagesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    
    "web_project.language_middleware.DefaultLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.booking.middleware.DuplicateSessionCleanupMiddleware",

]

# Optional: clean up on startup - set to True to run cleanup when the server starts
CLEAN_DUPLICATE_SESSIONS_ON_STARTUP = True

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.language_code",
                "config.context_processors.my_setting",
                "config.context_processors.get_cookie",
                "config.context_processors.environment",
                # Add the notification context processor
                "apps.account.context_processors.notification_context",
            ],
            "libraries": {
                "theme": "web_project.template_tags.theme",
            },
            "builtins": [
                "django.templatetags.static",
                "web_project.template_tags.theme",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            # PostgreSQL specific options
            "client_encoding": "UTF8",
            "sslmode": os.environ.get("DB_SSL_MODE", "prefer"),
        },
    }
}

# REDIS CONFIGURATION
REDIS_URL = os.environ.get("REDIS_URL")

# CELERY CONFIGURATION
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# FILE STORAGE CONFIGURATION
if ENVIRONMENT == "production":
    # Use S3 for production
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    # S3 settings
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_DEFAULT_ACL = "private"
    AWS_S3_CUSTOM_DOMAIN = None
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
else:
    # Use local file storage for development
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# Enable i18n and set the list of supported languages
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("ar", _("Arabic")),
    ("es", _("Spanish")),
    ("de", _("German")),
]

# Set default language
LANGUAGE_CODE = "en"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "src" / "assets",
]

# Media files (User uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ["true", "yes", "1"]
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")

# Login/logout URLs
LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/overview/"

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Fix the SESSION_COOKIE_AGE setting - remove the extra comment in the string
try:
    SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", 604800))  # 1 week in seconds
except (ValueError, TypeError):
    # Fallback if there's an issue with the environment variable
    SESSION_COOKIE_AGE = 604800  # 1 week in seconds



# CSRF settings
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Google Calendar API
GOOGLE_CALENDAR_CLIENT_ID = os.environ.get("GOOGLE_CALENDAR_CLIENT_ID")
GOOGLE_CALENDAR_CLIENT_SECRET = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET")
GOOGLE_CALENDAR_REDIRECT_URI = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI")

# Default auto field for models
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Template Settings
THEME_LAYOUT_DIR = THEME_LAYOUT_DIR
TEMPLATE_CONFIG = TEMPLATE_CONFIG
THEME_VARIABLES = THEME_VARIABLES