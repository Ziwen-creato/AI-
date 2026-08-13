"""AI Money News - via NewsAPI.org"""
import urllib.request, urllib.parse, json, os, time, re
import xml.etree.ElementTree as ET
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "3274f78b206141e298f347d503f07e24"
OUT = r"C:\AI编程\AI赚钱新闻收集\ai_reports"
os.makedirs(OUT, exist_ok=True)
MAX_ARTICLES = 20
EXCLUDE_INDUSTRY_DOMAINS = (
    "biztoc.com,slashdot.org,digitimes.com,techspot.com,gizmodo.com,"
    "9to5mac.com,pymnts.com,searchenginejournal.com,whatsnewinpublishing.com,"
    "socialmediatoday.com,finance.yahoo.com,marketbeat.com,seekingalpha.com,"
    "fool.com,stocktwits.com,benzinga.com,cryptobriefing.com"
)
EXCLUDED_SOURCES = {
    "Mshale",
    "Fortune",
    "finance.biggo.com",
    "PYMNTS.com",
    "Creative Boom",
    "Sportskeeda",
    "TechFinancials",
    "The Business Times",
    "TradingView",
    "eu.36kr.com",
    "Finimize",
    "Business Insider",
    "Yahoo Finance",
    "Yahoo Finance Singapore",
    "South China Morning Post",
    "The Portugal News",
    "Professional Wealth Management",
    "Passive Income MD",
    "financialexpress.com",
    "Popular Science",
    "Big News Network.com",
    "Big News Network",
}

AD_NOISE_PATTERNS = [
    r"sponsored content", r"with this \$\d+", r"ranking best",
    r"best .* generators", r"this online course",
]
AI_KEYWORDS = [
    "artificial intelligence", "ChatGPT", "OpenAI", "GPT", "LLM",
    "machine learning", "deep learning", "Gemini", "Copilot", "Claude",
]
MONEY_MAKING_KEYWORDS = [
    "make money", "making money", "earn money", "earning money",
    "make extra money", "earn extra money", "money-making", "moneymaking",
    "side hustle", "side hustles", "side income", "passive income",
    "income stream", "income streams", "online income", "extra income",
    "remote income", "monetize your",
    "business idea", "business ideas", "revenue stream", "online business",
    "digital products", "affiliate marketing", "freelance income",
    "freelancing income", "gig economy", "gig work", "work from home",
    "paying customers", "profit from", "profitable", "profitability",
    "online course", "dropshipping", "print-on-demand", "content monetization",
    "ebook", "side business", "home business",
    "start a business",
]

INDUSTRY_NOISE_TERMS = [
    "free cash flow", "capex", "capital spending", "capital expenditure",
    "quarterly results", "earnings report", "stock market", "stock price",
    "stock falls", "stock soars", "shares", "valuation", "funding",
    "acquisition", "initial public offering", "ipo", "universal high income",
    "ubi", "pricing", "revenue guidance", "market cap", "financial results",
    "investor", "shareholders", "cloud service providers", "csp",
    "fee income", "publisher", "publishers", "trade", "ceo", "bank",
    "make money disappear", "side business surges", "lost her side business",
    "lost his side hustle", "funding platform", "monetization pressure",
    "ruined it for us", "ai trading", "making money in the first place",
    "profit from the ai boom", "gaap", "earnings", "financing",
    "cost-saving business", "revenue stream",
    "automated trading", "moneysimpler", "wealth management",
    "wealth managers", "wall street", "business story tonight",
    "business story", "cost center to profit center", "customer experience",
    "youtube uses to make money", "dangerous lie", "gen z careers",
    "creator economy", "market factors", "kimi k3", "moonshot",
    "wants to make money", "data centers", "microsoft",
    "investments start paying off",
    "who really profits", "who profits from the ai boom", "capital behind",
    "big tech", "m7", "semiconductor", "semiconductors", "cloud",
    "ai profitability", "cash generation", "ai funds",
]


def contains_word(text, keyword):
    return re.search(
        r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])",
        text,
    )


def is_relevant_article(title, description):
    title = (title or "").strip()
    title_lower = title.lower()
    has_ai = re.search(r"\bAI\b", title_lower, re.I) or any(
        keyword.lower() in title_lower for keyword in AI_KEYWORDS
    )
    has_money = any(
        contains_word(title_lower, keyword) for keyword in MONEY_MAKING_KEYWORDS
    )
    has_industry_noise = any(term in title_lower for term in INDUSTRY_NOISE_TERMS)
    return has_ai and has_money and not has_industry_noise


def title_fingerprint(title):
    title = (title or "").lower()
    title = re.split(r"\s+\|\s+|\s+-\s+", title, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title)

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


def parse_rss_date(value):
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.strftime("%Y-%m-%dT%H:%M:%S") if parsed else ""
    except Exception:
        return ""


def clean_news_title(title, source_name):
    title = (title or "").strip()
    source_name = (source_name or "").strip()
    if source_name and title.lower().endswith(" - " + source_name.lower()):
        title = title[: -(len(source_name) + 3)].strip()
    return title


