"""
Build system-prompt snippets for assigned document templates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.ai_layers.models import Agent


def format_assigned_templates_instruction(agent: "Agent") -> str:
    """
    Return markdown block listing enabled template assignments for this agent.
    """
    from api.document_templates.models import AgentDocumentTemplateAssignment

    qs = (
        AgentDocumentTemplateAssignment.objects.filter(agent=agent, is_enabled=True)
        .select_related("template")
        .order_by("template__name")
    )
    rows = list(qs)
    if not rows:
        return ""

    lines = [
        "\n\n=== DOCUMENT TEMPLATES ===",
        "The organization attached Word templates to you. When the user needs a filled document, "
        "use `list_document_templates` if you need the full schema, then `render_document_template` "
        "with a JSON object mapping **exact** placeholder names to string values. "
        "After rendering, explicitly include the generated attachment in your response markdown "
        "using `[Download document](attachment:<attachment_id>)`.",
        "",
    ]
    for a in rows:
        t = a.template
        md = t.metadata or {}
        placeholders = md.get("placeholders") or []
        variables = md.get("variables") or {}
        var_lines = []
        if isinstance(placeholders, list):
            for ph in placeholders:
                spec = variables.get(ph) if isinstance(variables, dict) else {}
                if isinstance(spec, dict):
                    desc = (spec.get("description") or "").strip()
                    req = spec.get("required", True)
                    ex = (spec.get("example") or "").strip()
                    var_lines.append(
                        f"  - `{ph}`: required={bool(req)}"
                        + (f"; description: {desc}" if desc else "")
                        + (f"; example: {ex}" if ex else "")
                    )
                else:
                    var_lines.append(f"  - `{ph}`")
        vars_block = "\n".join(var_lines) if var_lines else "  (no placeholders detected)"
        usage = (a.usage_instructions or "").strip()
        lines.append(f"**Template id:** `{t.id}`")
        lines.append(f"**Name:** {t.name}")
        if t.description:
            lines.append(f"**Description:** {t.description}")
        if usage:
            lines.append(f"**When to use (assignment):** {usage}")
        lines.append("**Variables:**")
        lines.append(vars_block)
        lines.append("")
    lines.append("=== END DOCUMENT TEMPLATES ===\n")
    return "\n".join(lines)


def agent_has_template_assignments(agent: "Agent") -> bool:
    from api.document_templates.models import AgentDocumentTemplateAssignment

    return AgentDocumentTemplateAssignment.objects.filter(
        agent=agent, is_enabled=True
    ).exists()
