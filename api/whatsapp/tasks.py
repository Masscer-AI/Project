import logging
from celery import shared_task
from .actions import send_message, handle_webhook

logger = logging.getLogger(__name__)


@shared_task
def async_send_message(business_phone_number_id, to):
    return send_message(
        business_phone_number_id=business_phone_number_id,
        to=to,
    )


@shared_task
def async_handle_webhook(webhook_data):
    return handle_webhook(webhook_data=webhook_data)
