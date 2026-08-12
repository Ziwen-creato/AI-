# -*- coding: utf-8 -*-
"""NewsAPI + article fetch + LLM full Chinese content."""
import os, re, json, time, urllib.request, urllib.parse, sys, ssl
from html import escape, unescape
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

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

def extract_article_and_images(html):
    if not html or len(html) < 500:
        return '', []
    try:
        from lxml.html import fromstring
        tree = fromstring(html)
    except:
        return '', []
    images = []
    for img in tree.xpath('//img'):
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
            src = img.get(attr, '')
            if src and src.startswith('http') and not any(s in src.lower() for s in ['icon', 'logo', 'avatar', 'pixel', '1x1', 'spacer', 'tracking', 'ad.', '/ads/']):
                w = img.get('width', '')
                if w and w.isdigit() and int(w) < 200: continue
                images.append(src)
                break
    images = list(dict.fromkeys(images))[:5]
    for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside',
                'noscript', 'form', 'iframe', 'svg', 'figure', 'figcaption']:
        for el in tree.xpath('//' + tag):
            try: el.getparent().remove(el)
            except: pass
    paras = []
    for el in tree.iter('p'):
        text = el.text_content().strip()
        if len(text) < 30: continue
        links = el.xpath('.//a')
        link_text = sum(len(a.text_content()) for a in links if a.text_content())
        if len(text) > 0 and link_text / len(text) > 0.5: continue
        paras.append(text)
    if not paras:
        body = tree.find('body')
        if body is not None:
            return body.text_content().strip()[:5000], images
        return '', images
    return '\n\n'.join(paras[:20]), images

def llm_article(title, description, article_text):
    """Generate full Chinese article from available sources."""
    has_full = len(article_text) > 200

    if has_full:
        prompt = f"""请将以下英文新闻翻译成流畅自然的中文新闻稿。

要求：
- 4-6 个自然段落
- 保持原文信息完整
- 语言专业流畅，新闻风格
- 直接输出中文，不加任何前缀

标题：{title}
英文原文：
{article_text[:5000]}

中文翻译："""
    else:
        prompt = f"""你是一位资深中文财经编辑。请根据以下新闻线索写一篇完整的中文新闻稿。

要求：
- 4-6 个自然段落，总字数 600-1000
- 第一段导语概括核心事件和影响
- 中间段落展开细节、背景、数据
- 最后一段总结展望
- 语言专业流畅，中立新闻风格
- 直接输出中文段落，不加标题前缀

标题：{title}
摘要线索：{description[:800]}

中文新闻稿："""

    body = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "请用中文回答。你一定要用中文输出。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2500,
        "temperature": 0.7
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
        return content
    except Exception as e:
        print('    LLM error: ' + str(e))
        return None

def gen_page(title, source_url, region, pubdate, cn_text, images, en_text=''):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    pub_str = pubdate[:19] if pubdate else ''
    img_html = ''
    for img_url in images[:3]:
        if img_url.startswith('http'):
            img_html += '<div style="margin:16px 0;text-align:center;"><img src="' + img_url + '" style="max-width:100%;border-radius:8px;" alt="" loading="lazy" onerror="this.style.display=\'none\'"/></div>\n'

    paras = [p.strip() for p in cn_text.split('\n\n') if p.strip()]
    if len(paras) < 2:
        paras = [p.strip() for p in cn_text.split('\n') if p.strip() and len(p.strip()) > 15]
    p_html = ''
    for p in paras:
        p_html += '<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;text-indent:2em;">' + escape(p) + '</p>\n'
    if not p_html:
        p_html = '<p style="font-size:16px;color:#334155;line-height:1.9;margin:14px 0;">' + escape(cn_text) + '</p>\n'

    en_section = ''
    if en_text and len(en_text) > 50:
        en_section = '<details style="margin-top:20px;padding:14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"><summary style="font-size:13px;color:#64748b;cursor:pointer;">英文原文</summary><p style="font-size:14px;color:#64748b;line-height:1.8;margin:10px 0 0;white-space:pre-wrap;">' + escape(en_text[:2000]) + '</p></details>\n'

    safe_url = escape(source_url, quote=True)
    t = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>' + escape(title) + '</title>\n<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#334155;padding:16px;max-width:700px;margin:0 auto}h1{font-size:22px;color:#1e293b;margin:16px 0 8px;line-height:1.5}.meta{font-size:12px;color:#94a3b8;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}.meta span{margin-right:16px}.back{display:inline-block;margin-top:24px;color:#3b82f6;text-decoration:none;font-size:14px}.source{margin-top:16px;font-size:12px;color:#cbd5e1;padding-top:12px;border-top:1px solid #e2e8f0}.source a{color:#94a3b8;word-break:break-all}img{height:auto}</style>\n</head><body>\n<h1>' + escape(title) + '</h1>\n<div class="meta"><span>' + region + '</span><span>' + pub_str + '</span><span>' + now + '</span></div>\n' + img_html + '<div class="content">' + p_html + '</div>\n' + en_section + '<div class="source">原文链接：<a href="' + safe_url + '" target="_blank">查看原文</a></div>\n<a href="javascript:history.back()" class="back">&larr; 返回日报</a>\n</body></html>'
    return t

