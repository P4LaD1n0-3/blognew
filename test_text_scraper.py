import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

def scrape_web_text(query, num_results=3):
    """Scrape DuckDuckGo HTML search for real text context."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        results = []
        for a in soup.find_all('a', class_='result__snippet'):
            text = a.get_text(strip=True)
            if text:
                results.append(text)
                if len(results) >= num_results:
                    break
        return "\n\n".join(results)
    except Exception as e:
        return f"Erro na extração: {e}"

print("CONTEXTO EXTRAÍDO DA WEB:")
print(scrape_web_text("Origem 4a temporada spoilers MGM"))
