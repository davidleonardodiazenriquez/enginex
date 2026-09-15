"""Isolated tests, even when .env points to the shared Azure services."""

from .settings import *  # noqa: F403

DEBUG = True
LOCAL_DEMO_AUTO_LOGIN = False
SECRET_KEY = "isolated-test-signing-key"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AZURE_STORAGE_ACCOUNT_NAME = ""
AZURE_STORAGE_ACCOUNT_KEY = ""
AZURE_AI_FOUNDRY_ENDPOINT = ""
AZURE_AI_FOUNDRY_API_KEY = ""
AZURE_AI_FOUNDRY_DEPLOYMENT = ""
