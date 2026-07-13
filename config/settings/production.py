from .base import *

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = True

SECURE_HSTS_SECONDS = 31536000

SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SECURE_HSTS_PRELOAD = True


# AWS_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = env("R2_BUCKET_NAME")
# AWS_S3_ENDPOINT_URL = env("R2_ENDPOINT_URL")
# AWS_S3_REGION_NAME = "auto"  # R2 doesn't use AWS regions, "auto" is R2's convention
# AWS_DEFAULT_ACL = None  # R2 buckets are private by default; don't fight that