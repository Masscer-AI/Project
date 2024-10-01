import chromadb


class ChromaManager:
    client = None

    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path="vector_storage")

    def heartbeat(self) -> str:
        if self.client is None:
            raise Exception("Chroma not yet initialized!")
        return self.client.heartbeat()

    def get_or_create_collection(self, collection_name: str):
        collection = self.client.get_or_create_collection(name=collection_name)
        return collection

    def upsert_chunk(self, collection_name: str, chunk_text: str, chunk_id: str):
        collection = self.get_or_create_collection(collection_name)
        collection.upsert(documents=[chunk_text], ids=[chunk_id])

    def get_results(self, collection_name: str, query_text: str, n_results: int = 4):
        collection = self.get_or_create_collection(collection_name)
        return collection.query(query_texts=[query_text], n_results=n_results)

    def delete_collection(self, collection_name: str):
        print("Deleting collection from chroma")
        self.client.delete_collection(collection_name)


chroma_client = ChromaManager()
