import os
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

def search_brave(query):
    api_key = os.getenv('BRAVE_API_KEY')

    print("Searching the web ")
    if not api_key:
        raise ValueError("API key not found. Please set BRAVE_API_KEY in your .env file.")
    
    url = f'https://api.search.brave.com/res/v1/web/search?q={query}'
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': api_key
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        search_results = response.json()
        urls = [result['url'] for result in search_results.get('web', {}).get('results', [])]
        
        last_4_urls = urls[-4:]
        
        url_contents = []
        for url in last_4_urls:
            try:
                page_response = requests.get(url)
                if page_response.status_code == 200:
                    soup = BeautifulSoup(page_response.content, 'html.parser')
                    content = soup.get_text()
                    url_contents.append(f"URL: {url}\nCONTENT: {content}\n---")
                else:
                    url_contents.append(f"URL: {url}\nCONTENT: Error: {page_response.status_code}\n---")
            except Exception as e:
                url_contents.append(f"URL: {url}\nCONTENT: Error: {str(e)}\n---")
        
        # Join all contents and cut to 3000 characters
        result = "\n".join(url_contents)[:3000]
        
        return result
    else:
        return f'Error: {response.status_code}'