def fetch_google_news(query):
    search_query = query + " when:30d"
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(search_query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
    root = ET.fromstring(raw)
    results = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source_el = item.find("source")
        source_name = source_el.text.strip() if source_el is not None and source_el.text else ""
        title = clean_news_title(title, source_name)
        pubdate = parse_rss_date(item.findtext("pubDate") or "")
        results.append({
            "title": title,
            "url": link,
            "source_name": source_name,
            "description": "",
            "content": "",
            "image_url": "",
            "published_at": pubdate,
        })
    return results


def add_candidate(all_articles, seen_urls, seen_titles, source_counts, article):
    art_url = (article.get("url") or "").strip()
    raw_title = (article.get("title") or "").strip()
    source_name = article.get("source_name", "")
    title = clean_news_title(raw_title, source_name)
    if source_name in EXCLUDED_SOURCES:
        return
    title_lower = title.lower()
    if any(re.search(pattern, title_lower) for pattern in AD_NOISE_PATTERNS):
        return
    if source_counts.get(source_name, 0) >= 3:
        return
    if not art_url or art_url in seen_urls:
        return
    if not is_relevant_article(title, article.get("description", "")):
        return
    fingerprint = title_fingerprint(title)
    if not fingerprint or fingerprint in seen_titles:
        return
    seen_urls.add(art_url)
    seen_titles.add(fingerprint)
    source_counts[source_name] = source_counts.get(source_name, 0) + 1
    all_articles.append({
        "title": title,
        "url": art_url,
        "source_name": source_name,
        "description": article.get("description", ""),
        "content": article.get("content", ""),
        "image_url": article.get("image_url", ""),
        "published_at": article.get("published_at", ""),
    })

def main():
    print(f">>> Fetching AI money news via Google News RSS (max {MAX_ARTICLES})...")
    google_queries = [
        '"make money with AI"',
        '"earn money with AI"',
        '"AI side hustle"',
        '"ChatGPT side hustle"',
        '"monetize AI"',
        '"AI business idea"',
        '"AI freelancer"',
        '"AI affiliate marketing"',
        '"AI digital products"',
        '"sell AI services"',
        '"AI business opportunity"',
        '"AI money making"',
        '"AI digital product"',
        "AI passive income",
        "AI online income",
        "AI side business",
        "AI income stream",
        "AI make money online",
        "AI business ideas",
        "AI freelancing income",
        "AI digital products business",
        "AI content monetization",
        "AI home business",
        "AI side job",
        "AI money making",
        "AI earn cash",
        "AI online business",
        "AI profit from home",
        "ChatGPT make money",
        "OpenAI side hustle",
        "AI extra money",
        "AI business income",
        "AI money",
        "AI income",
        "AI monetization",
        "AI side hustle ideas",
        "AI passive income ideas",
        "AI affiliate marketing for beginners",
        "AI prompt packs",
        "AI printables on Etsy",
        "AI Notion templates",
        "AI app publishing",
        "AI YouTube monetization",
        "AI ebook publishing",
        "AI sell prompts",
        "ChatGPT passive income",
        "AI freelancing jobs",
        "AI online course creation",
        "AI digital products income",
        "AI side hustle business",
        "AI passive income opportunities",
        "AI work from home side hustle",
        "AI content writing income",
        "AI affiliate programs",
        "AI print on demand income",
        "AI digital marketing income",
        "AI creator monetization",
        "AI service business income",
        "AI gig economy",
        "AI online earning",
        "AI make money from home",
    ]
    newsapi_queries = [
        '"make money with AI" OR "earn money with AI" OR "AI side hustle" OR "AI passive income"',
        'AI AND ("affiliate marketing" OR "digital products" OR "freelance income" OR "side business")',
        'ChatGPT AND ("make money" OR "side hustle" OR "passive income" OR monetize)',
    ]
    all_articles = []
    seen_urls = set()
    seen_titles = set()
    source_counts = {}

    for q in google_queries:
        if len(all_articles) >= MAX_ARTICLES * 8:
            break
        try:
            articles = fetch_google_news(q)
            print(f"  Google RSS: {q} ({len(articles)} results)")
            for article in articles:
                add_candidate(all_articles, seen_urls, seen_titles, source_counts, article)
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(0.3)

    if len(all_articles) < MAX_ARTICLES:
        print("  Google News RSS did not reach 20; trying NewsAPI fallback...")
        for q in newsapi_queries:
            if len(all_articles) >= MAX_ARTICLES:
                break
            encoded_q = urllib.parse.quote(q)
            url = (
                f"https://newsapi.org/v2/everything?q={encoded_q}&language=en"
                f"&sortBy=relevancy&pageSize=100"
                f"&excludeDomains={EXCLUDE_INDUSTRY_DOMAINS}&apiKey={API_KEY}"
            )
            try:
                data = fetch_json(url)
                if data.get("status") != "ok":
                    print(f"    API error: {data.get('message', 'unknown')}")
                    continue
                print(f"  NewsAPI: {q[:60]} ({len(data.get('articles', []))} results)")
                for a in data.get("articles", []):
                    add_candidate(all_articles, seen_urls, seen_titles, source_counts, {
                        "title": a.get("title", ""),
                        "url": a.get("url", ""),
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
    all_articles = list(unique.values())
    # Preserve the relevance order returned by Google News queries.
    all_articles = all_articles[:MAX_ARTICLES]
    print(f"  Total after dedup + AI money-making filter: {len(all_articles)}")

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
    content += "\n\n---\n*Google News RSS + NewsAPI translate*"

    fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    fpath = os.path.join(OUT, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f">>> Saved: {fpath}")

if __name__ == "__main__":
    main()
