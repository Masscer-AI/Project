"""
Utilities for reading and writing Excel workbooks (.xlsx write, .xlsx/.xls read).
"""

from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
XLS_CONTENT_TYPE = "application/vnd.ms-excel"
OLE_COMPOUND_MAGIC = b"\xd0\xcf\x11\xe0"

_SHEET_NAME_SAFE = re.compile(r"[\[\]\:\*\?\/\\]+")
_MAX_SHEET_NAME_LEN = 31
_MAX_ROWS_PER_SHEET = 10_000
_MAX_COLS_PER_SHEET = 256


def _sanitize_sheet_name(name: str, fallback: str) -> str:
    cleaned = _SHEET_NAME_SAFE.sub("_", (name or "").strip())[:_MAX_SHEET_NAME_LEN]
    return cleaned or fallback


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def extract_xlsx_text_from_bytes(raw: bytes) -> str:
    """
    Convert an .xlsx workbook into sheet-aware plain text for RAG indexing.

    Each sheet is rendered as:
      === Sheet: <name> ===
      col1 | col2 | ...
    """
    text = _extract_workbook_text(raw, data_only=True)
    if not text:
        text = _extract_workbook_text(raw, data_only=False)
    if not text:
        raise ValueError(
            "The Excel file has no readable cell content. "
            "If it uses formulas only, open it in Excel and save so values are cached."
        )
    return text


def _extract_workbook_text(raw: bytes, *, data_only: bool) -> str:
    workbook = load_workbook(
        BytesIO(raw), read_only=True, data_only=data_only
    )
    parts: list[str] = []

    try:
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [_cell_to_text(cell) for cell in row]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                parts.append(f"=== Sheet: {sheet_name} ===\n" + "\n".join(rows))
    finally:
        workbook.close()

    return "\n\n".join(parts).strip()


def extract_xls_text_from_bytes(raw: bytes) -> str:
    """
    Convert a legacy .xls workbook into sheet-aware plain text for RAG indexing.

    Output format matches extract_xlsx_text_from_bytes.
    """
    try:
        import xlrd
        from xlrd import XLRDError
    except ModuleNotFoundError as exc:
        raise ValueError(
            "Excel .xls support is not installed on this server (missing xlrd). "
            "Rebuild and redeploy the Django image."
        ) from exc

    try:
        workbook = xlrd.open_workbook(file_contents=raw)
    except XLRDError as exc:
        raise ValueError(f"Could not read Excel file: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Could not read Excel file: {exc}") from exc

    parts: list[str] = []
    for sheet in workbook.sheets():
        rows: list[str] = []
        for rx in range(min(sheet.nrows, _MAX_ROWS_PER_SHEET)):
            cells = [
                _xls_cell_to_text(sheet.cell(rx, cx), workbook.datemode)
                for cx in range(min(sheet.ncols, _MAX_COLS_PER_SHEET))
            ]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            parts.append(f"=== Sheet: {sheet.name} ===\n" + "\n".join(rows))

    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError(
            "The Excel file has no readable cell content. "
            "If it uses formulas only, open it in Excel and save so values are cached."
        )
    return text


def _xls_cell_to_text(cell: Any, datemode: int) -> str:
    try:
        import xlrd
    except ModuleNotFoundError:
        return _cell_to_text(getattr(cell, "value", None))

    ctype = getattr(cell, "ctype", None)
    value = getattr(cell, "value", None)
    if ctype == xlrd.XL_CELL_EMPTY or ctype == xlrd.XL_CELL_BLANK:
        return ""
    if ctype == xlrd.XL_CELL_DATE:
        try:
            return str(xlrd.xldate_as_datetime(value, datemode)).strip()
        except Exception:
            return _cell_to_text(value)
    if ctype == xlrd.XL_CELL_BOOLEAN:
        return "TRUE" if value else "FALSE"
    if ctype == xlrd.XL_CELL_NUMBER:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return _cell_to_text(value)
    return _cell_to_text(value)


def build_xlsx_bytes_from_sheets(sheets: list[dict[str, Any]]) -> bytes:
    """
    Build an .xlsx workbook from structured sheet definitions.

    Each sheet dict supports:
      - name: str
      - headers: list[str] (optional)
      - rows: list[list[Any]] (optional)
    """
    if not sheets:
        raise ValueError("At least one sheet is required")

    workbook = Workbook()
    workbook.remove(workbook.active)

    for index, sheet_def in enumerate(sheets):
        if not isinstance(sheet_def, dict):
            raise ValueError(f"sheets[{index}] must be an object")

        sheet_name = _sanitize_sheet_name(
            str(sheet_def.get("name") or ""),
            fallback=f"Sheet{index + 1}",
        )
        worksheet = workbook.create_sheet(title=sheet_name)

        headers = sheet_def.get("headers") or []
        if headers and not isinstance(headers, list):
            raise ValueError(f"sheets[{index}].headers must be a list")
        if headers:
            worksheet.append([_cell_to_text(h) for h in headers[:_MAX_COLS_PER_SHEET]])

        rows = sheet_def.get("rows") or []
        if rows and not isinstance(rows, list):
            raise ValueError(f"sheets[{index}].rows must be a list")

        row_count = 0
        for row in rows:
            if row_count >= _MAX_ROWS_PER_SHEET:
                break
            if not isinstance(row, list):
                raise ValueError(f"sheets[{index}].rows entries must be lists")
            worksheet.append(
                [_cell_to_text(cell) for cell in row[:_MAX_COLS_PER_SHEET]]
            )
            row_count += 1

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def parse_sheets_json(sheets_json: str) -> list[dict[str, Any]]:
    """Parse a JSON string into sheet definitions for workbook creation."""
    try:
        parsed = json.loads(sheets_json or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid sheets JSON: {exc}") from exc

    if not isinstance(parsed, list):
        raise ValueError("sheets JSON must be a list of sheet objects")
    if not parsed:
        raise ValueError("sheets JSON must contain at least one sheet")
    return parsed
