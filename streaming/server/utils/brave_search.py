import os
import time
import asyncio
import requests
import json
from requests.utils import quote
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from ..utils.openai_functions import create_structured_completion
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..logger import get_custom_logger

logger = get_custom_logger("brave_search")


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        ...,
        description="A list of queries to execute web search and pass to the AI as context. This must be in the best language possible depending of the user requirements",
    )
    country_code: str = Field(
        ...,
        description="The country code to search the web. If you are not sure, use ALL.",
    )


class SelectUrls(BaseModel):
    selected: list[str] = Field(
        ...,
        description="The selected URLs to query. Up to 3 urls",
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

    # print(web_results, "WEB RESULTS")
    return web_results if web_results else "No results found."


def fetch_url_content(url):
    try:
        page_response = requests.get(url)
        if page_response.status_code == 200:
            soup = BeautifulSoup(page_response.content, "html.parser")

            content = []
            for tag in [
                "article",
                "h1",
                "h2",
                "h3",
                "h4",
                "p",
                "span",
                "blockquote",
                "pre",
                "code",
                "strong",
                "ul",
                "ol",
                "li",
            ]:
                elements = soup.find_all(tag)
                for element in elements:
                    content.append(element.get_text(strip=True))  # Strip whitespace

            combined_content = "\n\n".join(content)

            logger.info(f"Fetched content from {combined_content[:50]}")
            return {"url": url, "content": combined_content}
        else:
            raise Exception(
                f"Failed to fetch {url}: Status code {page_response.status_code}"
            )

    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
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
    print(response, "RESPONSE")
    url_contents = []

    if response.status_code == 200:
        search_results = response.json()
        print(search_results, "SEARCH RESULTS")
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


def new_search_brave(user_message, context):
    _system = f"""
You are an experienced web scrapper. Your task is to convert a context made of messages between a user and an AI to search queries.

Provide a list of queries from 1 to 2 queries to search the web. You must think which are the most relevant queries to search the web. THe number of provided queries depending of the difficulty of the user requirement. If is posible to do it with a single query, return only one query.

REGIONS LIST:
{json.dumps(VALID_COUNTRIES)}

TODAY:
If you need to know it, today is: {time.strftime("%Y-%m-%d")} at {time.strftime("%H:%M:%S")}
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
    clickables = []

    for q in queries.queries:
        search_results = get_brave_results(q, "US", api_key)
        # web_results.append(res)
        if search_results:
            urls = [
                result["url"]
                for result in search_results.get("web", {}).get("results", [])
            ]
            _system_select = f"""
Please select the urls that you want to explore. From the provided list. This urls will be used to generate a response for the user.

The query that produces these urls is: {q}

URLS you can select from:

{json.dumps(urls)}

PLease select the most relevant urls for the query.
    """

            selected_urls = create_structured_completion(
                model="gpt-4o-mini",
                system_prompt=_system_select,
                user_prompt="Please select the urls for me",
                response_format=SelectUrls,
            )
            clickables.extend(selected_urls.selected)

    results = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_url = {
            executor.submit(fetch_url_content, url): url for url in clickables
        }
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                results.append(result)

    return results


def get_brave_results(q, country, api_key=os.getenv("BRAVE_API_KEY")):
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

    if response.status_code == 200:
        return response.json()
    else:
        return None
