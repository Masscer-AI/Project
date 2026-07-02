from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError


class OrganizationTenantTheme(BaseModel):
    primary_color: Optional[str] = Field(
      default=None,
      pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
      description="Primary color in hex format (#RGB or #RRGGBB)",
  )


def validate_tenant_theme(data: dict | None) -> dict:
    """Validate and normalize tenant theme JSON for storage."""
    if not data:
        return {}
    try:
        return OrganizationTenantTheme.model_validate(data).model_dump(exclude_none=True)
    except ValidationError as exc:
        first = exc.errors()[0]
        message = first.get("msg", "Invalid theme")
        loc = first.get("loc", ())
        if loc:
            message = f"{'.'.join(str(part) for part in loc)}: {message}"
        raise ValueError(message) from exc


def tenant_theme_for_response(theme: dict | None) -> dict[str, Any]:
    if not theme:
        return {}
    return OrganizationTenantTheme.model_validate(theme).model_dump(exclude_none=True)
