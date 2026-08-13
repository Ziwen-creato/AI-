#!/usr/bin/env python3
"""Publish daily news to WeChat Official Account (微信公众号)"""
import os, sys, json, time, glob, re
import urllib.request, urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(SCRIPT_DIR, "html")

# ---------------------------------------------------------------------------
# 1. Load config
# ---------------------------------------------------------------------------
cfg_path = os.path.join(SCRIPT_DIR, "wechat_config.json")
if not os.path.exists(cfg_path):
    print(f"[ERROR] Config file not found: {cfg_path}")
    print("Please edit wechat_config.json with your AppID and AppSecret.")
    sys.exit(1)

with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

APPID    = cfg["appid"]
SECRET   = cfg["appsecret"]
AUTHOR   = cfg.get("author", "AI赚钱日报")
AUTO_PUB = cfg.get("auto_publish", False)
COMMENT  = cfg.get("comment_open", True)

if "请填写" in APPID or "请填写" in SECRET:
    print("[ERROR] Please fill in your AppID and AppSecret in wechat_config.json")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Get access token
# ---------------------------------------------------------------------------
def get_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}"
    try:
        req = urllib.request.Request(url)
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        if "access_token" in resp:
            return resp["access_token"]
        print(f"[ERROR] Token failed: {resp}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Network error getting token: {e}")
        sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Find latest generated file
# ---------------------------------------------------------------------------
def find_latest_html():
    files = glob.glob(os.path.join(HTML_DIR, "wechat_daily_*.html"))
    if not files:
        print("[ERROR] No wechat_daily_*.html found in html/")
        sys.exit(1)
    latest = max(files, key=os.path.getmtime)
    print(f"[INFO] Using: {os.path.basename(latest)}")
    return latest

# ---------------------------------------------------------------------------
# 4. Extract title & digest from HTML
# ---------------------------------------------------------------------------
def extract_meta(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Title from <title> or h1
    title_m = re.search(r'<title>(.*?)</title>', content)
    h1_m    = re.search(r'<h1[^>]*>(.*?)</h1>', content)
    if title_m:
        title = title_m.group(1).strip()
    elif h1_m:
        title = h1_m.group(1).strip()
    else:
        title = "AI赚钱日报"

    # Digest: first summary paragraph or date line
    digest_m = re.search(r'<p[^>]*style="font-size:12px;color:#94a3b8;margin:6px 0 0[^"]*"[^>]*>(.*?)</p>', content)
    date_m   = re.search(r'<p style="font-size:13px[^"]*"[^>]*>(.*?)</p>', content)
    if digest_m:
        digest = re.sub(r'<[^>]+>', '', digest_m.group(1))
    elif date_m:
        digest = re.sub(r'<[^>]+>', '', date_m.group(1))
    else:
        digest = "全球AI赚钱新闻"

    digest = digest.strip()[:120]
    return title, digest, content

# ---------------------------------------------------------------------------
# 5. Clean HTML for WeChat (strip problematic tags/attributes)
# ---------------------------------------------------------------------------
def clean_for_wechat(html):
    """WeChat accepts a subset of HTML with inline styles."""
    # Remove DOCTYPE, html, head, body tags - keep only body content
    body_m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if body_m:
        html = body_m.group(1)

    # Remove <script>, <iframe>, <embed>, <object>
    for tag in ["script", "iframe", "embed", "object"]:
        html = re.sub(fr'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove event handlers (onclick, onload, etc.)
    html = re.sub(r'\s+on\w+="[^"]*"', '', html)

    return html.strip()

# ---------------------------------------------------------------------------
# 6. Create draft on WeChat
# ---------------------------------------------------------------------------
def create_draft(token, title, digest, content_html, source_url=""):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"

    # WeChat content needs <section> wrappers but the generated HTML already has them
    body = {
        "articles": [{
            "title":              title,
            "author":             AUTHOR,
            "digest":             digest,
            "content":            content_html,
            "content_source_url": source_url,
            "need_open_comment":  1 if COMMENT else 0,
            "only_fans_can_comment": 0,
        }]
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        print(f"[DRAFT] Response: {resp}")
        return resp
    except Exception as e:
        print(f"[ERROR] Draft creation failed: {e}")
        return {}

# ---------------------------------------------------------------------------
# 7. Optional: publish the draft (free publish, not mass-send)
# ---------------------------------------------------------------------------
def publish_draft(token, media_id):
    url = f"https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token={token}"
    body = {"media_id": media_id}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        print(f"[PUBLISH] Response: {resp}")
        if resp.get("errmsg") == "ok":
            print("[PUBLISH] Article published successfully!")
        return resp
    except Exception as e:
        print(f"[ERROR] Publish failed: {e}")
        return {}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("  WeChat Official Account Publisher")
    print("=" * 50)

    html_path = find_latest_html()
    title, digest, content_html = extract_meta(html_path)
    print(f"[INFO] Title: {title}")
    print(f"[INFO] Digest: {digest}")

    token = get_token()
    print(f"[INFO] Token obtained: {token[:10]}...")

    cleaned = clean_for_wechat(content_html)

    # Use GitHub Pages URL as source URL
    source_url = "https://ziwen-creato.github.io/AI-/"

    result = create_draft(token, title, digest, cleaned, source_url)

    if result.get("media_id"):
        media_id = result["media_id"]
        print(f"[OK] Draft created! media_id: {media_id}")
        print(f"[INFO] You can now review the draft in WeChat MP backend.")
        print(f"[INFO] URL: https://mp.weixin.qq.com")

        if AUTO_PUB:
            print("[INFO] Auto-publish enabled, submitting...")
            time.sleep(2)
            publish_draft(token, media_id)
        else:
            print("[INFO] Auto-publish disabled. Please publish manually.")
    else:
        print(f"[ERROR] Draft creation failed. Check error message above.")
        if "errcode" in result:
            codes = {
                40001: "Invalid token (expired or wrong)",
                40007: "Invalid media_id",
                40125: "Invalid appsecret",
                41001: "Missing access_token",
                45009: "API call limit reached",
                48001: "Not authorized (account not verified?)",
            }
            code = result.get("errcode", 0)
            msg  = result.get("errmsg", "unknown")
            hint = codes.get(code, "")
            print(f"[ERROR] errcode={code} errmsg={msg} {hint}")
