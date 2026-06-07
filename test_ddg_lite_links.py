import requests
import re

def scrape_ddg_lite_links(query):
    url = "https://lite.duckduckgo.com/lite/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    data = {"q": query}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        
        # Extract links
        matches = re.findall(r'<a rel="nofollow" href="([^"]+)" class="result-url"', resp.text, re.IGNORECASE)
        
        links = []
        for m in matches:
            if m.startswith('http'):
                links.append(m)
                
        return links[:3]
    except Exception as e:
        print("Erro DDG Lite:", e)
        return []

def get_og_image(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        og_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', resp.text, re.IGNORECASE)
        return og_match.group(1) if og_match else None
    except:
        return None

query = "Origem 4a temporada spoilers MGM"
print(f"Buscando links: {query}")
links = scrape_ddg_lite_links(query)

for link in links:
    print(f"\nLink: {link}")
    img = get_og_image(link)
    print(f"OG Image: {img}")

