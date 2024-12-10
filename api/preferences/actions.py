from api.messaging.models import Conversation
from api.utils.color_printer import printer
from .models import UserTags

def clean_unused_tags(user_id: int) -> None:
    user_tags = UserTags.objects.filter(user_id=user_id).first()
    if not user_tags or not user_tags.tags:
        return

    all_conversation_tags = set(
        tag
        for sublist in Conversation.objects.filter(user_id=user_id).values_list(
            "tags", flat=True
        )
        for tag in sublist
    )
    unused_tags = [tag for tag in user_tags.tags if tag not in all_conversation_tags]

    for tag in unused_tags:
        user_tags.remove_tag(tag)

    printer.yellow("Removed unused tags:", unused_tags)
