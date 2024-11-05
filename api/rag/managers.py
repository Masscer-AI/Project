import chromadb

# from chromadb.utils import embedding_functions

# default_ef = embedding_functions.DefaultEmbeddingFunction()


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
        self, collection_name: str, query_texts: list[str], n_results: int = 4
    ):
        # TODO: This is bad, if the collection doesn't exist, ignore
        collection = self.get_or_create_collection(collection_name)

        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
            # where_document={"$contains": "search_string"},
        )

    def get_collection_or_none(self, collection_name: str):
        try:
            return self.client.get_collection(name=collection_name)
        except Exception as e:
            print(e, "EXCEPTION TRYING TO GET COLLECTION")
            return None

    def delete_collection(self, collection_name: str):
        print("Deleting collection from chroma")
        self.client.delete_collection(collection_name)

    def delete_chunk(self, collection_name: str, chunk_id: str):
        # TODO: This is bad, if the collection doesn't exist, ignore
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=[chunk_id])

    def bulk_delete_chunks(self, collection_name: str, chunk_ids: list[str]):
        collection = self.get_collection_or_none(collection_name)
        if collection:
            collection.delete(ids=chunk_ids)


chroma_client = ChromaManager()
