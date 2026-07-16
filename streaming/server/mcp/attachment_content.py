"""Map attachment bytes to MCP content blocks."""

from __future__ import annotations

import base64
import os

import mcp.types as types

DOWNLOAD_ATTACHMENT_TOOL = "download_attachment"

MCP_ATTACHMENT_MAX_BYTES = int(
    os.getenv("MCP_ATTACHMENT_MAX_BYTES", str(10 * 1024 * 1024))
)


def download_attachment_tool() -> types.Tool:
    return types.Tool(
        name=DOWNLOAD_ATTACHMENT_TOOL,
        description=(
            "Download a Masscer file attachment by UUID. Use attachment_id from a "
            "prior agent response attachments[] array. Returns audio, image, or "
            "binary file content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "attachment_id": {
                    "type": "string",
                    "description": (
                        "UUID from attachments[].attachment_id in an agent tool result"
                    ),
                },
            },
            "required": ["attachment_id"],
        },
    )


def attachment_bytes_to_content_blocks(
    *,
    attachment_id: str,
    data: bytes,
    mime_type: str,
    filename: str | None = None,
) -> list[types.ContentBlock]:
    if len(data) > MCP_ATTACHMENT_MAX_BYTES:
        raise ValueError(
            f"Attachment exceeds maximum size of {MCP_ATTACHMENT_MAX_BYTES} bytes"
        )

    normalized_mime = (mime_type or "application/octet-stream").split(";")[0].strip()
    b64 = base64.b64encode(data).decode("ascii")
    uri = f"masscer://attachment/{attachment_id}"

    if normalized_mime.startswith("audio/"):
        return [
            types.AudioContent(
                type="audio",
                data=b64,
                mimeType=normalized_mime,
            )
        ]

    if normalized_mime.startswith("image/"):
        return [
            types.ImageContent(
                type="image",
                data=b64,
                mimeType=normalized_mime,
            )
        ]

    blocks: list[types.ContentBlock] = [
        types.EmbeddedResource(
            type="resource",
            resource=types.BlobResourceContents(
                uri=uri,
                mimeType=normalized_mime,
                blob=b64,
            ),
        )
    ]
    if filename:
        blocks.append(
            types.TextContent(
                type="text",
                text=f'Attachment "{filename}" ({normalized_mime}, {len(data)} bytes)',
            )
        )
    return blocks
