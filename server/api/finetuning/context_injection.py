"""Inject approved completions into agent task context based on context_rules."""

from __future__ import annotations

from api.ai_layers.models import Agent
from api.messaging.models import Conversation

from .context_rules import parse_context_rules
from .models import Completion

MAX_AUTO_COMPLETIONS = 12
MAX_AUTO_COMPLETION_CHARS = 12_000


def completion_matches_context_rules(completion: Completion, conversation: Conversation) -> bool:
    rules = parse_context_rules(completion.context_rules)
    if rules.include_always:
        return True
    if not rules.include_for_tags:
        return False
    conv_tags = conversation.tags or []
    if not isinstance(conv_tags, list):
        return False
    conv_tag_ids = {int(t) for t in conv_tags if t is not None}
    rule_tag_ids = set(rules.include_for_tags)
    return bool(conv_tag_ids & rule_tag_ids)


def get_completions_for_context(agent: Agent, conversation: Conversation) -> list[Completion]:
    qs = (
        Completion.objects.filter(
            approved=True,
            assignments__agent=agent,
        )
        .distinct()
        .order_by("-updated_at")
    )
    return [c for c in qs if completion_matches_context_rules(c, conversation)]


def format_completions_context_block(completions: list[Completion]) -> str:
    if not completions:
        return ""

    lines = [
        "\n\n=== AGENT TRAINING (auto-included) ===",
        "The following approved training rows apply to this turn. Follow them when relevant.\n",
    ]
    total_chars = 0
    included = 0

    for completion in completions:
        if included >= MAX_AUTO_COMPLETIONS:
            lines.append(
                f"\n[... {len(completions) - included} more training row(s) omitted for context limit ...]"
            )
            break

        block = (
            f"--- Training row #{completion.id} ---\n"
            f"CUE (when to apply): {completion.prompt.strip()}\n"
            f"PAYLOAD (what to apply): {completion.answer.strip()}\n"
        )
        if total_chars + len(block) > MAX_AUTO_COMPLETION_CHARS:
            lines.append(
                f"\n[... remaining training rows omitted ({MAX_AUTO_COMPLETION_CHARS} char limit) ...]"
            )
            break

        lines.append(block)
        total_chars += len(block)
        included += 1

    lines.append("=== END AGENT TRAINING ===\n")
    return "\n".join(lines)
