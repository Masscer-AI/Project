from io import BytesIO

from django.test import SimpleTestCase

from api.utils.spreadsheet_tools import (
    build_xlsx_bytes_from_sheets,
    extract_xlsx_text_from_bytes,
    parse_sheets_json,
)


class SpreadsheetToolsTests(SimpleTestCase):
    def _sample_workbook_bytes(self) -> bytes:
        return build_xlsx_bytes_from_sheets(
            [
                {
                    "name": "Sales",
                    "headers": ["Month", "Revenue"],
                    "rows": [["Jan", 1000], ["Feb", 1200]],
                },
                {
                    "name": "Notes",
                    "rows": [["Summary", "Q1 growth"]],
                },
            ]
        )

    def test_build_xlsx_bytes_produces_valid_zip(self):
        raw = self._sample_workbook_bytes()
        self.assertTrue(raw.startswith(b"PK"))

    def test_extract_xlsx_text_from_bytes(self):
        raw = self._sample_workbook_bytes()
        text = extract_xlsx_text_from_bytes(raw)
        self.assertIn("=== Sheet: Sales ===", text)
        self.assertIn("Month | Revenue", text)
        self.assertIn("Jan | 1000", text)
        self.assertIn("=== Sheet: Notes ===", text)
        self.assertIn("Summary | Q1 growth", text)

    def test_extract_xlsx_rejects_empty_workbook(self):
        from io import BytesIO
        from openpyxl import Workbook

        buf = BytesIO()
        Workbook().save(buf)
        with self.assertRaises(ValueError):
            extract_xlsx_text_from_bytes(buf.getvalue())

    def test_parse_sheets_json(self):
        sheets = parse_sheets_json(
            '[{"name":"A","headers":["H"],"rows":[["1"]]}]'
        )
        self.assertEqual(sheets[0]["name"], "A")
        self.assertEqual(sheets[0]["headers"], ["H"])

    def test_build_requires_at_least_one_sheet(self):
        with self.assertRaises(ValueError):
            build_xlsx_bytes_from_sheets([])

    def test_read_file_content_xlsx_branch(self):
        from api.rag.actions import read_file_content

        raw = self._sample_workbook_bytes()
        buffer = BytesIO(raw)
        buffer.name = "report.xlsx"
        text, file_name = read_file_content(buffer)
        self.assertEqual(file_name, "report.xlsx")
        self.assertIn("Month | Revenue", text)

    def test_read_file_content_xlsx_without_extension_uses_mime(self):
        from api.rag.actions import read_file_content

        raw = self._sample_workbook_bytes()
        buffer = BytesIO(raw)
        buffer.name = "upload"
        buffer.content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        text, _ = read_file_content(buffer)
        self.assertIn("Month | Revenue", text)

    def test_read_file_content_xlsx_uses_post_name_fallback(self):
        from api.rag.actions import read_file_content

        raw = self._sample_workbook_bytes()
        buffer = BytesIO(raw)
        buffer.name = "upload"
        text, file_name = read_file_content(
            buffer,
            fallback_name="MEDIOS DIGITALES- JUNIO 2026 (1).xlsx",
        )
        self.assertIn("Month | Revenue", text)
        self.assertEqual(file_name, "MEDIOS DIGITALES- JUNIO 2026 (1).xlsx")

    def test_read_file_content_xlsx_without_extension_uses_magic_bytes(self):
        from api.rag.actions import read_file_content

        raw = self._sample_workbook_bytes()
        buffer = BytesIO(raw)
        buffer.name = "upload.bin"
        text, _ = read_file_content(buffer)
        self.assertIn("Month | Revenue", text)
