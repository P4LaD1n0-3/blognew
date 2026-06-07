import sys
import json
import base64
import os
import urllib.request
import urllib.error

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("No API key")
    sys.exit(1)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

images = [
    "/Users/wesleyrolimsimoes/.gemini/antigravity-ide/brain/77e1c71a-8183-4b67-afb2-02e748685dfe/media__1780794212392.png"
]

contents = [{"text": "Describe exactly what looks visually bad or unpolished in this UI screenshot. Is the title aligned poorly? Are the inputs looking like strange boxes? Is there too much padding? Describe the layout of a single row in detail."}]
for img in images:
    if os.path.exists(img):
        b64 = encode_image(img)
        contents.append({"inline_data": {"mime_type": "image/png", "data": b64}})
    else:
        print(f"Image not found: {img}")

data = {
    "contents": [{"parts": contents}],
    "generationConfig": {"temperature": 0.0}
}

req = urllib.request.Request(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(result['candidates'][0]['content']['parts'][0]['text'])
except Exception as e:
    print("Error:", e)
