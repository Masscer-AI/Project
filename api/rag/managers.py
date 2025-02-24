import chromadb
import time
import os
import subprocess

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
        self.client = chromadb.HttpClient(host="localhost", port=8002)

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
        where: dict = {},
    ):
        # TODO: This is bad, if the collection doesn't exist, ignore
        collection = self.get_or_create_collection(collection_name)

        if search_string:
            return collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where_document={"$contains": search_string},
                where=where,
            )
        return collection.query(
            query_texts=query_texts, n_results=n_results, where=where
        )

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
    # start_chroma_server()
    # time.sleep(3)

    # chroma_client = ChromaManager()
    raise ChromaNotInitializedException
