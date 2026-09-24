from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyWebsiteExtraction(BaseModel):
    legal_name: str | None = Field(
        default=None, description="Company legal or trade name as shown on the page."
    )
    nationality: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code, e.g. MX.",
    )
    economic_activity: str | None = Field(
        default=None, description="What the company does (giro / occupation)."
    )
    email: str | None = Field(default=None, description="Public contact email.")
    phone: str | None = Field(
        default=None,
        description="Public phone with country code digits, e.g. +525512345678.",
    )
