import glob
import html
import os
import re
from datetime import datetime

ROOT = r"C:/AI编程/AI赚钱新闻收集"
SRC = os.path.join(ROOT, "ai_reports")
DETAILS = os.path.join(ROOT, "html", "details")
HTML_OUT = os.path.join(ROOT, "5条精选AI新闻.html")
WEB_OUT = os.path.join(ROOT, "html", "5条精选AI新闻.html")

SOURCE_ZH = {
    "The Motley Fool": ("莫特利·富尔", "motley"),
    "The Economic Times": ("印度经济时报", "economic"),
    "Economic Times": ("印度经济时报", "economic"),
    "Economictimes.com": ("印度经济时报", "economic"),
    "Forbes": ("福布斯", "forbes"),
    "AOL.com": ("美国在线", "aol"),
    "AOL": ("美国在线", "aol"),
    "entrepreneur.com": ("企业家杂志", "entrepreneur"),
    "Entrepreneur": ("企业家杂志", "entrepreneur"),
    "Inc.com": ("Inc.杂志", "entrepreneur"),
    "GOBankingRates": ("银行利率指南", "economic"),
    "SiliconANGLE News": ("硅角新闻", "economic"),
    "Tech Build Africa": ("非洲科技建设网", "economic"),
}

PRIORITY_PATTERNS = [
    (r"16岁|150K|\$150", 12),
    (r"如何利用人工智能赚钱|如何用人工智能赚钱", 12),
    (r"在线赚钱|赚钱的新方式|赚钱方法", 11),
    (r"人工智能.*副业|AI.*副业|副业", 8),
    (r"ChatGPT|Claude", 7),
    (r"数字产品", 7),
    (r"被动收入", 6),
    (r"零工", 5),
    (r"自动化", 4),
]


def parse_latest_report():
    files = sorted(
        glob.glob(os.path.join(SRC, "*.md")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not files:
        return None, []

    with open(files[0], encoding="utf-8-sig") as report:
        content = report.read()

    date_match = re.search(r"^# AI赚钱日报\s+(\d{4}-\d{2}-\d{2})", content, re.M)
    today = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
    lines = content.splitlines()
    articles = []
    index = 0
    while index < len(lines):
        match = re.match(r"- \[(.*?)\]\(([^)]+)\) \| (\w+)", lines[index])
        if not match:
            index += 1
            continue

        title = match.group(1)
        source_name = ""
        cursor = index + 1
        while cursor < len(lines):
            comment = lines[cursor].strip()
            if comment.startswith("<!-- SRC:"):
                source_name = comment[8:-3].strip().lstrip(":")
                break
            if comment.startswith("- [") or comment.startswith("# ") or comment.startswith("---"):
                break
            cursor += 1

        articles.append({
            "detail_index": len(articles),
            "title": title,
            "url": match.group(2),
            "source_name": source_name,
        })
        index = cursor

    return today, articles


def detail_summary(detail_index):
    detail_path = os.path.join(DETAILS, f"detail_{detail_index:03d}.html")
    if not os.path.exists(detail_path):
        return ""

    with open(detail_path, encoding="utf-8") as detail_file:
        raw = detail_file.read()
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", raw, flags=re.I | re.S)
    cleaned = []
    for paragraph in paragraphs:
        text = re.sub(r"<[^>]+>", "", paragraph)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text.startswith("该来源") or text.startswith("原文来源"):
            continue
        if text == "返回":
            continue
        cleaned.append(text)

    summary = "".join(cleaned)
    if len(summary) > 225:
        cut = summary.rfind("。", 150, 225)
        if cut > 0:
            summary = summary[: cut + 1]
        else:
            summary = summary[:210] + "……"
    return summary.strip()


def detail_title(detail_index):
    detail_path = os.path.join(DETAILS, f"detail_{detail_index:03d}.html")
    if not os.path.exists(detail_path):
        return ""
    with open(detail_path, encoding="utf-8") as detail_file:
        raw = detail_file.read()
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, flags=re.I | re.S)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", "", match.group(1))
    return html.unescape(title).strip()


def select_articles(articles):
    scored = []
    for index, article in enumerate(articles):
        title = article["title"]
        score = sum(weight for pattern, weight in PRIORITY_PATTERNS if re.search(pattern, title, re.I))
        scored.append((score, -index, article))
    scored.sort(reverse=True)
    return [item[2] for item in scored[:5]]


def build_card(article):
    source_name, source_class = SOURCE_ZH.get(
        article["source_name"],
        (article["source_name"] or "新闻机构", "motley"),
    )
    summary = detail_summary(article["detail_index"])
    if not summary:
        summary = article["title"]
    title = detail_title(article["detail_index"]) or article["title"]
    return (
        '<article class="news-card">\n'
        f'<div class="source-row"><span class="source {source_class}">{source_name}</span></div>\n'
        f'<h2>{html.escape(title)}</h2>\n'
        f'<p class="summary">{html.escape(summary)}</p>\n'
        "</article>\n"
    )


def render_page(today, articles):
    cards = "\n".join(build_card(article) for article in articles)
    css = """
    <style>
      *{margin:0;padding:0;box-sizing:border-box}
      body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f6f7f9;color:#1f2937;line-height:1.75;padding:16px 14px 42px}
      .page{max-width:640px;margin:0 auto}
      .header{padding:24px 8px 20px}
      .header h1{font-size:28px;line-height:1.35;font-weight:800;color:#111827}
      .header p{margin-top:8px;color:#6b7280;font-size:14px}
      .news-card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:18px 16px;margin-bottom:14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
      .source-row{display:flex;align-items:center;gap:8px;margin-bottom:9px}
      .source{display:inline-flex;min-height:24px;padding:2px 9px;border-radius:4px;font-size:12px;font-weight:700;color:#fff}
      .source.motley{background:#2563eb}
      .source.economic{background:#059669}
      .source.forbes{background:#9333ea}
      .source.aol{background:#d97706}
      .source.entrepreneur{background:#dc2626}
      .news-card h2{font-size:20px;line-height:1.5;color:#111827;font-weight:750}
      .summary{margin-top:10px;font-size:16px;color:#374151}
      @media(max-width:480px){.header h1{font-size:25px}.news-card{padding:16px 14px}.news-card h2{font-size:18px}.summary{font-size:15px}}
    </style>
    """
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>5条精选AI新闻</title>\n"
        + css
        + "</head>\n<body>\n<main class=\"page\">\n"
        '<header class="header">\n'
        "<h1>5条精选AI新闻</h1>\n"
        f"<p>{today} · 从今天的AI赚钱日报中挑选</p>\n"
        "</header>\n"
        + cards
        + "</main>\n</body>\n</html>\n"
    )


def main():
    today, articles = parse_latest_report()
    if not articles:
        print("No report articles found.")
        return
    selected = select_articles(articles)
    page = render_page(today, selected)
    for path in (HTML_OUT, WEB_OUT):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as output:
            output.write(page)
    print(
        "Saved 5 selected AI news: "
        + ", ".join(article["title"] for article in selected)
    )


if __name__ == "__main__":
    main()
