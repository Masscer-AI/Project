"""Tests for MCP download_attachment tool and attachment content mapping."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import AsyncMock, patch

import mcp.types as types

from server.mcp.attachment_content import (
    DOWNLOAD_ATTACHMENT_TOOL,
    attachment_bytes_to_content_blocks,
    download_attachment_tool,
)
from server.mcp.auth import set_mcp_bearer_token
from server.mcp.server import _handle_download_attachment


class AttachmentContentTests(unittest.TestCase):
    def test_audio_returns_audio_content(self):
        data = b"fake-audio-bytes"
        blocks = attachment_bytes_to_content_blocks(
            attachment_id="abc-123",
            data=data,
            mime_type="audio/mpeg",
            filename="dialogue.mp3",
        )
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertIsInstance(block, types.AudioContent)
        self.assertEqual(block.mimeType, "audio/mpeg")
        self.assertEqual(base64.b64decode(block.data), data)

    def test_image_returns_image_content(self):
        data = b"\x89PNG"
        blocks = attachment_bytes_to_content_blocks(
            attachment_id="img-1",
            data=data,
            mime_type="image/png",
        )
        self.assertEqual(len(blocks), 1)
        self.assertIsInstance(blocks[0], types.ImageContent)

    def test_other_file_returns_embedded_resource(self):
        data = b"excel-bytes"
        blocks = attachment_bytes_to_content_blocks(
            attachment_id="file-1",
            data=data,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="report.xlsx",
        )
        self.assertEqual(len(blocks), 2)
        self.assertIsInstance(blocks[0], types.EmbeddedResource)
        self.assertIsInstance(blocks[0].resource, types.BlobResourceContents)
        self.assertIsInstance(blocks[1], types.TextContent)

    def test_rejects_oversized_attachment(self):
        with patch(
            "server.mcp.attachment_content.MCP_ATTACHMENT_MAX_BYTES",
            10,
        ):
            with self.assertRaises(ValueError) as ctx:
                attachment_bytes_to_content_blocks(
                    attachment_id="big",
                    data=b"x" * 11,
                    mime_type="audio/mpeg",
                )
            self.assertIn("maximum size", str(ctx.exception))


class DownloadAttachmentToolDefinitionTests(unittest.TestCase):
    def test_download_attachment_tool_schema(self):
        tool = download_attachment_tool()
        self.assertEqual(tool.name, DOWNLOAD_ATTACHMENT_TOOL)
        self.assertIn("attachment_id", tool.inputSchema["properties"])
        self.assertEqual(tool.inputSchema["required"], ["attachment_id"])


class DownloadAttachmentToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        set_mcp_bearer_token("test-token")

    async def asyncTearDown(self):
        set_mcp_bearer_token(None)

    async def test_call_download_attachment_returns_audio(self):
        audio = b"mp3-data"
        mock_client = AsyncMock()
        mock_client.download_attachment = AsyncMock(
            return_value=(audio, "audio/mpeg", "clip.mp3")
        )

        blocks = await _handle_download_attachment(
            mock_client,
            {"attachment_id": "550e8400-e29b-41d4-a716-446655440000"},
        )

        self.assertEqual(len(blocks), 1)
        self.assertIsInstance(blocks[0], types.AudioContent)
        mock_client.download_attachment.assert_awaited_once_with(
            "550e8400-e29b-41d4-a716-446655440000"
        )

    async def test_call_download_attachment_requires_id(self):
        mock_client = AsyncMock()
        with self.assertRaises(ValueError) as ctx:
            await _handle_download_attachment(mock_client, {})
        self.assertIn("attachment_id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
