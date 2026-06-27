import urllib.request, json, sys

url = "http://127.0.0.1:8000/api/generate_outline"
payload = json.dumps({"prompt": "人工智能发展趋势", "pages": 8, "style": "business"}).encode("utf-8")

req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read().decode("utf-8")
        print("status:", r.status)
        data = json.loads(body)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
except Exception as e:
    print("ERROR:", e)
    sys.exit(1)
