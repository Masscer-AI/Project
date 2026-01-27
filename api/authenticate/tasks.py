import logging
import os

import requests
from celery import shared_task
from django.core.files.base import ContentFile

from api.utils.openai_functions import generate_image

from .models import CredentialsManager, Organization

logger = logging.getLogger(__name__)


@shared_task
def generate_organization_logo(organization_id: str):
    """
    Generate an organization logo with DALL-E-3 and save it asynchronously.
    Called when creating an organization without a logo and without logo management (feature flag).
    """
    try:
        organization = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.warning(f"generate_organization_logo: Organization {organization_id} not found")
        return

    try:
        credentials = CredentialsManager.objects.get(organization=organization)
        api_key = credentials.openai_api_key
    except CredentialsManager.DoesNotExist:
        api_key = None

    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        logger.warning(
            f"generate_organization_logo: OpenAI API key not configured for org {organization_id}"
        )
        return

    prompt = f"A modern, professional logo for {organization.name}. "
    if organization.description:
        prompt += f"The organization is about: {organization.description}. "
    prompt += "Simple, clean design with a transparent or solid background. Suitable for business use."

    try:
        image_url = generate_image(
            prompt=prompt,
            model="dall-e-3",
            size="1024x1024",
            quality="standard",
            api_key=api_key,
        )
    except Exception as e:
        logger.error(
            f"generate_organization_logo: DALL-E error for org {organization_id}: {e}",
            exc_info=True,
        )
        return

    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(
            f"generate_organization_logo: Failed to fetch image for org {organization_id}: {e}",
            exc_info=True,
        )
        return

    try:
        ext = "png"
        filename = f"{organization.id}.{ext}"
        organization.logo.save(filename, ContentFile(response.content), save=True)
        logger.info(f"generate_organization_logo: Logo saved for org {organization_id}")
    except Exception as e:
        logger.error(
            f"generate_organization_logo: Failed to save logo for org {organization_id}: {e}",
            exc_info=True,
        )
