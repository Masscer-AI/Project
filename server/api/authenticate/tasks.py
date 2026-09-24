import logging
import os

import requests
from celery import shared_task
from django.core.files.base import ContentFile

from api.utils.openai_functions import generate_image

from .models import Organization, OrganizationInvite

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


@shared_task
def send_invite_welcome_whatsapp(invite_id: str):
    from api.authenticate.invite_welcome import (
        welcome_lines_for_org,
        welcome_template_id,
    )
    from api.whatsapp.conversations import get_or_create_ws_contact
    from api.whatsapp.template_send import send_ws_template_to_member

    invite = (
        OrganizationInvite.objects.select_related(
            "organization", "accepted_user"
        )
        .filter(pk=invite_id)
        .first()
    )
    if not invite or not invite.send_welcome_message:
        return
    user = invite.accepted_user
    if not user:
        return

    try:
        lines = welcome_lines_for_org(invite.organization, invite.welcome_line_ids)
    except ValueError:
        logger.warning(
            "send_invite_welcome_whatsapp: lines missing invite=%s", invite_id
        )
        return

    phones = invite.welcome_phones or []
    if not lines or not phones:
        return

    template_id = welcome_template_id(invite.welcome_language)
    org_name = invite.organization.name
    person_name = (invite.name or user.username or "").strip() or user.username
    help_text = (invite.welcome_help_text or "").strip()

    for ws_number in lines:
        agent_name = (ws_number.agent.name if ws_number.agent_id else "") or ""
        for phone in phones:
            try:
                contact = get_or_create_ws_contact(ws_number, phone)
                if contact.user_id and contact.user_id != user.id:
                    logger.warning(
                        "send_invite_welcome_whatsapp: contact already linked "
                        "invite=%s line=%s phone=%s",
                        invite_id,
                        ws_number.id,
                        phone,
                    )
                    continue
                if contact.user_id is None:
                    contact.user = user
                    contact.save(update_fields=["user", "updated_at"])
                send_ws_template_to_member(
                    actor_user_id=user.id,
                    organization_id=invite.organization_id,
                    agent_id=ws_number.agent_id,
                    sender_id=ws_number.id,
                    ws_contact_id=contact.id,
                    template_id=template_id,
                    template_variables={
                        "body": [person_name, org_name, agent_name, help_text]
                    },
                    source_conversation_id=None,
                )
            except Exception:
                logger.exception(
                    "send_invite_welcome_whatsapp failed invite=%s line=%s phone=%s",
                    invite_id,
                    ws_number.id,
                    phone,
                )
