import os
import requests
import json
from requests.utils import quote
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from ..utils.openai_functions import create_structured_completion
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        ...,
        description="A list of queries to execute web search and pass to the AI as context",
    )
    country_code: str = Field(
        ...,
        description="The country code to search the web. If you are not sure, use ALL.",
    )

    


# Cargar las variables de entorno desde el archivo .env
load_dotenv()

VALID_COUNTRIES = [
    "ALL",
    "AR",
    "AU",
    "AT",
    "BE",
    "BR",
    "CA",
    "CL",
    "DK",
    "FI",
    "FR",
    "DE",
    "HK",
    "IN",
    "ID",
    "IT",
    "JP",
    "KR",
    "MY",
    "MX",
    "NL",
    "NZ",
    "NO",
    "PH",
    "RU",
    "SA",
    "ZA",
    "ES",
    "SE",
    "CH",
    "TW",
    "TR",
    "GB",
    "US",
]


def search_brave(user_message, context):
    _system = f"""
You are an experienced web scrapper. Your task is to convert a context made of messages between a user and an AI to search queries.

Provide a list of queries from 1 to 3 queries to search the web. You must think which are the most relevant queries to search the web.


REGIONS LIST:
{json.dumps(VALID_COUNTRIES)}
"""

    api_key = os.getenv("BRAVE_API_KEY")

    if not api_key:
        raise ValueError(
            "API key not found. Please set BRAVE_API_KEY in your .env file."
        )

    queries = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=_system,
        user_prompt=context + "\n\n LAST USER MESSAGE: \n" + user_message,
        response_format=SearchQueries,
    )

    web_results = []

    with ThreadPoolExecutor() as executor:
        future_to_query = {
            executor.submit(search_brave_query, q, "US", api_key): q
            for q in queries.queries
        }

        for future in as_completed(future_to_query):
            q = future_to_query[future]
            try:
                url_contents = future.result()
                web_results.extend(url_contents)
            except Exception as e:
                print(f"Error processing query '{q}': {str(e)}")

    # Join all contents and cut to 3000 characters
    return web_results if web_results else "No results found."


def fetch_url_content(url):
    try:
        page_response = requests.get(url)
        if page_response.status_code == 200:
            soup = BeautifulSoup(page_response.content, "html.parser")

            # Collect all relevant tags
            content = []

            # Find all desired tags
            for tag in [
                "h1",
                "h2",
                "p",
                "blockquote",
                "pre",
                "span",
                "li",
                "strong",
                "main",
            ]:
                elements = soup.find_all(tag)
                for element in elements:
                    content.append(element.get_text(strip=True))  # Strip whitespace

            # Join the collected content into a single string
            combined_content = "\n\n".join(
                content
            )  # Add double new lines for better readability

            return {
                "url": url,
                "content": combined_content[:5000],  # Limit to 5000 characters
            }
        else:
            print(f"Failed to fetch {url}: Status code {page_response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching URL {url}: {str(e)}")
        return None


def search_brave_query(q, country, api_key=os.getenv("BRAVE_API_KEY")):
    q = quote(q)
    if country not in VALID_COUNTRIES:
        country = "ALL"
    url = f"https://api.search.brave.com/res/v1/web/search?q={q}&country={country}"

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

        first_three_urls = urls[:3]

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {
                executor.submit(fetch_url_content, url): url for url in first_three_urls
            }
            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    url_contents.append(result)

    return url_contents


def query_brave(q: str, api_key=os.getenv("BRAVE_API_KEY")):
    q = quote(q)
    url = f"https://api.search.brave.com/res/v1/web/search?q={q}"

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    response = requests.get(url, headers=headers)
    return response.json()
