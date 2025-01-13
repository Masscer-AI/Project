from django.apps import AppConfig
from api.utils.color_printer import printer
from django.db.utils import OperationalError

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
        self.startup_function()

    def startup_function(self):
        from .models import ReactionTemplate

        try:
            # printer.blue(f"Running startup function for {self.name}")
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
                printer.success("System reactions were created successfully!")
                return
            # printer.info("System reactions already exist :)")

        except OperationalError:
            printer.red(
                f"Database is not ready. Skipping {self.name} startup function."
            )