def main():
    fs = [f for f in os.listdir(SRC) if f.endswith('.md') and not f.startswith('~')]
    fs.sort(key=lambda f: os.path.getmtime(os.path.join(SRC, f)), reverse=True)
    with open(os.path.join(SRC, fs[0]), encoding='utf-8-sig') as f:
        content = f.read()

    items = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'- \[(.*?)\]\(([^)]+)\) \| (\w+)(?: \| (.*?) \| (.*))?', line)
        if m:
            article = {'title': m.group(1), 'url': m.group(2), 'region': m.group(3),
                       'pubdate': m.group(4) or '', 'desc': m.group(5) or '',
                       'image_url': '', 'content': '', 'source_name': ''}
            j = i + 1
            while j < len(lines):
                cmt = lines[j].strip()
                if cmt.startswith('<!-- IMG:'): article['image_url'] = cmt[8:-3].strip()
                elif cmt.startswith('<!-- CNT:'): article['content'] = cmt[8:-3].strip()
                elif cmt.startswith('<!-- SRC:'): article['source_name'] = cmt[8:-3].strip()
                elif cmt.startswith('- [') or cmt.startswith('# ') or cmt.startswith('---'): break
                j += 1
            items.append(article)
            i = j
        else:
            i += 1

    total = min(5, len(items))
    print('\nGenerating full articles (' + str(total) + ' items)...\n')
    detail_map = {}

    for idx, article in enumerate(items[:total]):
        title = article['title']
        url = article['url']
        rgn = {'US':'美国','CN':'中国','GB':'英国'}.get(article['region'], article['region'])
        pubdate = article['pubdate']
        desc = article.get('desc', '')
        newsapi_img = article.get('image_url', '')
        newsapi_content = article.get('content', '')
        source_name = article.get('source_name', '')

        print('[' + str(idx+1) + '/' + str(total) + '] ' + title[:50] + '...')

        # Try to fetch real article
        en_text = ''
        images = []
        html = _fetch(url, timeout=15)
        if html:
            article_text, imgs = extract_article_and_images(html)
            if article_text and len(article_text) > 100:
                en_text = article_text
                print('  Fetched: ' + str(len(en_text)) + ' chars, ' + str(len(imgs)) + ' images')
            else:
                print('  Short/paywall article (' + str(len(article_text)) + ' chars)')
            if imgs: images = imgs
        else:
            print('  Could not fetch (blocked)')

        # Fallback images
        if newsapi_img and not images: images = [newsapi_img]
        elif newsapi_img: images.insert(0, newsapi_img)

        # Generate Chinese content via LLM
        # Use description from NewsAPI as fallback context
        context = en_text if len(en_text) > 100 else (newsapi_content + '\n\n' + desc)
        cn_text = llm_article(title, desc, context)
        if cn_text and len(cn_text) > 100:
            paras_count = len([p for p in cn_text.split('\n\n') if p.strip()])
            print('  CN: ' + str(len(cn_text)) + ' chars, ' + str(paras_count) + ' paragraphs')
        else:
            print('  LLM failed, using description')
            cn_text = desc if desc else title

        detail_name = 'detail_' + format(idx, '03d') + '.html'
        page = gen_page(title, url, rgn, pubdate, cn_text, images, en_text[:2000] if len(en_text) > 50 else '')
        with open(os.path.join(OUT, detail_name), 'w', encoding='utf-8') as f:
            f.write(page)
        detail_map[str(idx)] = detail_name
        time.sleep(0.5)

    with open(os.path.join(OUT, 'detail_map.json'), 'w', encoding='utf-8') as f:
        json.dump(detail_map, f, ensure_ascii=False, indent=2)
    print('\nDone! ' + str(total) + ' detail pages.\n')

if __name__ == '__main__':
    main()
