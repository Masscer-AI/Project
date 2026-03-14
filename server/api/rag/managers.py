import chromadb
import os
import subprocess
import sys

# Import the settings
from api.settings import MEDIA_ROOT

# from chromadb.utils import embedding_functions
VECTOR_STORAGE_PATH = os.environ.get(
    "VECTOR_STORAGE_PATH", os.path.join(MEDIA_ROOT, "vector_storage/")
)

if not os.path.exists(VECTOR_STORAGE_PATH):
    os.makedirs(VECTOR_STORAGE_PATH)

# default_ef = embedding_functions.DefaultEmbeddingFunction()
ChromaNotInitializedException = Exception("Chroma not yet initialized!")


class ChromaManager:
    client = None

    def __init__(self) -> None:
        chroma_host = os.environ.get("CHROMA_HOST", "localhost")
        chroma_port = int(os.environ.get("CHROMA_PORT", "8002"))
        self.client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        self.prewarm_default_embedding()

    def prewarm_default_embedding(self):
        # Avoid pulling embedding models during management commands (migrate/makemigrations/etc).
        # For these commands, Chroma is not required and the container is often ephemeral,
        # so downloading the ONNX model repeatedly is wasteful.
        #
        # You can override behavior by explicitly setting CHROMA_PREWARM.
        if os.environ.get("CHROMA_PREWARM") is None:
            mgmt_cmds = {"migrate", "makemigrations", "collectstatic", "test"}
            if any(arg in mgmt_cmds for arg in sys.argv[1:]):
                return

        prewarm_enabled = os.environ.get("CHROMA_PREWARM", "true").lower()
        if prewarm_enabled not in {"1", "true", "yes", "on"}:
            return

        try:
            collection_name = os.environ.get(
                "CHROMA_PREWARM_COLLECTION", "masscer_prewarm"
            )
            collection = self.get_or_create_collection(collection_name)
            collection.upsert(
                ids=["masscer-prewarm-doc"],
                documents=["Masscer Chroma prewarm document."],
                metadatas=[{"system": "prewarm"}],
            )
            collection.query(query_texts=["warmup"], n_results=1)
            print("Chroma prewarm completed.")
        except Exception as e:
            print(f"Chroma prewarm skipped: {e}")

    def heartbeat(self) -> str:
        if self.client is None:
            raise Exception("Chroma not yet initialized!")
        return self.client.heartbeat()

    def get_or_create_collection(self, collection_name: str):
        collection = self.client.get_or_create_collection(name=collection_name)
        return collection

    def upsert_chunk(
        self, collection_name: str, chunk_text: str, chunk_id: str, metadata: dict = {}
    ):
        collection = self.get_or_create_collection(collection_name)
        collection.upsert(documents=[chunk_text], ids=[chunk_id], metadatas=[metadata])

    def bulk_upsert_chunks(
        self,
        collection_name: str,
        documents: list[str],
        chunk_ids: list[str],
        metadatas: list[dict],
    ):
        collection = self.get_or_create_collection(collection_name)
        collection.upsert(documents=documents, ids=chunk_ids, metadatas=metadatas)

    def get_results(
        self,
        collection_name: str,
        query_texts: list[str],
        n_results: int = 4,
        search_string: str = "",
        where: dict | None = None,
    ):
        # TODO: This is bad, if the collection doesn't exist, ignore
        collection = self.get_or_create_collection(collection_name)

        query_kwargs = {
            "query_texts": query_texts,
            "n_results": n_results,
        }

        normalized_search_string = (search_string or "").strip()
        if normalized_search_string:
            query_kwargs["where_document"] = {"$contains": normalized_search_string}

        normalized_where = where if isinstance(where, dict) and where else None
        if normalized_where:
            query_kwargs["where"] = normalized_where

        return collection.query(**query_kwargs)

    def get_collection_or_none(self, collection_name: str):
        try:
            return self.client.get_collection(name=collection_name)
        except Exception as e:
            print(e, "EXCEPTION TRYING TO GET COLLECTION")
            return None

    def delete_collection(self, collection_name: str):
        print("Deleting collection from chroma")
        try:
            self.client.delete_collection(collection_name)
            print("DELETED SUCCESSFULLY")
        except Exception as e:
            print(e, "EXCEPTION TRYING TO DELETE COLLECTION")

    def delete_chunk(self, collection_name: str, chunk_id: str):
        # TODO: This is bad, if the collection doesn't exist, ignore
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=[chunk_id])

    def bulk_delete_chunks(self, collection_name: str, chunk_ids: list[str]):
        collection = self.get_collection_or_none(collection_name)
        if collection:
            collection.delete(ids=chunk_ids)


def start_chroma_server():

    process = subprocess.Popen(
        ["chroma", "run", "--path", VECTOR_STORAGE_PATH, "--port", "8002"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process.wait()


chroma_client = None
try:
    chroma_client = ChromaManager()
except Exception as e:
    print(f"ChromaDB not available: {e}")
    # chroma_client will remain None
    # This allows migrations to run without ChromaDB
