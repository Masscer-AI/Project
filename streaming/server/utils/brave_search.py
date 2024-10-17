import os
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from ..utils.openai_functions import create_structured_completion
from pydantic import BaseModel, Field


class SearchQueries(BaseModel):
    queries: list[str] = Field(..., description="A list of queries to execute web search and pass to the AI as context")


# Cargar las variables de entorno desde el archivo .env
load_dotenv()


def search_brave(user_message, context):
    _system = """
You are are an experienced web searcher. You task is to convert a context made of messages between and user and an AI to search queries.

Provide three (3) search queries based in the context to enrich the AI response.

In the user message you will receive the last message and the previous context.
"""

    api_key = os.getenv("BRAVE_API_KEY")

    print("Searching the web ")
    if not api_key:
        raise ValueError(
            "API key not found. Please set BRAVE_API_KEY in your .env file."
        )


    queries = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=_system,
        user_prompt=context + "\n\n LAST USER MESSAGE: \n" +user_message,
        response_format=SearchQueries
    )

    print(queries, "AI SUGGESTED QUERIES")

    for q in queries:
        url = f"https://api.search.brave.com/res/v1/web/search?q={q}"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }

        response = requests.get(url, headers=headers)

        url_contents = []
        if response.status_code == 200:
            search_results = response.json()
            urls = [
                result["url"] for result in search_results.get("web", {}).get("results", [])
            ]

            last_4_urls = urls[-4:]

            for url in last_4_urls:
                try:
                    page_response = requests.get(url)
                    if page_response.status_code == 200:
                        soup = BeautifulSoup(page_response.content, "html.parser")
                        content = soup.get_text()
                        url_contents.append(f"---URL: {url}\nCONTENT: {content[:3000]}\n---")
                    else:
                        url_contents.append(
                            f"URL: {url}\nCONTENT: Error: {page_response.status_code}\n---"
                        )
                except Exception as e:
                    url_contents.append(f"URL: {url}\nCONTENT: Error: {str(e)}\n---")

        # Join all contents and cut to 3000 characters
        result = "\n".join(url_contents)

        return result
    else:
        return f"Error: {response.status_code}"
