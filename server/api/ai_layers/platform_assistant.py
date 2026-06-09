"""
Platform assistant provisioning and prompt constants.

Each organization gets one platform assistant row (association anchor).
Behavior (prompt, tools) is defined here in code, not via user-editable DB fields.
"""

from __future__ import annotations

import os

from api.ai_layers.models import Agent, AgentKind, DEFAULT_SYSTEM_PROMPT

PLATFORM_ASSISTANT_NAME = "Masscer Assistant"
PLATFORM_ASSISTANT_SLUG_PREFIX = "masscer-assistant"

# Override with PLATFORM_ASSISTANT_MODEL_SLUG env var; falls back to gpt-4.1-mini.
PLATFORM_ASSISTANT_MODEL_SLUG: str = os.environ.get(
    "PLATFORM_ASSISTANT_MODEL_SLUG", "gpt-5.5-mini"
)

PLATFORM_ASSISTANT_ACT_AS = """
You are the Masscer Assistant — an internal onboarding and help guide for the Masscer platform.
You help organization owners and authorized members learn how to use Masscer: inviting users,
managing roles, configuring agents, and understanding core features.
Be concise, friendly, and action-oriented. When you don't know something, say so honestly.
Do not pretend to perform actions you cannot execute via your tools.

When the user asks how to do something in Masscer:
1. Call list_masscer_help_topics if you are unsure which topic_id fits.
2. Call get_masscer_help_topic(topic_id) for step-by-step guidance.
3. Always include the app_url from the tool result as a markdown link, e.g. [Open page](/organization?activeTab=members).
4. If access_allowed is false, explain which permission is missing — do not invent steps.

Workflow assignments (optional but encouraged for multi-step questions):
- Call list_user_assignments first to avoid duplicate checklists.
- Call read_masscer_instructions to see the ONLY valid step button actions (navigate / focus_element targets). Never invent routes, selectors, or flows.
- When helpful, call create_user_assignment with a title and ordered steps. Each step has a title, optional description, and an optional button with action_type + action_target taken from read_masscer_instructions.
- Keep each step to a single concrete action. The user tracks progress in the Tasks panel and marks steps done manually.
- Viewing invoices/billing history is not available yet — do not create such steps.
- Help topic content from tools is in English; present it in the user's language.
""".strip()

PLATFORM_ASSISTANT_SALUTE = (
    "Hi! I'm your Masscer Assistant. I can help you get started with your organization — "
    "inviting members, understanding features, and more. What would you like help with?"
)

PLATFORM_ASSISTANT_CONVERSATION_TITLE_PROMPT = """
Given the first messages in a Masscer onboarding/help chat, generate a short conversation title.
The title must start with one emoji, then plain text (no quotes). Max 50 characters.
Focus on what the user asked about (e.g. inviting members, creating agents, billing, tasks).
Examples: 🚀 Getting started with Masscer, 👥 How to invite team members, 🤖 Create your first agent
Return ONLY the title (emoji + text).
""".strip()

PLATFORM_ASSISTANT_SYSTEM_PROMPT = """
{{act_as}}

You are assisting users inside the Masscer application. Focus on practical onboarding guidance.

Organization context (use when relevant):
{{context}}
""".strip()


def platform_assistant_slug_for_org(org_id) -> str:
    org_str = str(org_id).replace("-", "")[:8]
    return f"{PLATFORM_ASSISTANT_SLUG_PREFIX}-{org_str}"


def provision_platform_assistant(organization) -> tuple[Agent, bool]:
    """
    Idempotently create the platform assistant for an organization.

    Returns (agent, created).
    """
    slug = platform_assistant_slug_for_org(organization.id)
    agent, created = Agent.objects.get_or_create(
        organization=organization,
        agent_kind=AgentKind.PLATFORM_ASSISTANT,
        defaults={
            "name": PLATFORM_ASSISTANT_NAME,
            "slug": slug,
            "salute": PLATFORM_ASSISTANT_SALUTE,
            "act_as": PLATFORM_ASSISTANT_ACT_AS,
            "conversation_title_prompt": PLATFORM_ASSISTANT_CONVERSATION_TITLE_PROMPT,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "user": None,
            "model_provider": "openai",
            "model_slug": PLATFORM_ASSISTANT_MODEL_SLUG,
        },
    )
    update_fields: list[str] = []
    if not created and agent.slug != slug:
        agent.slug = slug
        update_fields.append("slug")
    if not agent.conversation_title_prompt:
        agent.conversation_title_prompt = PLATFORM_ASSISTANT_CONVERSATION_TITLE_PROMPT
        update_fields.append("conversation_title_prompt")
    if agent.model_slug != PLATFORM_ASSISTANT_MODEL_SLUG and not agent.llm_id:
        agent.model_slug = PLATFORM_ASSISTANT_MODEL_SLUG
        update_fields.append("model_slug")
    if update_fields:
        agent.save(update_fields=update_fields)

    if created:
        try:
            from api.ai_layers.cache_utils import bump_agent_list_version_for_org_members

            bump_agent_list_version_for_org_members(organization)
        except Exception:
            pass

    return agent, created


def build_platform_assistant_instructions(organization, *, clock_context: str = "") -> str:
    """Build runtime instructions from code constants + live org context."""
    from api.authenticate.models import UserProfile

    member_count = UserProfile.objects.filter(organization=organization).count()
    owner_email = ""
    if organization.owner_id:
        owner_email = getattr(organization.owner, "email", "") or ""

    plan_slug = ""
    sub = organization.subscriptions.select_related("plan").order_by("-created_at").first()
    if sub and sub.plan_id:
        plan_slug = sub.plan.slug or ""

    context_lines = [
        f"Organization name: {organization.name}",
        f"Organization id: {organization.id}",
        f"Member count (profiles linked to org): {member_count}",
    ]
    if owner_email:
        context_lines.append(f"Owner email: {owner_email}")
    if plan_slug:
        context_lines.append(f"Subscription plan: {plan_slug}")
    if organization.description:
        context_lines.append(f"Description: {organization.description}")

    context = "\n".join(context_lines)
    formatted = PLATFORM_ASSISTANT_SYSTEM_PROMPT.replace(
        "{{act_as}}", PLATFORM_ASSISTANT_ACT_AS
    ).replace("{{context}}", context)
    formatted += f"\n\nYour name is: {PLATFORM_ASSISTANT_NAME}."
    formatted += (
        "\n\nProduct help tools: list_masscer_help_topics, get_masscer_help_topic. "
        "Assignment tools: read_masscer_instructions, list_user_assignments, create_user_assignment. "
        "Prefer these over guessing UI paths."
    )
    if clock_context:
        formatted += f"\n{clock_context}"
    return formatted
