"""
Render DOCX templates with docxtpl, supporting local and remote storage.
"""

from __future__ import annotations

import os
import tempfile
from io import BytesIO
from typing import TYPE_CHECKING

from docxtpl import DocxTemplate

if TYPE_CHECKING:
    from api.document_templates.models import DocumentTemplate


def render_docx_template_to_bytes(template: "DocumentTemplate", variables: dict) -> bytes:
    """
    Load template from Django storage, render with variables, return .docx bytes.

    docxtpl expects a filesystem path; we copy remote files to a temp file when needed.
    """
    suffix = os.path.splitext(template.original_filename or template.file.name)[1] or ".docx"
    with template.file.open("rb") as f:
        raw = f.read()

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(raw)
        tmp.flush()
        tmp.close()
        tpl = DocxTemplate(tmp.name)
        tpl.render(variables or {})
        out = BytesIO()
        tpl.save(out)
        return out.getvalue()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
