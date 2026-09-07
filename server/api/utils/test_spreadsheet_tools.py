from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase

from api.utils.spreadsheet_tools import (
    OLE_COMPOUND_MAGIC,
    build_xlsx_bytes_from_sheets,
    extract_xls_text_from_bytes,
    extract_xlsx_text_from_bytes,
    parse_sheets_json,
)

_TESTDATA = Path(__file__).resolve().parent / "testdata"


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

    def _sample_xls_bytes(self) -> bytes:
        raw = (_TESTDATA / "sample.xls").read_bytes()
        self.assertTrue(raw.startswith(OLE_COMPOUND_MAGIC))
        return raw

    def test_extract_xls_text_from_bytes(self):
        text = extract_xls_text_from_bytes(self._sample_xls_bytes())
        self.assertIn("=== Sheet: Sales ===", text)
        self.assertIn("Month | Revenue", text)
        self.assertIn("Jan | 1000", text)
        self.assertIn("=== Sheet: Notes ===", text)
        self.assertIn("Summary | Q1 growth", text)

    def test_extract_xls_rejects_empty_workbook(self):
        raw = (_TESTDATA / "empty.xls").read_bytes()
        with self.assertRaises(ValueError):
            extract_xls_text_from_bytes(raw)

    def test_read_file_content_xls_branch(self):
        from api.rag.actions import read_file_content

        buffer = BytesIO(self._sample_xls_bytes())
        buffer.name = "report.xls"
        text, file_name = read_file_content(buffer)
        self.assertEqual(file_name, "report.xls")
        self.assertIn("Month | Revenue", text)
        self.assertIn("Jan | 1000", text)

    def test_read_file_content_xls_without_extension_uses_mime(self):
        from api.rag.actions import read_file_content

        buffer = BytesIO(self._sample_xls_bytes())
        buffer.name = "upload"
        buffer.content_type = "application/vnd.ms-excel"
        text, _ = read_file_content(buffer)
        self.assertIn("Month | Revenue", text)

    def test_read_file_content_xls_without_extension_uses_magic_bytes(self):
        from api.rag.actions import read_file_content

        buffer = BytesIO(self._sample_xls_bytes())
        buffer.name = "upload.bin"
        text, _ = read_file_content(buffer)
        self.assertIn("Month | Revenue", text)

    def test_ms_excel_mime_with_xlsx_bytes_still_reads_xlsx(self):
        from api.rag.actions import read_file_content

        buffer = BytesIO(self._sample_workbook_bytes())
        buffer.name = "upload"
        buffer.content_type = "application/vnd.ms-excel"
        text, _ = read_file_content(buffer)
        self.assertIn("Month | Revenue", text)

    def test_infer_data_url_ext_xls_mime_and_filename(self):
        from api.messaging.views import _infer_data_url_attachment_ext

        raw = self._sample_xls_bytes()
        self.assertEqual(
            _infer_data_url_attachment_ext(
                "data:application/vnd.ms-excel;base64",
                "sheet.xls",
                raw,
            ),
            "xls",
        )
        self.assertEqual(
            _infer_data_url_attachment_ext(
                "data:application/octet-stream;base64",
                "legacy.xls",
                raw,
            ),
            "xls",
        )
        self.assertEqual(
            _infer_data_url_attachment_ext(
                "data:application/octet-stream;base64",
                "upload.bin",
                raw,
            ),
            "xls",
        )

    def test_infer_data_url_ext_ms_excel_mime_with_xlsx_bytes(self):
        from api.messaging.views import _infer_data_url_attachment_ext

        raw = self._sample_workbook_bytes()
        self.assertEqual(
            _infer_data_url_attachment_ext(
                "data:application/vnd.ms-excel;base64",
                "sheet.xls",
                raw,
            ),
            "xlsx",
        )

    def test_extract_spreadsheet_text_for_model_xls(self):
        from api.ai_layers.tools.read_attachment import (
            _extract_spreadsheet_text_for_model,
        )

        text = _extract_spreadsheet_text_for_model(
            self._sample_xls_bytes(),
            "report.xls",
            "application/vnd.ms-excel",
        )
        self.assertIsNotNone(text)
        self.assertIn("Month | Revenue", text)
        self.assertIn("Jan | 1000", text)
