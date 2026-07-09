from pathlib import Path

import environ

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------

env = environ.Env()

environ.Env.read_env(BASE_DIR / ".env")

# ------------------------------------------------------------------
# Core
# ------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  

    "apps.firms.apps.FirmsConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.documents.apps.DocumentsConfig",
    "apps.search.apps.SearchConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL")
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


#  TODO: the custom auth backend (ModelBackend subclass) must query User.objects.get(firm=firm, username=username) — until that backend exists, Django's default login views will misbehave for duplicate usernames across firms
SILENCED_SYSTEM_CHECKS = ["auth.E003", "auth.W004"]

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.FirmBackend",
    "django.contrib.auth.backends.ModelBackend",  # fallback, e.g. for Django admin login by superuser
]