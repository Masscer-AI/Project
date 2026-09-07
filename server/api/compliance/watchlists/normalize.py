from __future__ import annotations

import unicodedata


def fold_text(value: str | None) -> str:
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(value))
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def join_name_parts(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and str(part).strip())


def build_search_document(parts: list[str | None]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        folded = fold_text(part)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        ordered.append(folded)
    return "\n".join(ordered)
