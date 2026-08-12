import os, re, sys, json
from datetime import datetime, timezone, timedelta
from html import unescape

SRC = "C:/AI编程/AI赚钱新闻收集/ai_reports"
OUT = "C:/AI编程/AI赚钱新闻收集/html"

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
        items.append((m.group(1), m.group(2), region_name, region_code, m.group(4) or "", m.group(5) or "", source_name))
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
total = len(items)
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
html += '<h1 style="font-size:24px;font-weight:800;color:#1e293b;margin:0 0 8px;letter-spacing:1px;">AI\u8d5a\u94b1\u65e5\u62a5</h1>\n'
html += '<p style="font-size:13px;color:#94a3b8;margin:0;">' + today + ' \u5168\u7403AI\u8d5a\u94b1\u65b0\u95fb</p>\n'
html += '</section>\n'

html += '<section style="text-align:center;padding:8px 16px 16px;">\n'
html += '<span style="display:inline-block;background:#f1f5f9;border-radius:8px;padding:10px 24px;margin:4px 8px;"><b style="font-size:20px;color:#3b82f6;">' + str(total) + '</b><br><span style="font-size:11px;color:#94a3b8;">\u603b\u8ba1</span></span>\n'
regions_count = len(set(r for _, _, r, *_ in items))
html += '<span style="display:inline-block;background:#f1f5f9;border-radius:8px;padding:10px 24px;margin:4px 8px;"><b style="font-size:20px;color:#8b5cf6;">' + str(regions_count) + '</b><br><span style="font-size:11px;color:#94a3b8;">\u5730\u533a</span></span>\n'
html += '</section>\n'

for idx, (title, url, region_name, region_code, pubdate, summary, source_name) in enumerate(items[:50]):
    detail_file = detail_map.get(str(idx), "")
    detail_path = os.path.join(OUT, "details", detail_file) if detail_file else ""
    if detail_file and os.path.exists(detail_path):
        detail_url = "details/" + detail_file
    else:
        detail_url = url

    # Use source name as badge, region as secondary
    badge_label = source_name if source_name else region_name
    badge_color = source_colors[idx % len(source_colors)]
    # Make color consistent per source
    source_hash = hash(source_name) if source_name else idx
    badge_color = source_colors[abs(source_hash) % len(source_colors)]

    pub = fmt_pubdate(pubdate)
    clean_sum = unescape(summary)
    clean_sum = re.sub(r'<[^>]+>', '', clean_sum).strip()
    if '<' in clean_sum:
        clean_sum = clean_sum[:clean_sum.index('<')].strip()
    short_sum = clean_sum[:80]

    html += '<section style="background:#f8fafc;border-radius:8px;padding:12px 14px;margin:8px 10px;border-left:3px solid ' + badge_color + ';">\n'
    # Badge: source name
    html += '<span style="display:inline-block;background:' + badge_color + ';color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;margin-right:6px;vertical-align:middle;">' + badge_label + '</span>\n'
    html += '<a href="' + detail_url + '" style="color:#334155;font-size:14px;font-weight:500;line-height:1.5;text-decoration:none;word-break:break-all;">' + title + '</a>\n'
    html += '<a href="' + url + '" style="color:#94a3b8;text-decoration:none;font-size:11px;margin-left:4px;">&#8599;</a>\n'
    if short_sum:
        html += '<p style="font-size:12px;color:#94a3b8;margin:6px 0 0;line-height:1.5;">' + short_sum + '</p>\n'
    # Country/region label instead of "谷歌新闻"
    country_emoji = {"美国":"\U0001F1FA\U0001F1F8","中国":"\U0001F1E8\U0001F1F3","英国":"\U0001F1EC\U0001F1E7"}.get(region_name, "")
    if pub:
        html += '<p style="font-size:10px;color:#cbd5e1;margin:4px 0 0;">' + pub + ' | ' + country_emoji + region_name + '</p>\n'
    html += '</section>\n'

html += '<section style="text-align:center;padding:24px 16px;color:#cbd5e1;font-size:11px;">\n'
html += '<p style="margin:0;">AI\u8d5a\u94b1\u65e5\u62a5 \u00b7 NewsAPI \u00b7 \u6bcf\u65e5\u66f4\u65b0</p>\n'
html += '</section>\n</section>'

stamp = sys.argv[1].replace("wechat_daily_", "") if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d_%H%M%S")
with open(os.path.join(OUT, "wechat_daily_" + stamp + ".html"), "w", encoding="utf-8") as f:
    f.write(html)
with open(os.path.join(OUT, "wechat_daily_" + stamp + ".txt"), "w", encoding="utf-8") as f:
    f.write(html)
print("Saved: wechat_daily_" + stamp + ".html + .txt  (" + str(min(50, len(items))) + " cards)")
