# -*- coding: utf-8 -*-
"""Fetch full article content and generate rich Chinese detail pages via LLM."""
import os, re, json, time, urllib.request, urllib.parse, sys
from datetime import datetime
from html import unescape, escape
sys.stdout.reconfigure(encoding='utf-8')

SRC = r'C:/AI编程/AI赚钱新闻收集/ai_reports'
OUT = r'C:/AI编程/AI赚钱新闻收集/html/details'
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
LLM_URL = 'http://127.0.0.1:15721/v1/chat/completions'

def _fetch_url(url, timeout=10, retries=2):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(0.5)
    return None

def extract_article_lxml(html):
    if not html or len(html) < 500:
        return ''
    try:
        from lxml.html import fromstring
        tree = fromstring(html)
    except:
        return ''
    for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside',
                'noscript', 'form', 'iframe', 'svg', 'figure', 'figcaption']:
        for el in tree.xpath(f'//{tag}'):
            try: el.getparent().remove(el)
            except: pass
    paras = []
    for el in tree.iter('p'):
        text = el.text_content().strip()
        if len(text) < 30:
            continue
        links = el.xpath('.//a')
        link_text_len = sum(len(a.text_content()) for a in links if a.text_content())
        if len(text) > 0 and link_text_len / len(text) > 0.5:
            continue
        if len(text) > 800:
            continue
        paras.append(text)
    if not paras:
        body = tree.find('body')
        if body is not None:
            return body.text_content().strip()[:3000]
        return ''
    return '\n\n'.join(paras[:20])

def llm_summary(title, source_text, source_url=''):
    """Generate a comprehensive 200-400 char Chinese summary using LLM."""
    prompt = f"""你是一个中文新闻摘要编辑。请根据以下英文新闻内容，用中文写一段 200-400 字的摘要。

要求：
- 用流畅自然的中文
- 包含关键信息：发生了什么、涉及谁、为什么重要
- 保持新闻感，不要啰嗦

标题：{title}
{'' if not source_url else '来源：' + source_url}

原文内容：
{source_text[:3000]}

请直接输出中文摘要，不要包含任何前缀或标记。"""

    body = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "你是一个专业的中文新闻摘要编辑。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.7
    }
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(LLM_URL, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer PROXY_MANAGED'
    })
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        content = resp['choices'][0]['message']['content'].strip()
        # Remove any markdown fences
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        return content
    except Exception as e:
        print(f'    LLM error: {e}')
        return None

def gen_page(title, source_url, region, pubdate, cn_text, en_text=''):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    pub_str = pubdate[:19] if pubdate else ''
    paras = cn_text.split('\n')
    p_html = ''
    for p in paras:
        p = p.strip()
        if p:
            p_html += f'<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;">{escape(p)}</p>\n'
    if not p_html:
        p_html = f'<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;">{escape(cn_text)}</p>\n'
    original = ''
    if en_text and en_text.strip() and cn_text.strip() != en_text.strip():
        original = f'<details style="margin-top:18px;padding:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"><summary style="font-size:12px;color:#64748b;cursor:pointer;">原文摘要</summary><p style="font-size:13px;color:#64748b;line-height:1.8;margin:10px 0 0;">{escape(en_text)}</p></details>\n'
    safe_url = escape(source_url, quote=True)
    return f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{escape(title)}</title>\n<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#334155;padding:16px;max-width:700px;margin:0 auto}}h1{{font-size:22px;color:#1e293b;margin:16px 0 12px;line-height:1.5}}.meta{{font-size:12px;color:#94a3b8;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #e2e8f0}}.meta span{{margin-right:16px}}.back{{display:inline-block;margin-top:24px;color:#3b82f6;text-decoration:none;font-size:14px}}.source{{margin-top:8px;font-size:12px;color:#cbd5e1}}.source a{{color:#94a3b8;word-break:break-all}}</style>\n</head>\n<body>\n<h1>{escape(title)}</h1>\n<div class="meta"><span>{region}</span><span>{pub_str}</span><span>生成于 {now}</span></div>\n<div class="content">{p_html}</div>\n{original}<div class="source">原文来源：<a href="{safe_url}">查看原文</a></div>\n<a href="javascript:history.back()" class="back">&larr; 返回</a>\n</body>\n</html>'

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
    print(f'\nGenerating rich detail pages ({total} items)...\n')

    detail_map = {}
    for i, (title, url, region, pubdate, summary) in enumerate(items[:total]):
        print(f'[{i+1}/{total}] {title[:50]}...')

        # Step 1: Try to fetch full article
        article_text = None
        html = _fetch_url(url, timeout=12)
        if html:
            article_text = extract_article_lxml(html)
            if article_text:
                print(f'  Fetched article: {len(article_text)} chars')
            else:
                print(f'  Failed to extract content, using RSS summary')

        # Step 2: Generate Chinese summary via LLM
        source = article_text if article_text else summary.strip()
        if not source or len(source) < 20:
            source = title + '\n\n' + (summary.strip() if summary else '')

        cn_text = llm_summary(title, source, url)
        if not cn_text or len(cn_text) < 30:
            # Fallback: quick Google Translate of the summary
            print(f'  LLM failed, using basic translation')
            cn_text = summary.strip() if summary else title

        print(f'  CN: {len(cn_text)} chars')

        # Save
        detail_name = f'detail_{i:03d}.html'
        page = gen_page(title, url, region, pubdate, cn_text, source[:500])
        with open(os.path.join(OUT, detail_name), 'w', encoding='utf-8') as f:
            f.write(page)
        detail_map[str(i)] = detail_name
        time.sleep(0.5)

    with open(os.path.join(OUT, 'detail_map.json'), 'w', encoding='utf-8') as f:
        json.dump(detail_map, f, ensure_ascii=False, indent=2)
    print(f'\nDone! {total} detail pages.\n')

if __name__ == '__main__':
    main()
