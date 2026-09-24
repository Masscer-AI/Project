from __future__ import annotations

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.website.schemas import CompanyWebsiteExtraction

INSTRUCTIONS = """
You fill company contact fields from a website.
Call fetch_url with the given URL, then fill the schema from that page.
Use only facts visible on the page. Use null when a field is not shown.
nationality is ISO 3166-1 alpha-2 (e.g. MX).
phone includes the country calling code.
Do not invent RFC, dates, addresses, or other identifiers.
""".strip()


def fill_company_from_website(url: str) -> CompanyWebsiteExtraction:
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.tools.fetch_url import get_tool

    loop = AgentLoop.create(
        provider="openai",
        tools=[get_tool()],
        instructions=INSTRUCTIONS,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=CompanyWebsiteExtraction,
        max_iterations=4,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "Read this company website and extract contact fields: "
                    f"{url}"
                ),
            }
        ]
    )
    output = result.output
    if isinstance(output, CompanyWebsiteExtraction):
        return output
    return CompanyWebsiteExtraction.model_validate(output)
