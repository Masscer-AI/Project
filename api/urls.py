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
]

urlpatterns_apps = [
    path(url, include(urlconf, namespace=namespace)) for url, urlconf, namespace in apps
]

urlpatterns_django = [
    path("admin/", admin.site.urls),
]

urlpatterns_static = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# add the media URL
urlpatterns_media = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns_apps + urlpatterns_django + urlpatterns_static + urlpatterns_media
