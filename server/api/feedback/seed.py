from api.feedback.models import ReactionTemplate
from api.utils.color_printer import printer

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


def sync_system_reactions() -> int:
    """Create system ReactionTemplates if none exist. Returns number created."""
    if ReactionTemplate.objects.filter(type="system").exists():
        return 0

    for reaction in SYSTEM_REACTIONS:
        ReactionTemplate.objects.create(
            name=reaction["name"],
            emoji=reaction["emoji"],
            emoji_type=reaction["emoji_type"],
            description=reaction["description"],
            type="system",
        )
    printer.success("System reactions were created successfully!")
    return len(SYSTEM_REACTIONS)
