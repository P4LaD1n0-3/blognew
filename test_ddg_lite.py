import requests
import re
import urllib.parse

def scrape_ddg_lite(query):
    url = "https://lite.duckduckgo.com/lite/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    data = {"q": query}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        
        # Extract snippets (the text below the title)
        snippets = re.findall(r'<td class=\'result-snippet\'>\s*(.*?)\s*</td>', resp.text, re.IGNORECASE | re.DOTALL)
        
        # Clean html tags
        clean_snippets = []
        for s in snippets:
            clean_s = re.sub(r'<[^>]+>', '', s).strip()
            clean_s = clean_s.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
            if clean_s:
                clean_snippets.append(clean_s)
                
        return clean_snippets[:5]
    except Exception as e:
        print("Erro DDG Lite:", e)
        return []

query = "Origem 4a temporada spoilers MGM"
print(f"Buscando no DuckDuckGo Lite: {query}")
snippets = scrape_ddg_lite(query)

print("\nFatos Encontrados (Contexto para a IA):")
for i, s in enumerate(snippets):
    print(f"{i+1}. {s}")

