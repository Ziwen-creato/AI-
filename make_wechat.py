import os, re, sys, json
from datetime import datetime, timezone, timedelta
from html import unescape
import urllib.parse, urllib.request

SRC = "C:/AI编程/AI赚钱新闻收集/ai_reports"
OUT = "C:/AI编程/AI赚钱新闻收集/html"
MAX_LIST_ITEMS = 20
PUBLIC_BASE_URL = os.environ.get(
    "AI_NEWS_BASE_URL", "https://ziwen-creato.github.io/AI-"
).rstrip("/")

SOURCE_ZH = {
    "Digitimes": "电子时报",
    "Nvidia.com": "英伟达",
    "Biztoc.com": "商业新闻聚合",
    "The Times of India": "印度时报",
    "Times of India": "印度时报",
    "Cointelegraph": "币电报",
    "SiliconANGLE News": "硅角新闻",
    "SiliconANGLE": "硅角新闻",
    "Crypto Briefing": "加密货币简报",
    "4sysops.com": "系统管理网",
    "The Verge": "边缘网",
    "Common Dreams": "共同梦想新闻",
    "Search Engine Journal": "搜索引擎杂志",
    "Business Insider": "商业内幕",
    "Economic Times": "经济时报",
    "TechCrunch": "科技博客",
    "The Register": "登记者科技新闻",
    "LiveMint": "印度商业新闻",
    "LiveMint.com": "印度商业新闻",
    "Mint": "印度商业新闻",
    "Financial Post": "金融邮报",
    "Atlassian": "阿特拉斯软件",
    "Slashdot": "科技新闻社区",
    "MarketWatch": "市场观察",
    "Theregister.com": "登记者科技新闻",
    "Slashdot.org": "科技新闻社区",
    "pymnts.com": "支付新闻",
    "Decrypt": "解密媒体",
    "The Next Web": "下一代网络",
    "CryptoSlate": "加密石板",
    "selfemployed.com": "自由职业者网站",
    "financialexpress.com": "金融快报",
    "appinventiv.com": "应用创新网",
    "eciks.org": "小企业趋势",
    "Ilmilog": "伊尔米日志",
    "AOL.com": "美国在线",
    "blog.google": "谷歌博客",
    "inc.com": "公司杂志",
    "entrepreneur.com": "企业家网",
    "The Manila Times": "马尼拉时报",
    "GOBankingRates": "银行业利率网",
    "Forbes": "福布斯",
    "The Motley Fool": "莫特利愚人",
    "Popular Science": "大众科学",
    "Big News Network.com": "大新闻网",
    "Nasscom": "印度软件与服务业协会",
    "Tech Build Africa": "非洲科技建设网",
    "Reuters": "路透社",
    "Bloomberg": "彭博社",
    "CNBC": "消费者新闻与商业频道",
    "BBC": "英国广播公司",
}

TITLE_ZH = {
    "Compal doubles AI server capacity, targets 30–40% revenue share by 2027": "仁宝将人工智能服务器产能翻倍，目标到2027年占据30%至40%的收入份额",
    "CoreWeave’s stock soars as earnings show major AI momentum - MarketWatch": "科瑞维夫股价因财报显示强劲人工智能增长势头而飙升",
    "Oracle’s stock falls amid resurfacing AI spending concerns": "人工智能支出担忧重燃，甲骨文股价下跌",
    "$12.4B-$13.2B": "124亿至132亿美元",
    "I gave ChatGPT my skills, time and income goal. Here’s the side hustle it picked": "我把自己的技能、时间和收入目标交给 ChatGPT，它为我选出了这个副业",
    "At Age 16, He Started a Side Hustle That Hit $150K in Under a Year. He Used Amazon and ChatGPT to ‘Rinse and Repeat’ Sales.": "16 岁时他开启副业，一年内收入 15 万美元；他使用亚马逊和 ChatGPT 重复销售",
    "I Asked ChatGPT How Retirees Can Generate $2K Monthly in Passive Income in 2026: Here’s What It Recommended": "我问 ChatGPT 退休人员如何在 2026 年每月获得 2000 美元被动收入，以下是它的建议",
    "5 ChatGPT Prompts To Turn Your Skills Into A $2,000 A Month Side Hustle": "5 个 ChatGPT 提示，把你的技能变成每月 2000 美元的副业",
    "Use ChatGPT To Launch A $1000/Month Back-To-School Side Hustle": "利用 ChatGPT 启动每月 1000 美元的返校季副业",
    "I Asked ChatGPT To Build a $500 a Month Passive Income Stream — Here's the Exact Plan It Gave Me": "我问 ChatGPT 如何每月获得 500 美元被动收入，以下是它给出的具体计划",
    "ChatGPT": "聊天生成模型",
    "Claude": "克劳德",
    "FTC": "美国联邦贸易委员会",
    "NVIDIA": "英伟达",
    "Nvidia": "英伟达",
    "Supermicro": "美超微",
    "HappyRobot": "快乐机器人",
    "King Slide": "川湖",
    "Quanta": "广达",
    "AIC": "营邦",
    "Compal": "仁宝",
    "Accel": "加速创投",
    "River AI": "河流人工智能",
    "AMD": "超威半导体",
    "CoreWeave": "科瑞维夫",
    "SpaceX": "太空探索技术公司",
    "Lumentum": "朗美通",
    "Oracle": "甲骨文",
    "Bitdeer": "比特小鹿",
    "Edge AI": "边缘人工智能",
    "DDI": "显示驱动芯片",
    "OpenAI": "开放人工智能",
    "Kevin Weil": "凯文·韦尔",
    "IPO": "首次公开募股",
    "Target": "塔吉特",
    "Gemini": "双子座",
    "ETMarkets": "经济时报市场",
    "Rahul Jain": "拉胡尔·贾因",
    "Y.S.": "元山",
    "Thailand": "泰国",
    "泰国’s": "泰国实行",
    "crypto tax": "加密税",
    "Bitcoin Red Team": "比特币红队",
    "forced to use": "被迫使用",
    "Chinese AI": "中国人工智能",
    "Asia Express": "亚洲快报",
    "红队 被迫": "红队被迫",
    "加密税.": "加密税。",
    "中国人工智能: 亚洲": "中国人工智能：亚洲",
}


