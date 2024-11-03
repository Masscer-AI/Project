from django.apps import AppConfig

SYSTEM_REACTIONS = [
    {
        "name": "Wow",
        "emoji": "🤯",
        "emoji_type": "text",
        "description": "wow-reaction-desc",
    },
    {
        "name": "Like",
        "emoji": "👍",
        "emoji_type": "text",
        "description": "like-reaction-desc",
    },
    {
        "name": "Heart",
        "emoji": "❤️",
        "emoji_type": "text",
        "description": "heart-reaction-desc",
    },
    {
        "name": "Laugh",
        "emoji": "😂",
        "emoji_type": "text",
        "description": "laugh-reaction-desc",
    },
    {
        "name": "Dislike",
        "emoji": "👎",
        "emoji_type": "text",
        "description": "dislike-reaction-desc",
    },
    {
        "name": "Hmm",
        "emoji": "🤔",
        "emoji_type": "text",
        "description": "hmm-reaction-desc",
    },
    {
        "name": "Horrible",
        "emoji": "🤮",
        "emoji_type": "text",
        "description": "horrible-reaction-desc",
    },
    {
        "name": "Robot",
        "emoji": "🤖",
        "emoji_type": "text",
        "description": "robot-reaction-desc",
    },
]


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.feedback"

    def ready(self):
        from .models import ReactionTemplate

        all_system_reactions = ReactionTemplate.objects.filter(type="system")
        if all_system_reactions.count() == 0:
            for reaction in SYSTEM_REACTIONS:
                ReactionTemplate.objects.create(
                    name=reaction["name"],
                    emoji=reaction["emoji"],
                    emoji_type=reaction["emoji_type"],
                    description=reaction["description"],
                    type="system",
                )
        print("Feedback app is ready!")
