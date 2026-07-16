"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.static import serve
from django.views.i18n import set_language
from urllib.parse import urlsplit

from api.mcp_oauth import views as mcp_oauth_views


apps = [
    ("v1/auth/", "api.authenticate.urls", "auth"),
    ("v1/messaging/", "api.messaging.urls", "messaging"),
    ("v1/tools/", "api.tools.urls", "tools"),
    ("v1/rag/", "api.rag.urls", "rag"),
    ("v1/ai_layers/", "api.ai_layers.urls", "ai_layers"),
    ("v1/finetuning/", "api.finetuning.urls", "finetuning"),
    ("v1/whatsapp/", "api.whatsapp.urls", "whatsapp"),
    ("v1/feedback/", "api.feedback.urls", "feedback"),
    ("v1/preferences/", "api.preferences.urls", "preferences"),
    ("v1/assignments/", "api.assignments.urls", "assignments"),
    ("v1/notify/", "api.notify.urls", "notify"),
    ("v1/payments/", "api.payments.urls", "payments"),
    ("v1/cloudbeds/", "api.cloudbeds.urls", "cloudbeds"),
    ("v1/integrations/", "api.integrations.urls", "integrations"),
    ("v1/document-templates/", "api.document_templates.urls", "document_templates"),
    ("v1/data-governance/", "api.data_governance.urls", "data_governance"),
    ("v1/voices/", "api.voices.urls", "voices"),
    ("v1/mcp_oauth/", "api.mcp_oauth.urls", "mcp_oauth"),
]

urlpatterns_apps = [
    path(url, include(urlconf, namespace=namespace)) for url, urlconf, namespace in apps
]

urlpatterns_django = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path(
        ".well-known/oauth-authorization-server",
        mcp_oauth_views.authorization_server_metadata,
        name="oauth_authorization_server_metadata",
    ),
    path("oauth/authorize", mcp_oauth_views.oauth_authorize, name="oauth_authorize"),
    path("oauth/token", mcp_oauth_views.oauth_token, name="oauth_token"),
    path("oauth/register", mcp_oauth_views.oauth_register, name="oauth_register"),
]

urlpatterns_static = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Serve local media files even when DEBUG is False.
# When MEDIA_URL points to S3 (absolute URL), Django should not serve media.
_media_url_parts = urlsplit(settings.MEDIA_URL)
if settings.MEDIA_URL and not _media_url_parts.netloc:
    _media_prefix = settings.MEDIA_URL.strip("/")
    urlpatterns_media = (
        [path(f"{_media_prefix}/<path:path>", serve, {"document_root": settings.MEDIA_ROOT})]
        if _media_prefix
        else []
    )
else:
    urlpatterns_media = []

urlpatterns = urlpatterns_apps + urlpatterns_django + urlpatterns_static + urlpatterns_media
