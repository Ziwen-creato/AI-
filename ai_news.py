"""AI Money News - Global + Translate"""
import urllib.request, urllib.parse, re, os, json, time
from datetime import datetime

OUT = r"C:\AI编程\AI赚钱新闻收集\ai_reports"
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_ARTICLES = 5  # 今日只取5条

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        except:
            time.sleep(2)
    return ""

def gnews(q):
    results = []
    for region, lang, ceid in [("UK", "en", "GB:en"), ("CN", "zh-Hans", "CN:zh-Hans"), ("US", "en", "US:en")]:
        if len(results) >= MAX_ARTICLES * 2:  # stop early if enough candidates
            break
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={lang}&gl={region}&ceid={ceid}"
        data = fetch(url)
        if not data: continue
        for m in re.finditer(r"<item>.*?</item>", data, re.DOTALL):
            t = re.search(r"<title>(.*?)</title>", m.group())
            l = re.search(r"<link>(.*?)</link>", m.group())
            if t:
                title = t.group(1).split(" - ")[0].strip()
                link = l.group(1) if l else ""
                pub = re.search(r"<pubDate>(.*?)</pubDate>", m.group())
                desc = re.search(r"<description>(.*?)</description>", m.group())
                pubdate = pub.group(1) if pub else ""
                raw_desc = desc.group(1) if desc else ""
                summary = re.sub(r"<[^>]+>", "", raw_desc.replace("&lt;","<").replace("&gt;",">").replace("&amp;","&"))[:150]
                results.append((title, link, region, pubdate, summary))
    return results

def translate(text):
    if not text or any(ord(ch) > 127 for ch in text):
        return text
    for attempt in range(2):
        try:
            q = urllib.parse.quote(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl=zh-CN&dt=t&q={q}"
            raw = fetch(url)
            if raw and len(raw) > 10:
                data = json.loads(raw)
                result = "".join(blk[0] for blk in data[0] if blk and blk[0])
                if result and result != text:
                    return result
        except:
            pass
        time.sleep(3)
    return f"[EN] {text}"

def main():
    print(f">>> Fetching AI money news (max {MAX_ARTICLES})...")
    items = []

    # 只用 AI 赚钱相关的精准关键词
    queries = [
        "AI+money+making",
        "AI+side+hustle",
        "ChatGPT+monetize",
        "AI+passive+income",
        "AI+赚钱",
    ]
    for q in queries:
        if len(items) >= MAX_ARTICLES * 3:
            break
        print(f"  Search: {q}")
        new_items = gnews(q)
        items.extend(new_items)
        time.sleep(0.3)

    print(f"  Total raw: {len(items)}")

    # 去重
    seen = set()
    unique = []
    for title, link, region, pubdate, summary in items:
        # 跳过太短/无意义的标题
        if not title or len(title) < 5:
            continue
        if title not in seen:
            seen.add(title)
            unique.append((title, link, region, pubdate, summary))

    print(f"  Dedup: {len(unique)}")

    # 只取前 N 条
    unique = unique[:MAX_ARTICLES]

    # 翻译
    ok = fail = 0
    translated = []
    for i, (title, link, region, pubdate, summary) in enumerate(unique):
        cn = translate(title)
        translated.append((cn, link, region, pubdate, summary))
        if cn.startswith("[EN]"):
            fail += 1
        else:
            ok += 1
        print(f"    [{i+1}/{len(unique)}] {cn[:60]}...")
        time.sleep(0.1)

    print(f"  Done! OK:{ok} FAIL:{fail}")

    # 生成报告
    lines = []
    for cn_title, link, region, pubdate, summary in translated:
        ts = pubdate[:25] if pubdate else ""
        ss = summary[:500] if summary else ""
        lines.append(f"- [{cn_title}]({link}) | {region} | {ts} | {ss}")

    today = datetime.now().strftime("%Y-%m-%d")
    content = f"# AI赚钱日报 {today}\n\n共 {len(lines)} 条 (CN:{ok} EN:{fail})\n\n" + "\n".join(lines)
    content += "\n\n---\n*Google News (US+CN+UK) translate*"

    fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    fpath = os.path.join(OUT, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f">>> Saved: {fpath}")

if __name__ == "__main__":
    main()
