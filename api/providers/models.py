from django.db import models
from django.contrib.auth.models import User


class Provider(models.Model):
    name = models.CharField(max_length=100)
    website_url = models.URLField(max_length=200, blank=True, null=True)
    docs_url = models.URLField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProviderCredentials(models.Model):
    api_key = models.CharField(max_length=255)
    # secret_key = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AIProvider(Provider):
    def __str__(self):
        return self.name


class AIProviderCredentials(ProviderCredentials):
    provider = models.ForeignKey(
        AIProvider, on_delete=models.CASCADE, related_name="ai_credentials"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ai_provider_credentials"
    )

    def __str__(self):
        return f"Credentials for {self.provider.name} by {self.user.username}"


class SearchEngineProvider(Provider):
    def __str__(self):
        return self.name


class SearchEngineProviderCredentials(ProviderCredentials):
    provider = models.ForeignKey(
        SearchEngineProvider,
        on_delete=models.CASCADE,
        related_name="search_credentials",
    )
    # user = models.ForeignKey(
    #     User, on_delete=models.CASCADE, related_name="provider_credentials"
    # )


class MediaProvider(Provider):
    def __str__(self):
        return self.name


class MediaProviderCredentials(ProviderCredentials):
    provider = models.ForeignKey(
        MediaProvider, on_delete=models.CASCADE, related_name="media_credentials"
    )
