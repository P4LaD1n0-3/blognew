import requests
import re
import urllib.parse

def google_search_snippets(query, num=5):
    """Scrape Google Search results (snippets + titles)."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&hl=pt-BR&num={num}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    
    results = []
    
    # Extract snippets from Google's HTML
    # Google wraps snippets in <span> tags inside divs
    # Pattern for titles: <h3 class="...">title</h3>
    titles = re.findall(r'<h3[^>]*>(.*?)</h3>', resp.text)
    
    # Pattern for snippets - Google puts them in specific divs
    # Look for text blocks that are substantial
    snippets = re.findall(r'<span[^>]*>((?:(?!</span>).){50,500})</span>', resp.text)
    
    # Clean HTML tags from results
    def clean(text):
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()
    
    clean_titles = [clean(t) for t in titles if len(clean(t)) > 10]
    clean_snippets = [clean(s) for s in snippets if len(clean(s)) > 40 and 'function' not in s and 'var ' not in s and '{' not in s]
    
    print(f"Títulos encontrados: {len(clean_titles)}")
    for t in clean_titles[:5]:
        print(f"  📌 {t}")
    
    print(f"\nSnippets encontrados: {len(clean_snippets)}")
    for s in clean_snippets[:8]:
        print(f"  📝 {s[:120]}...")
    
    return clean_titles[:5], clean_snippets[:8]

# Test
print("=" * 60)
print("BUSCA: 'Série From temporada 4 novidades 2025'")
print("=" * 60)
google_search_snippets("Série From temporada 4 novidades 2025")

print("\n" + "=" * 60)
print("BUSCA: 'iPhone 16 Pro Max análise completa'")
print("=" * 60)
google_search_snippets("iPhone 16 Pro Max análise completa")

print("\n" + "=" * 60)
print("BUSCA: 'Inteligência Artificial impacto mercado trabalho 2025'")
print("=" * 60)
google_search_snippets("Inteligência Artificial impacto mercado trabalho 2025")
