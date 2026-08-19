"""Download Chroma's default ONNX embedding model into the local cache.

The `chromadb` client embeds documents and queries in-process (the Chroma server
only stores the vectors), so every Django/Celery container needs the ~80MB
all-MiniLM-L6-v2 ONNX model in `$HOME/.cache/chroma`. Running this at image build
time bakes the model into the image instead of downloading it on first query.

Failures are non-fatal: the model is downloaded lazily at runtime as a fallback.
"""

import os
import sys

def main() -> int:
    try:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )

        ONNXMiniLM_L6_V2()._download_model_if_not_exists()

        archive = os.path.join(
            ONNXMiniLM_L6_V2.DOWNLOAD_PATH, ONNXMiniLM_L6_V2.ARCHIVE_FILENAME
        )
        if os.path.exists(archive):
            os.remove(archive)

        print(f"Chroma embedding model ready at {ONNXMiniLM_L6_V2.DOWNLOAD_PATH}")
    except Exception as exc:
        print(f"WARNING: could not prefetch Chroma embedding model: {exc}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