def apply_title_replacements(title):
    for english, chinese in TITLE_ZH.items():
        title = title.replace(english, chinese)
    return re.sub(r"(?<![A-Za-z])AI(?![A-Za-z])", "人工智能", title, flags=re.I)


def translate_text(text):
    text = (text or "").strip()
    if not text or not any("a" <= ch <= "z" or "A" <= ch <= "Z" for ch in text):
        return text
    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text[:1000])
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
        if translated and translated != text:
            return translated.strip()
    except Exception:
        pass
    return text


def translate_title(title):
    title = (title or "").strip()
    title = apply_title_replacements(title)
    return apply_title_replacements(translate_text(title))


def translate_source(source_name):
    source_name = (source_name or "").strip()
    normalized = re.sub(r"[^a-z0-9]+", "", source_name.lower())
    for english, chinese in SOURCE_ZH.items():
        if re.sub(r"[^a-z0-9]+", "", english.lower()) == normalized:
            return chinese
    return translate_text(source_name)

fs = [f for f in os.listdir(SRC) if f.endswith(".md") and not f.startswith("~")]
fs.sort(key=lambda f: os.path.getmtime(os.path.join(SRC, f)), reverse=True)

with open(os.path.join(SRC, fs[0]), encoding="utf-8-sig") as f:
    content = f.read()

# Parse articles with source names from HTML comments
items = []
lines = content.split("\n")
i = 0
while i < len(lines):
    line = lines[i]
    m = re.match(r"- \[(.*?)\]\(([^)]+)\) \| (\w+)(?: \| (.*?) \| (.*))?", line)
    if m:
        region_code = m.group(3)
        region_name = {"US":"美国","CN":"中国","GB":"英国"}.get(region_code, region_code)
        source_name = ""
        # Read following comments for source name
        j = i + 1
        while j < len(lines):
            cmt = lines[j].strip()
            if cmt.startswith("<!-- SRC:"):
                source_name = cmt[8:-3].strip().lstrip(":")
                break
            elif cmt.startswith("- [") or cmt.startswith("# ") or cmt.startswith("---"):
                break
            j += 1
        items.append((translate_title(m.group(1)), m.group(2), region_name, region_code, m.group(4) or "", m.group(5) or "", translate_source(source_name)))
        i = j
    else:
        i += 1

