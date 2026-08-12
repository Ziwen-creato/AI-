"""AI Money News - via NewsAPI.org"""
import urllib.request, urllib.parse, json, os, time, re
from datetime import datetime

API_KEY = "3274f78b206141e298f347d503f07e24"
OUT = r"C:\AI编程\AI赚钱新闻收集\ai_reports"
os.makedirs(OUT, exist_ok=True)
MAX_ARTICLES = 5

def fetch_json(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
            return json.loads(raw)
        except Exception as e:
            if attempt == 2: raise e
            time.sleep(2)

def translate(text):
    if not text or any(ord(ch) > 127 for ch in text):
        return text
    for attempt in range(2):
        try:
            q = urllib.parse.quote(text[:500])
            url = f"https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl=zh-CN&dt=t&q={q}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
            if raw and len(raw) > 10:
                data = json.loads(raw)
                result = "".join(blk[0] for blk in data[0] if blk and blk[0])
                if result and result != text:
                    return result
        except:
            pass
        time.sleep(3)
    return text

def main():
    print(f">>> Fetching AI money news via NewsAPI (max {MAX_ARTICLES})...")
    # Use exact phrase search + AND for relevance
    queries = [
        '(AI OR "artificial intelligence") AND (money OR monetize OR revenue OR profit OR earn OR income)',
        '(ChatGPT OR OpenAI) AND (monetize OR money OR revenue OR ads)',
        '"AI startup" AND (funding OR revenue OR profit)',
        '"AI agent" AND (business OR money OR revenue)',
    ]
    all_articles = []
    seen_urls = set()

    for q in queries:
        if len(all_articles) >= MAX_ARTICLES * 2:
            break
        encoded_q = urllib.parse.quote(q)
        url = f"https://newsapi.org/v2/everything?q={encoded_q}&language=en&sortBy=publishedAt&pageSize=5&apiKey={API_KEY}"
        print(f"  Search: {q[:60]}...")
        try:
            data = fetch_json(url)
            if data.get("status") != "ok":
                print(f"    API error: {data.get('message', 'unknown')}")
                continue
            articles = data.get("articles", [])
            print(f"    Got {len(articles)} articles")
            for a in articles:
                art_url = a.get("url", "")
                if art_url in seen_urls or not art_url:
                    continue
                title = a.get("title", "")
                # Filter: must contain AI-related keywords in title
                ai_keywords = ['AI', 'artificial intelligence', 'ChatGPT', 'OpenAI', 'GPT', 'LLM',
                              'machine learning', 'deep learning', 'Gemini', 'Copilot', 'Claude']
                if not any(kw.lower() in title.lower() for kw in ai_keywords):
                    continue
                seen_urls.add(art_url)
                all_articles.append({
                    "title": title,
                    "url": art_url,
                    "source_name": (a.get("source") or {}).get("name", ""),
                    "description": a.get("description", ""),
                    "content": a.get("content", ""),
                    "image_url": a.get("urlToImage", ""),
                    "published_at": a.get("publishedAt", ""),
                })
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(0.3)

    unique = {a["url"]: a for a in all_articles}
    all_articles = list(unique.values())[:MAX_ARTICLES]
    print(f"  Total after dedup + AI filter: {len(all_articles)}")

    if not all_articles:
        print("  WARNING: No articles found! Trying broader search...")
        # Fallback: simpler query
        url = f"https://newsapi.org/v2/everything?q=AI+money&language=en&sortBy=publishedAt&pageSize=5&apiKey={API_KEY}"
        try:
            data = fetch_json(url)
            for a in data.get("articles", []):
                all_articles.append({
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "source_name": (a.get("source") or {}).get("name", ""),
                    "description": a.get("description", ""),
                    "content": a.get("content", ""),
                    "image_url": a.get("urlToImage", ""),
                    "published_at": a.get("publishedAt", ""),
                })
        except:
            pass

    ok = fail = 0
    for i, a in enumerate(all_articles):
        cn = translate(a["title"])
        a["cn_title"] = cn
        if cn != a["title"]: ok += 1
        else: fail += 1
        print(f"    [{i+1}/{len(all_articles)}] {cn[:60]}...")
        time.sleep(0.1)
    print(f"  Translation: OK {ok} FAIL {fail}")

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    for a in all_articles:
        cn_title = a.get("cn_title", a["title"])
        region = "US"
        pub = (a.get("published_at") or "")[:19]
        desc = (a.get("description") or "")[:200]
        lines.append(f"- [{cn_title}]({a['url']}) | {region} | {pub} | {desc}")
        if a.get("image_url"):
            lines.append(f"  <!-- IMG:{a['image_url']} -->")
        if a.get("content"):
            content_snippet = a["content"][:500].replace("\n", " ")
            lines.append(f"  <!-- CNT:{content_snippet} -->")
        if a.get("source_name"):
            lines.append(f"  <!-- SRC:{a['source_name']} -->")

    content = f"# AI赚钱日报 {today}\n\n共 {len(all_articles)} 条\n\n" + "\n".join(lines)
    content += "\n\n---\n*NewsAPI.org translate*"

    fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    fpath = os.path.join(OUT, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f">>> Saved: {fpath}")

if __name__ == "__main__":
    main()
