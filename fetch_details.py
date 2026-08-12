# -*- coding: utf-8 -*-
"""Fetch article details: OG image + LLM full article (long timeout, retry)."""
import os, re, json, time, urllib.request, sys
from datetime import datetime
from html import escape
sys.stdout.reconfigure(encoding='utf-8')

SRC = r'C:/AI编程/AI赚钱新闻收集/ai_reports'
OUT = r'C:/AI编程/AI赚钱新闻收集/html/details'
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
LLM_URL = 'http://127.0.0.1:15721/v1/chat/completions'

def _fetch(url, timeout=12, retries=2):
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')
        except: time.sleep(0.5)
    return None

def fetch_og_image(gn_url):
    html = _fetch(gn_url, timeout=15)
    if not html: return None
    m = re.search(r'og:image.*?content="(.+?)"', html)
    if m: return m.group(1)
    m = re.search(r'"(https?://lh3\.googleusercontent\.com/[^"]+)"', html)
    if m: return m.group(1)
    return None

def llm_article(title, summary, retry_left=2):
    prompt = f"""你是资深中文财经编辑。根据以下英文新闻线索，写一篇完整中文新闻稿。

要求：
- 4-6 个自然段落，总字数 800-1200
- 第一段导语概括核心事件
- 中间段落展开细节、背景、数据
- 最后一段总结影响和展望
- 语言专业流畅，中立新闻风格
- 直接输出中文段落，不加标题前缀

标题：{title}
摘要线索：{summary[:500]}

中文新闻稿："""

    body = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "你是一位专业中文财经记者。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.8
    }
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(LLM_URL, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer PROXY_MANAGED'
    })
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
        content = resp['choices'][0]['message']['content'].strip()
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        if len(content) < 100:
            raise ValueError("TOO SHORT")
        return content
    except Exception as e:
        if retry_left > 0:
            print(f'    Retrying LLM ({retry_left} left)...')
            time.sleep(3)
            return llm_article(title, summary, retry_left - 1)
        print(f'    LLM failed: {e}')
        return None

def gen_page(title, source_url, region, pubdate, cn_text, og_image=''):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    pub_str = pubdate[:19] if pubdate else ''
    img_html = ''
    if og_image:
        img_html = f'<div style="margin:16px 0;text-align:center;"><img src="{og_image}" style="max-width:100%;border-radius:8px;" alt="" onerror="this.style.display=\'none\'"/></div>\n'
    # Parse paragraphs - split by double newline
    raw_paras = [p.strip() for p in cn_text.split('\n\n') if p.strip()]
    if len(raw_paras) < 2:
        raw_paras = [p.strip() for p in cn_text.split('\n') if p.strip()]
    p_html = ''
    for p in raw_paras:
        p_html += f'<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;text-indent:2em;">{escape(p)}</p>\n'
    if not p_html:
        p_html = f'<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;">{escape(cn_text)}</p>\n'

    safe_url = escape(source_url, quote=True)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#334155;padding:16px;max-width:700px;margin:0 auto}}h1{{font-size:22px;color:#1e293b;margin:16px 0 8px;line-height:1.5}}.meta{{font-size:12px;color:#94a3b8;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}}.meta span{{margin-right:16px}}.back{{display:inline-block;margin-top:24px;color:#3b82f6;text-decoration:none;font-size:14px}}.source{{margin-top:16px;font-size:12px;color:#cbd5e1;padding-top:12px;border-top:1px solid #e2e8f0}}.source a{{color:#94a3b8;word-break:break-all}}</style>
</head><body>
<h1>{escape(title)}</h1>
<div class="meta"><span>{region}</span><span>{pub_str}</span><span>AI生成 · {now}</span></div>
{img_html}
<div class="content">{p_html}</div>
<div class="source">原文链接：<a href="{safe_url}" target="_blank">查看原文</a></div>
<a href="javascript:history.back()" class="back">&larr; 返回日报</a>
</body></html>'''

def main():
    fs = [f for f in os.listdir(SRC) if f.endswith('.md') and not f.startswith('~')]
    fs.sort(key=lambda f: os.path.getmtime(os.path.join(SRC, f)), reverse=True)
    with open(os.path.join(SRC, fs[0]), encoding='utf-8-sig') as f:
        content = f.read()

    items = []
    for line in content.split('\n'):
        m = re.match(r'- \[(.*?)\]\(([^)]+)\) \| (\w+)(?: \| (.*?) \| (.*))?', line)
        if m:
            rgn = {'US':'美国','CN':'中国','GB':'英国'}.get(m.group(3), m.group(3))
            items.append((m.group(1), m.group(2), rgn, m.group(4) or '', m.group(5) or ''))

    total = min(5, len(items))
    print(f'\nGenerating full articles ({total} items)...\n')
    detail_map = {}
    for i, (title, url, region, pubdate, summary) in enumerate(items[:total]):
        print(f'[{i+1}/{total}] {title[:50]}...')
        og = fetch_og_image(url)
        print(f'  Image: {og[:70] if og else "none"}')
        cn = llm_article(title, summary)
        if cn:
            paras = len([p for p in cn.split('\n\n') if p.strip()])
            print(f'  Content: {len(cn)} chars, {paras} paragraphs')
        else:
            print(f'  LLM failed, using summary')
            cn = summary.strip() if summary else title
        detail_name = f'detail_{i:03d}.html'
        page = gen_page(title, url, region, pubdate, cn, og)
        with open(os.path.join(OUT, detail_name), 'w', encoding='utf-8') as f:
            f.write(page)
        detail_map[str(i)] = detail_name
        time.sleep(0.3)

    with open(os.path.join(OUT, 'detail_map.json'), 'w', encoding='utf-8') as f:
        json.dump(detail_map, f, ensure_ascii=False, indent=2)
    print(f'\nDone! {total} detail pages.\n')

if __name__ == '__main__':
    main()