def fmt_pubdate(raw):
    if not raw: return ""
    try:
        clean = raw.replace(" GMT", "").replace(" UT", "").replace("T", " ").replace("Z", "")
        dt = datetime.strptime(clean[:19], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        try:
            clean = raw.replace(" GMT", "").replace(" UT", "")
            dt = datetime.strptime(clean, "%a, %d %b %Y %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return raw[:16]

date_m = re.search(r"^# AI赚钱日报 (\d{4}-\d{2}-\d{2})", content, re.M)
today = date_m.group(1) if date_m else datetime.now().strftime("%Y-%m-%d")
total = min(MAX_LIST_ITEMS, len(items))
colors = {"美国": "#3b82f6", "中国": "#ef4444", "英国": "#8b5cf6"}

detail_map = {}
map_path = os.path.join(OUT, "details", "detail_map.json")
if os.path.exists(map_path):
    with open(map_path, "r", encoding="utf-8") as f:
        detail_map = json.load(f)

# Source-based colors (alternating)
source_colors = ["#3b82f6", "#8b5cf6", "#06b6d4", "#f59e0b", "#10b981", "#ef4444", "#ec4899", "#6366f1"]

html = '<section style="padding:10px 0;max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">\n'
html += '<section style="text-align:center;padding:30px 16px 16px;">\n'
html += '<h1 style="font-size:24px;font-weight:800;color:#1e293b;margin:0 0 8px;letter-spacing:1px;">\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65e5\u62a5</h1>\n'
html += '<p style="font-size:13px;color:#94a3b8;margin:0;">' + today + ' \u5168\u7403\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65b0\u95fb</p>\n'
html += '</section>\n'

html += '<section style="text-align:center;padding:8px 16px 16px;">\n'
html += '<span style="display:inline-block;background:#f1f5f9;border-radius:8px;padding:10px 24px;margin:4px 8px;"><b style="font-size:20px;color:#3b82f6;">' + str(total) + '</b><br><span style="font-size:11px;color:#94a3b8;">\u603b\u8ba1</span></span>\n'
regions_count = len(set(r for _, _, r, *_ in items[:MAX_LIST_ITEMS]))
html += '<span style="display:inline-block;background:#f1f5f9;border-radius:8px;padding:10px 24px;margin:4px 8px;"><b style="font-size:20px;color:#8b5cf6;">' + str(regions_count) + '</b><br><span style="font-size:11px;color:#94a3b8;">\u5730\u533a</span></span>\n'
html += '</section>\n'

for idx, (title, url, region_name, region_code, pubdate, _summary, source_name) in enumerate(items[:MAX_LIST_ITEMS]):
    detail_file = detail_map.get(str(idx), "")
    detail_path = os.path.join(OUT, "details", detail_file) if detail_file else ""
    if detail_file and os.path.exists(detail_path):
        detail_url = PUBLIC_BASE_URL + "/details/" + detail_file
    else:
        detail_url = url

    # Use source name as badge, region as secondary
    badge_label = source_name if source_name else region_name
    badge_color = source_colors[idx % len(source_colors)]
    # Make color consistent per source
    source_hash = hash(source_name) if source_name else idx
    badge_color = source_colors[abs(source_hash) % len(source_colors)]

    pub = fmt_pubdate(pubdate)
    html += '<section style="background:#f8fafc;border-radius:8px;padding:12px 14px;margin:8px 10px;border-left:3px solid ' + badge_color + ';">\n'
    # Badge: source name
    html += '<span style="display:inline-block;background:' + badge_color + ';color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;margin-right:6px;vertical-align:middle;">' + badge_label + '</span>\n'
    html += '<a href="' + detail_url + '" style="color:#334155;font-size:14px;font-weight:500;line-height:1.5;text-decoration:none;word-break:break-all;">' + title + '</a>\n'
    html += '<a href="' + url + '" style="color:#94a3b8;text-decoration:none;font-size:11px;margin-left:4px;">&#8599;</a>\n'
    # Country/region label instead of "谷歌新闻"
    country_emoji = {"美国":"\U0001F1FA\U0001F1F8","中国":"\U0001F1E8\U0001F1F3","英国":"\U0001F1EC\U0001F1E7"}.get(region_name, "")
    if pub:
        html += '<p style="font-size:10px;color:#cbd5e1;margin:4px 0 0;">' + pub + ' | ' + country_emoji + region_name + '</p>\n'
    html += '</section>\n'

html += '<section style="text-align:center;padding:24px 16px;color:#cbd5e1;font-size:11px;">\n'
html += '<p style="margin:0;">\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65e5\u62a5 \u00b7 \u65b0\u95fb\u805a\u5408\u63a5\u53e3 \u00b7 \u6bcf\u65e5\u66f4\u65b0</p>\n'
html += '</section>\n</section>'

html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65e5\u62a5</title>\n</head>\n<body style="margin:0;padding:0;background:#fff;">\n' + html + '\n</body>\n</html>'

stamp = sys.argv[1].replace("wechat_daily_", "") if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d_%H%M%S")
with open(os.path.join(OUT, "wechat_daily_" + stamp + ".html"), "w", encoding="utf-8") as f:
    f.write(html)
with open(os.path.join(OUT, "wechat_daily_" + stamp + ".txt"), "w", encoding="utf-8") as f:
    f.write(html)
index_name = "wechat_daily_" + stamp + ".html"
index_html = (
    '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n'
    '<meta http-equiv="refresh" content="0;url=' + index_name + '">\n'
    '<title>\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65e5\u62a5</title>\n</head>\n<body>\n'
    '<p>\u6b63\u5728\u8df3\u8f6c\u5230\u4eba\u5de5\u667a\u80fd\u8d5a\u94b1\u65e5\u62a5... '
    '<a href="' + index_name + '">\u70b9\u6b64\u76f4\u63a5\u8fdb\u5165</a></p>\n</body>\n</html>\n'
)
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_html)
print("Saved: wechat_daily_" + stamp + ".html + .txt  (" + str(total) + " cards)")
