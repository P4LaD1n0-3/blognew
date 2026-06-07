import requests
import urllib.parse
import re

def scrape_google_text(query):
    """Scrape Google Search HTML."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        # Emulating what we did for DDG, but Google is messy.
        # Let's try to find snippet divs.
        matches = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', resp.text)
        
        results = []
        for match in matches:
            clean_text = re.sub(r'<[^>]+>', '', match).strip()
            if clean_text and len(clean_text) > 30 and clean_text not in results:
                results.append(clean_text)
                
        return "\n\n".join(results[:5])
    except Exception as e:
        return f"Erro na extração: {e}"

print("CONTEXTO GOOGLE:")
print(scrape_google_text("Origem 4a temporada spoilers MGM"))
