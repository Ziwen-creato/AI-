# -*- coding: utf-8 -*-
"""NewsAPI + content extraction + clean images via NewsAPI urlToImage primary."""
import os, re, json, time, urllib.request, urllib.parse, sys, ssl
from html import escape
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

SRC = r'C:/AI编程/AI赚钱新闻收集/ai_reports'
OUT = r'C:/AI编程/AI赚钱新闻收集/html/details'
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
LLM_URL = 'http://127.0.0.1:15721/v1/chat/completions'

SKIP_IMG = ['icon', 'logo', 'avatar', 'pixel', '1x1', 'spacer', 'tracking', 'analytics',
            '/ad/', '/ads/', '/banner/', '/leaderboard/', '/promo/', '/sponsor',
            'b2b3_', 'button336', 'btn_', '_ad_', 'advert', 'author', 'profile',
            'gravatar', 'emoji', 'smiley', 'thumb-', '-thumb', '50x50', '100x100',
            'placeholder', 'pixel.', 'loading.', 'spinner']

def _fetch(url, timeout=12, retries=2):
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')
        except: time.sleep(0.5)
    return None

def extract_article_text(html):
    """Extract article text only (no images - we use NewsAPI for images)."""
    if not html or len(html) < 500:
        return ''
    try:
        from lxml.html import fromstring
        tree = fromstring(html)
    except:
        return ''
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
            return body.text_content().strip()[:5000]
        return ''
    return '\n\n'.join(paras[:20])

def extract_images_from_page(html):
    """Extract content images from article page (used as fallback only)."""
    if not html or len(html) < 500:
        return []
    try:
        from lxml.html import fromstring
        tree = fromstring(html)
    except:
        return []
    images = []
    for img in tree.xpath('//img'):
        # Check parent context - skip if inside author/avatar/sidebar area
        parent = img.getparent()
        skip = False
        for _ in range(4):  # Check up to 4 levels up
            if parent is None: break
            cls = (parent.get('class') or '') + ' ' + (parent.get('id') or '')
            if any(s in cls.lower() for s in ['author', 'avatar', 'sidebar', 'widget', 'comment', 'footer', 'nav', 'header']):
                skip = True
                break
            parent = parent.getparent()

        if skip: continue

        src = ''
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
            v = img.get(attr, '')
            if v and ('http' in v):
                src = v
                break
        if not src: continue

        src = src.lstrip(':').strip()
        src_lower = src.lower()

        # Filter by URL patterns
        if any(p in src_lower for p in SKIP_IMG): continue
        if any(s in src_lower for s in ['google', 'gstatic', 'doubleclick', 'facebook', 'twitter', 'instagram']):
            if 'googleusercontent' not in src_lower: continue

        # Filter by dimensions
        w = img.get('width', '')
        h = img.get('height', '')
        if w and h and w.isdigit() and h.isdigit():
            wi, hi = int(w), int(h)
            if wi > 400 and hi < 60: continue  # ultra-wide banner
            if wi < 100 or hi < 100: continue  # too small
            if wi / max(hi, 1) > 4: continue  # very wide (banner)
            if hi / max(wi, 1) > 4: continue  # very tall

        images.append(src)

    return list(dict.fromkeys(images))[:3]  # max 3 fallback images

