import json
import fitz
import chardet
from docx import Document as DocxDocument
from io import BytesIO
from .models import Chunk, Document, Collection
from api.utils.color_printer import printer
from api.utils.openai_functions import (
    create_structured_completion,
    create_completion_openai,
)
from pydantic import BaseModel, Field


def detect_file_encoding(file):
    raw_data = file.read(10000)
    result = chardet.detect(raw_data)
    file.seek(0)
    return result["encoding"]


def read_file_content(file):
    file_extension = file.name.split(".")[-1].lower()
    file_name = file.name

    if file_extension == "pdf":
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text()
        return text, file_name
    elif file_extension == "docx":
        doc = DocxDocument(BytesIO(file.read()))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text, file_name
    else:
        file_encoding = detect_file_encoding(file)
        return file.read().decode(file_encoding), file_name


class ChunkBriefModel(BaseModel):
    tags: str = Field(
        ...,
        description="A comma-separated list of tags associated with the chunk. Up to 3 words",
    )
    brief: str = Field(
        ...,
        description="A brief summary of max 25 words that describes the chunk content",
    )


def generate_chunk_brief(chunk_id):
    _system = """
You are a Machine Learning an AI expert. You are classifying chunks for a RAG pipeline. The goals is tu summarice and classify the content of an abstract piece of text. You goal is to return kwywords that can be potencially related to the chunk content and to summarice its content in up to 80 words, try to explain briefly what is the content of the chunk.


Everything must be in the same language as the chunk.
"""

    c = Chunk.objects.get(pk=chunk_id)
    printer.red(f"Generating chunk brief for {c.pk}")
    printer.blue(c.content)
    chunkito = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=_system,
        user_prompt=c.content,
        response_format=ChunkBriefModel,
    )
    printer.green(chunkito)
    c.brief = chunkito.brief
    c.tags = chunkito.tags
    c.save()


def generate_document_brief(document_id: int):
    number_of_characters = 20000
    _system = f"""
You are an AI and Machine Learning Specialist.
You task is to summarice the content of a document in up to 100 words, explaining what is the document and an overview of its content.
You will receive the first {number_of_characters} characters in the document.

The brief must be in the same language as the document.
"""
    d = Document.objects.get(pk=document_id)
    first_20000_chars = d.text[:number_of_characters]
    brief = create_completion_openai(
        system_prompt=_system, user_message=first_20000_chars
    )
    d.brief = brief
    d.save()


class SelectedChunks(BaseModel):
    queries: list[str] = Field(
        ...,
        description="A list of 3 different queries that can lead to the best results when using a vector store to retrieve information about the collection where the chunks are stored. The goals is to provide another AI with relevant context from the vector storage",
    )
    tags: str = Field(
        ...,
        description="A command separated list of related tags",
    )
    search_string: str = Field(
        ...,
        description="A one up to three words string that can be in the texts stored in the vector storage system",
    )


def querify_context(context: str, collection: Collection) -> SelectedChunks:

    chunks = get_chunks_for_collection(collection)
    printer.yellow(len(chunks), "Number of chunks for the collection")
    chunks_str = " ".join([json.dumps({"brief": c.content[100:500]}) for c in chunks])

    _system = f"""
You are a AI and Machine Learning specialist.

The following context contains a brief of each chunk stored in a vector storage the user is querying and tags associated with them.


CHUNKS:
---
{chunks_str}
---

The following context takes part of a conversation between the user and an AI assistant

CONTEXT:
---
{context}
---



Please return the queries that can lead to the best results when querying the vector storage as per user requirement.
"""
    queries = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=_system,
        user_prompt=chunks_str,
        response_format=SelectedChunks,
    )
    return queries


def get_chunks_for_collection(collection):
    # Get all documents associated with the collection
    documents = Document.objects.filter(collection=collection)

    # Get all chunks associated with those documents
    chunks = Chunk.objects.filter(document__in=documents)

    return chunks




def extract_rag_results(rag_results, context):
    documents_context = ""
    complete_context = context
    counter = 0
    added_sources = []
    sources = []
    if rag_results is not None:
        metadatas = rag_results["results"]["metadatas"]
        for meta in metadatas:
            for ref in meta:
                if len(ref) > 0:
                    if ref in added_sources:
                        continue

                    sources.append(ref)
                    added_sources.append(ref)

                    documents_context += f"vector_href='#{ref.get('model_name', 'chunk')}-{ref.get('model_id', 132132)}'\nVECTOR CONTENT:\n--- {ref.get('content', '')}---"
                    counter += 1

        if len(documents_context) > 0:
            complete_context += f"\n\nThe following is information about a embeddings vector storage querying the user message: ---start_vector_context\n\n{documents_context}\n\n---end_vector_context---\nIf you use information from the vector storage, please cite the resourcess in anchor tags using the provided href, for example: <a href='#chunk-CHUNK_ID' target='__blank'>SOME_RELATED_CONECTOR</a> where  SOME_RELATED_CONECTOR is a three-four words text related to the chunk content that the user will be able to review. You can add the sources in any place of your response. Add as many as needed. You must cite the source using the href, the SOME_RELATED_CONECTOR is generated by you."

    return complete_context, sources
