import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

def scrape_links_from_ddg(query):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        links = []
        for a in soup.find_all('a', class_='result__url'):
            href = a.get('href')
            if href and 'uddg=' in href:
                # Decode DuckDuckGo redirect
                actual_url = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
                if actual_url.startswith('http') and 'youtube' not in actual_url:
                    links.append(actual_url)
        return links[:3]
    except Exception as e:
        print("Erro DDG:", e)
        return []

def scrape_article_content(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 1. Get main image (og:image)
        og_image = soup.find('meta', property='og:image')
        main_image = og_image['content'] if og_image and og_image.get('content') else None
        
        # 2. Get text
        paragraphs = []
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 50:
                paragraphs.append(text)
                
        return {
            'url': url,
            'image': main_image,
            'text': "\n".join(paragraphs[:5])
        }
    except Exception as e:
        print(f"Erro ao extrair {url}:", e)
        return None

query = "Origem 4a temporada spoilers"
print(f"Buscando: {query}")
links = scrape_links_from_ddg(query)

print("\nResultados do RAG:")
for link in links:
    print(f"\nExtraindo: {link}")
    data = scrape_article_content(link)
    if data:
        print(f"IMAGEM CAPTURADA: {data['image']}")
        print(f"TEXTO CAPTURADO (amostra):\n{data['text'][:200]}...")