def llm_article(title, description, article_text):
    has_full = len(article_text) > 200
    if has_full:
        prompt = '请将以下英文新闻翻译成流畅自然的中文新闻稿（4-6段）。\n\n要求：\n- 保持原文信息完整\n- 语言专业流畅\n- 直接输出中文\n\n标题：' + title + '\n英文原文：\n' + article_text[:5000] + '\n\n中文翻译：'
    else:
        prompt = '你是资深中文财经编辑。根据以下线索写一篇完整中文新闻稿（4-6段，600-1000字）。\n\n要求：\n- 导语概括核心事件\n- 中间展开细节背景\n- 结尾总结影响\n- 直接输出中文\n\n标题：' + title + '\n线索：' + description[:800] + '\n\n中文新闻稿：'
    body = {"model": "deepseek-v4-pro", "messages": [{"role": "system", "content": "请用中文回答。"}, {"role": "user", "content": prompt}], "max_tokens": 2500, "temperature": 0.7}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(LLM_URL, data=data, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer PROXY_MANAGED'})
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
    pub_str = (pubdate or '')[:19]
    img_html = ''
    for img_url in images[:3]:
        clean_url = img_url.lstrip(':').strip()
        if clean_url.startswith('http'):
            img_html += '<div style="margin:16px 0;text-align:center;"><img src="' + clean_url + '" style="max-width:100%;border-radius:8px;" alt="" onerror="this.style.display=\'none\'"/></div>\n'
    paras = [p.strip() for p in cn_text.split('\n\n') if p.strip()]
    if len(paras) < 2:
        paras = [p.strip() for p in cn_text.split('\n') if p.strip() and len(p.strip()) > 15]
    p_html = ''
    for p in paras:
        p_html += '<p style="font-size:17px;color:#334155;line-height:2.0;margin:18px 0;">' + escape(p) + '</p>\n'
    if not p_html:
        p_html = '<p style="font-size:17px;color:#334155;line-height:2.0;margin:18px 0;">' + escape(cn_text) + '</p>\n'
    en_section = ''
    if en_text and len(en_text.strip()) > 50:
        en_section = '<details style="margin-top:20px;padding:14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"><summary style="font-size:13px;color:#64748b;cursor:pointer;">英文原文</summary><p style="font-size:14px;color:#64748b;line-height:1.8;margin:10px 0 0;white-space:pre-wrap;">' + escape(en_text[:2000]) + '</p></details>\n'
    safe_url = escape(source_url, quote=True)
    return '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>' + escape(title) + '</title>\n<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#334155;padding:16px;max-width:700px;margin:0 auto}h1{font-size:24px;color:#1e293b;margin:16px 0 8px;line-height:1.6}.meta{font-size:12px;color:#94a3b8;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}.meta span{margin-right:16px}.back{display:inline-block;margin-top:24px;color:#3b82f6;text-decoration:none;font-size:14px}.source{margin-top:16px;font-size:12px;color:#cbd5e1;padding-top:12px;border-top:1px solid #e2e8f0}.source a{color:#94a3b8;word-break:break-all}img{height:auto}</style>\n</head>\n<body>\n<h1>' + escape(title) + '</h1>\n<div class="meta"><span>' + region + '</span><span>' + pub_str + '</span><span>生成于 ' + now + '</span></div>\n' + img_html + '<div class="content">' + p_html + '</div>\n' + en_section + '<div class="source">原文来源：<a href="' + safe_url + '">查看原文</a></div>\n<a href="javascript:history.back()" class="back">&larr; 返回</a>\n</body>\n</html>'

def main():
    fs = [f for f in os.listdir(SRC) if f.endswith('.md') and not f.startswith('~')]
    fs.sort(key=lambda f: os.path.getmtime(os.path.join(SRC, f)), reverse=True)
    with open(os.path.join(SRC, fs[0]), encoding='utf-8-sig') as f:
        content = f.read()

    # Parse articles with metadata
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
                elif cmt.startswith('<!-- SRC:'): article['source_name'] = cmt[8:-3].strip().lstrip(':')
                elif cmt.startswith('- [') or cmt.startswith('# ') or cmt.startswith('---'): break
                j += 1
            items.append(article)
            i = j
        else:
            i += 1

    total = min(5, len(items))
    print('\nGenerating detail pages (' + str(total) + ' items)...\n')
    detail_map = {}

    for idx, article in enumerate(items[:total]):
        title = article['title']
        url = article['url']
        rgn = {'US':'美国','CN':'中国','GB':'英国'}.get(article['region'], article['region'])
        pubdate = article['pubdate']
        desc = article.get('desc', '')
        newsapi_img = (article.get('image_url') or '').lstrip(':').strip()
        newsapi_content = article.get('content', '')
        source_name = article.get('source_name', '')

        print('[' + str(idx+1) + '/' + str(total) + '] ' + title[:50] + '...')

        # PRIMARY: NewsAPI image (urlToImage is the main article image)
        images = []
        if newsapi_img and newsapi_img.startswith('http'):
            images = [newsapi_img]
            print('  Image: NewsAPI (' + newsapi_img[:60] + '...)')
        else:
            print('  No NewsAPI image')

        # SECONDARY: try to fetch real article for text
        en_text = ''
        html = _fetch(url, timeout=15)
        if html:
            article_text = extract_article_text(html)
            if article_text and len(article_text) > 200:
                en_text = article_text
                print('  Text: ' + str(len(en_text)) + ' chars from article')
            else:
                print('  Text: short/paywall (' + str(len(article_text)) + ' chars)')

            # Fallback images from article (only if no NewsAPI image AND good content images available)
            if not images:
                page_imgs = extract_images_from_page(html)
                if page_imgs:
                    images = page_imgs
                    print('  Images: ' + str(len(images)) + ' from article page')
        else:
            print('  Could not fetch article')

        # Use NewsAPI content if article text too short
        if len(en_text) < 100:
            en_text = newsapi_content if newsapi_content else desc

        # LLM content generation
        cn_text = llm_article(title, desc, en_text)
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

