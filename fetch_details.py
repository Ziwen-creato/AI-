# -*- coding: utf-8 -*-
"""NewsAPI + ordered content extraction (text + images in original positions)."""
import os, re, json, time, urllib.request, urllib.parse, sys, ssl
import xml.etree.ElementTree as ET
from html import escape
from io import BytesIO
from datetime import datetime
from PIL import Image
from lxml.html import fromstring
sys.stdout.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

SRC = r'C:/AI编程/AI赚钱新闻收集/ai_reports'
OUT = r'C:/AI编程/AI赚钱新闻收集/html/details'
os.makedirs(OUT, exist_ok=True)
MAX_DETAILS = 20
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
LLM_URL = 'http://127.0.0.1:15721/v1/chat/completions'

SKIP_IMG = ['icon', 'logo', 'avatar', 'pixel', '1x1', 'spacer', 'tracking', 'analytics',
            '/ad/', '/ads/', '/banner/', '/leaderboard/', '/promo/', '/sponsor',
            'b2b3_', 'button336', 'btn_', '_ad_', 'advert', 'author', 'profile',
            'gravatar', 'emoji', 'smiley', 'placeholder', 'pixel.', 'loading.', 'spinner',
            'gstatic.com', 'news.google.com', 'google_news', '300x250', 'thumb',
            'nav-ad', 'tiny-ad', 'hamburger', 'exit-intent', 'newsletter', '150x150',
            'crop', 'gbr-standard', 'tax-resource', 'best-banks-26', 'untitled-design',
            'image-phone-newsletter', 'dave-ramsey', 'mark-cuban', 'grant-cardone',
            'laura-beck', 'financially-savvy', 'gen-z-the-future', 'best_banks_series',
            'trc-non-spons-nav', 'retire-anywhere-nav-ad']

NOISE_TOKENS = [
    'author', 'avatar', 'sidebar', 'widget', 'comment', 'footer', 'nav', 'header',
    'banner', 'advert', 'ad_', '_ad', '/ad/', 'ads', 'promo', 'sponsor',
    'related', 'stories', 'storybox', 'listing_wrapper', 'primestoryslider',
    'reltopics', 'raltedtopics', 'paywall', 'blocker', 'benefit', 'subscribe',
    'subscription', 'trial', 'share', 'social', 'logo', 'icon', 'carousel',
    'mpnews', 'external_widget', 'liveevent', 'sticky', 'fontsize', 'bookmark',
    'artprint', 'rating', 'whatsapp', 'newsletter', 'readmore', 'artshare',
    'insideind', 'topstories', 'storiesbox', 'carditem', 'listbox', 'listitem',
    'clustered', 'campign', 'freetrial', 'prime_paywall', 'defaultsticky',
    'silic-after-content', 'post-footer', 'author-bio',
]

BOILERPLATE = [
    'unlock access', 'subscribe to', 'subscribe now', 'sign in', 'already a member',
    'et prime', 'prime membership', 'free trial', 'trial offer', 'track latest',
    "what's moving sensex", 'whatsapp', 'read more news', 'support our mission',
    'founded by tech visionaries', 'keep me signed in', 'some subscribers prefer',
    'login', 'log out', 'stories you might', 'watch now', 'follow us',
    'etmarkets.com is now on telegram', 'sensex and nifty', 'budget 2025',
    'top trending stocks',
]

def _fetch(url, timeout=12, retries=2):
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')
        except: time.sleep(0.5)
    return None


def _resolve_google_news(url):
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname != 'news.google.com':
            return url
        parts = [part for part in parsed.path.split('/') if part]
        if len(parts) < 2 or parts[-2] not in ('articles', 'read'):
            return url
        token = parts[-1]
        page = None
        nodes = []
        for path in (
            'https://news.google.com/articles/',
            'https://news.google.com/rss/articles/',
        ):
            page = _fetch(path + token, timeout=15)
            if not page:
                continue
            tree = fromstring(page)
            nodes = tree.xpath('//c-wiz/div[@jscontroller]')
            if nodes:
                break
        if not nodes:
            return url
        signature = nodes[0].get('data-n-a-sg')
        timestamp = nodes[0].get('data-n-a-ts')
        if not signature or not timestamp:
            return url
        payload = [
            'Fbv4je',
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
            'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,'
            f'null,0],"{token}",{timestamp},"{signature}"]',
        ]
        body = 'f.req=' + urllib.parse.quote(json.dumps([[payload]]))
        req = urllib.request.Request(
            'https://news.google.com/_/DotsSplashUi/data/batchexecute',
            data=body.encode('utf-8'),
            headers={
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'User-Agent': UA,
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode('utf-8', errors='ignore')
        parsed_data = json.loads(raw.split('\n\n')[1])[:-2]
        decoded = json.loads(parsed_data[0][2])[1]
        if isinstance(decoded, str) and decoded.startswith('http'):
            print('    Resolved source: ' + decoded[:90])
            return decoded
    except Exception as exc:
        print('    Resolve error: ' + str(exc))
    return url


def _validate_image_url(src):
    try:
        req = urllib.request.Request(src, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=12) as response:
            content_type = (response.headers.get('Content-Type') or '').lower()
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            return False
        if content_type.startswith('image/webp') or content_type.startswith('image/avif'):
            return len(raw) >= 10000
        Image.MAX_IMAGE_PIXELS = 20000000
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
        return min(width, height) >= 120 and max(width, height) / min(width, height) <= 4.5
    except Exception:
        return False


def _fetch_jina_reader(source_url):
    for attempt, delay in enumerate((2, 5, 10), start=1):
        try:
            req = urllib.request.Request(
                'https://r.jina.ai/' + source_url,
                headers={'User-Agent': UA, 'Accept': 'text/plain,text/markdown'},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as exc:
            print('    Reader retry ' + str(attempt) + ': ' + str(exc))
            time.sleep(delay)
    return ''


def _fetch_bing_metadata(title, source_url=''):
    try:
        path_parts = [
            part for part in urllib.parse.urlparse(source_url).path.split('/')
            if part and not part.isdigit()
        ]
        slug = ''
        if path_parts:
            slug = re.sub(r'\.(?:html?|php|aspx?)$', '', path_parts[-1], flags=re.I)
            slug = re.sub(r'[^a-z0-9]+', ' ', slug, flags=re.I).strip()
        candidates = [slug, title, 'agentic ai monetization']
        for search_text in candidates:
            if not search_text:
                continue
            query = urllib.parse.quote(search_text[:500])
            url = (
                'https://www.bing.com/news/search?q=' + query
                + '&format=rss&setlang=en&cc=US&mkt=en-US'
            )
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 Chrome/129.0 Safari/537.36',
                },
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read().decode('utf-8', errors='ignore')
            root = ET.fromstring(raw)
            for item in root.findall('./channel/item'):
                image = ''
                description = item.findtext('description') or ''
                for element in item.iter():
                    tag = element.tag.rsplit('}', 1)[-1].lower()
                    if tag == 'image' and not image and element.text:
                        image = element.text.strip().replace('http://', 'https://')
                if image:
                    return image, description
    except Exception:
        pass
    return '', ''


def _markdown_to_ordered(markdown):
    if not markdown or any(
        token in markdown[:4000].lower()
        for token in ('403 error', 'request blocked', 'access denied', 'cloudflare')
    ):
        return [], []
    lines = markdown.splitlines()
    marker = None
    for idx, line in enumerate(lines):
        if line.strip() == 'Markdown Content:':
            marker = idx
            break
    if marker is None:
        return [], []
    start = marker + 1

    skip_headings = (
        'read next', 'premium investing services', 'about the motley fool',
        'related investing topics', 'market data powered', 'advertisement',
    )
    ordered = []
    all_images = []
    seen_images = set()
    paragraph = []
    skip_section = False
    heading_seen = False

    def flush_paragraph():
        text = ' '.join(part.strip() for part in paragraph if part.strip())
        text = re.sub(r'\s+', ' ', text).strip()
        if text and len(text) >= 20:
            ordered.append({'type': 'text', 'content': text})
        paragraph.clear()

    def add_images(line):
        for src in re.findall(r'!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)', line):
            src = src.split('?')[0]
            if src in seen_images:
                continue
            lower = src.lower()
            if any(token in lower for token in SKIP_IMG):
                continue
            looks_like_image = bool(re.search(r'\.(?:jpe?g|png|webp|gif|avif)(?:$|[?#])', lower))
            if not looks_like_image and not _validate_image_url(src):
                continue
            seen_images.add(src)
            all_images.append(src)
            ordered.append({'type': 'image', 'src': src})
            if len(all_images) >= 8:
                return

    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if not heading_seen:
            add_images(stripped)
            if not (stripped.startswith('# ') or stripped.startswith('## ')):
                continue
            heading_seen = True
        if stripped.startswith('## ') or stripped.startswith('# '):
            flush_paragraph()
            heading = re.sub(r'[#*_`]+', '', stripped).strip()
            skip_section = any(item in heading.lower() for item in skip_headings)
            if not skip_section:
                ordered.append({
                    'type': 'heading',
                    'content': heading,
                    'level': 1 if stripped.startswith('# ') else 2,
                })
            continue
        if skip_section:
            continue
        if re.fullmatch(r'\[[^\]]+\]\([^)]+\)', stripped):
            continue
        add_images(stripped)
        clean = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', stripped)
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
        clean = re.sub(r'[*_`#>]+', '', clean)
        paragraph.append(clean)
    flush_paragraph()
    return ordered, all_images

def _class_xpath(cls):
    return "contains(concat(' ', normalize-space(@class), ' '), ' " + cls + " ')"

def _classes(el):
    return ((el.get('class') or '') + ' ' + (el.get('id') or '')).lower()

def _has_noise_el(el):
    hay = _classes(el)
    return any(tok in hay for tok in NOISE_TOKENS)

def _has_noise_ancestor(el, root):
    p = el.getparent()
    while p is not None and p is not root:
        if _has_noise_el(p):
            return True
        p = p.getparent()
    return False

def _has_ancestor_class(el, cls):
    p = el.getparent()
    while p is not None:
        if cls in _classes(p):
            return True
        p = p.getparent()
    return False

def _find_content_root(tree):
    body = tree.find('body')
    if body is None:
        body = tree
    xpaths = [
        "//*[" + _class_xpath('ct-prose') + " and not(" + _class_xpath('ct-prose-disclaimer') + ")]",
        "//*[" + _class_xpath('news-content-frame') + "]",
        "//article[" + _class_xpath('artData') + "]",
        "//div[" + _class_xpath('single-post-content') + "]",
        "//div[" + _class_xpath('post-content') + "]",
        "//div[" + _class_xpath('entry-content') + "]",
        "//div[" + _class_xpath('article-content') + "]",
        "//div[" + _class_xpath('article-body') + "]",
        "//main",
    ]
    for xp in xpaths:
        try:
            els = tree.xpath(xp)
        except Exception:
            els = []
        best = None
        best_score = (0, 0, 0)
        for el in els:
            if el is body:
                continue
            txt = (el.text_content() or '').strip()
            if len(txt) < 400:
                continue
            score = (len(txt), len(el.xpath('.//p')), len(el.xpath('.//img')))
            if score > best_score:
                best_score = score
                best = el
        if best is not None and best_score[0] >= 400:
            return best
    return body if body is not None else tree

def _resolve_src(src, base_url):
    src = src.lstrip(':').strip()
    if src.startswith('//'):
        return 'https:' + src
    if src.startswith(('http://', 'https://', 'data:')):
        return src
    if base_url:
        return urllib.parse.urljoin(base_url, src)
    return src

def _image_signature(src):
    m = re.search(r'msid-?(\d+)', src, re.I)
    if m:
        return ('msid', m.group(1))
    path = urllib.parse.urlparse(src).path.rstrip('/').lower()
    path = re.sub(r'-\d+x\d+(?:-\d+)?(?=\.[a-z0-9]+$)', '', path, flags=re.I)
    path = re.sub(r'-(?:thumb|small|medium|large)(?=\.[a-z0-9]+$)', '', path, flags=re.I)
    return ('path', path)

def _same_image(a, b):
    return _image_signature(a) == _image_signature(b)

def _img_src(img, base_url=''):
    for attr in ('src', 'data-src', 'data-lazy-src', 'data-original', 'data-url', 'data-image'):
        v = (img.get(attr) or '').strip()
        if v:
            return _resolve_src(v, base_url)
    for attr in ('srcset', 'data-srcset'):
        v = (img.get(attr) or '').strip()
        if v:
            parts = [p.strip() for p in v.split(',') if p.strip()]
            if parts:
                return _resolve_src(parts[-1].split(' ')[0], base_url)
    return ''

def _valid_img(img, root, base_url=''):
    src = _img_src(img, base_url)
    if not src or src.startswith('data:'):
        return None
    lower = src.lower()
    if any(s in lower for s in SKIP_IMG):
        return None
    if 'google' in lower and 'googleusercontent' not in lower:
        return None
    if _has_noise_el(img) or _has_noise_ancestor(img, root):
        return None
    if 'economictimes.indiatimes.com' in (base_url or '') and _has_ancestor_class(img, 'artimg'):
        return None
    w = img.get('width', '')
    h = img.get('height', '')
    if w and h and w.isdigit() and h.isdigit():
        wi, hi = int(w), int(h)
        if wi < 80 or hi < 80:
            return None
        if wi / max(hi, 1) > 6 or hi / max(wi, 1) > 6:
            return None
    return src

def _hero_images(tree, root, base_url=''):
    images = []
    root_srcs = [src for img in root.xpath('.//img') if (src := _valid_img(img, root, base_url))]
    for xp in [
        "//*[" + _class_xpath('single-post-thumbnail') + "]//img",
        "//*[" + _class_xpath('article-cover') + "]//img",
        "//*[" + _class_xpath('post-thumbnail') + "]//img",
        "//*[" + _class_xpath('main-photo') + "]//img",
        "//figure[" + _class_xpath('artImg') + "]//img",
        "//*[" + _class_xpath('hero') + "]//img",
    ]:
        for img in tree.xpath(xp):
            if img in root.xpath('.//img'):
                continue
            src = _valid_img(img, root, base_url)
            if src and _validate_image_url(src):
                images.append(src)
    if not images:
        for meta in tree.xpath("//meta[@property='og:image'] | //meta[@name='twitter:image']"):
            src = (meta.get('content') or '').strip()
            if src:
                resolved = _resolve_src(src, base_url)
                if _validate_image_url(resolved):
                    images.append(resolved)
    seen = set()
    out = []
    for src in images:
        if src in seen or any(_same_image(src, r) for r in root_srcs if r):
            continue
        seen.add(src)
        out.append(src)
    return out

def _split_long_text(text):
    text = text.strip()
    if len(text) <= 1200:
        return [text] if text else []
    pieces = re.split(r'(?<=[.!?])\s+|\n+', text)
    blocks = []
    current = ''
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if len(current) + len(piece) < 700:
            current = (current + ' ' + piece).strip()
        else:
            if current:
                blocks.append(current)
            current = piece
    if current:
        blocks.append(current)
    return blocks

def _root_starts_with_image(root, base_url=''):
    for el in root.iter():
        tag = str(el.tag).lower() if hasattr(el, 'tag') else ''
        if tag == 'img' and _valid_img(el, root, base_url):
            return True
        if tag in ('p', 'h2', 'h3', 'h4', 'blockquote', 'pre'):
            text = el.text_content().strip()
            if len(text) >= 20:
                return False
        elif tag == 'div' and 'arttext' in _classes(el):
            if len(el.text_content().strip()) >= 80:
                return False
    return False

def extract_ordered_content(html, base_url=''):
    """Extract article content in DOM order: paragraphs and images interleaved."""
    if not html or len(html) < 500:
        return [], []

    try:
        from lxml.html import fromstring
        tree = fromstring(html)
    except:
        return [], []

    content_root = _find_content_root(tree)
    if content_root is None:
        return [], []

    # Remove noise within the selected article container
    for tag in ['script', 'style', 'nav', 'aside', 'noscript', 'form', 'iframe', 'svg', 'template']:
        for el in content_root.xpath('.//' + tag):
            try: el.getparent().remove(el)
            except: pass
    for el in list(content_root.xpath('.//*')):
        if el is not content_root and _has_noise_el(el):
            try: el.getparent().remove(el)
            except: pass

    ordered = []
    all_images = []
    seen_texts = set()
    seen_images = set()

    for el in content_root.iter():
        tag = str(el.tag).lower() if hasattr(el, 'tag') else ''

        if tag == 'img':
            src = _valid_img(el, content_root, base_url)
            if not src or src in seen_images:
                continue
            seen_images.add(src)
            all_images.append(src)
            ordered.append({"type": "image", "src": src})

        elif tag == 'div' and 'arttext' in _classes(el):
            if _has_noise_el(el) or _has_noise_ancestor(el, content_root):
                continue
            for block in _split_long_text(el.text_content().strip()):
                low = block.lower()
                if len(block) < 80 or any(b in low for b in BOILERPLATE) or block in seen_texts:
                    continue
                seen_texts.add(block)
                ordered.append({"type": "text", "content": block})

        elif tag in ('h2', 'h3', 'h4'):
            if _has_noise_el(el) or _has_noise_ancestor(el, content_root):
                continue
            text = el.text_content().strip()
            if len(text) < 3 or text in seen_texts:
                continue
            seen_texts.add(text)
            ordered.append({
                'type': 'heading',
                'content': text,
                'level': int(tag[1]),
            })

        elif tag in ('p', 'blockquote', 'pre'):
            if _has_noise_el(el) or _has_noise_ancestor(el, content_root):
                continue
            text = el.text_content().strip()
            if len(text) < 20:
                continue
            low = text.lower()
            if any(b in low for b in BOILERPLATE):
                continue
            links = el.xpath('.//a')
            link_text = sum(len(a.text_content()) for a in links if a.text_content())
            if link_text and link_text / len(text) > 0.8:
                continue
            if text in seen_texts:
                continue
            seen_texts.add(text)
            ordered.append({"type": "text", "content": text})

    if not _root_starts_with_image(content_root, base_url):
        for hero in _hero_images(tree, content_root, base_url):
            if hero not in seen_images:
                seen_images.add(hero)
                all_images.insert(0, hero)
                ordered.insert(0, {"type": "image", "src": hero})
                break

    text_count = sum(1 for o in ordered if o["type"] == "text")
    img_count = sum(1 for o in ordered if o["type"] == "image")
    print(f'    Ordered: {text_count} texts, {img_count} images')
    return ordered, all_images

def merge_translation_with_ordered(ordered, paragraphs):
    """Replace text blocks while keeping images near their original positions."""
    paras = [p for p in paragraphs if p and p.strip()]
    if not paras:
        return ordered
    text_items = [o for o in ordered if o['type'] == 'text']
    anchor_items = [o for o in ordered if o['type'] != 'text']
    if not text_items:
        return [{'type': 'text', 'content': paras[0]}] + anchor_items

    n = len(text_items)
    m = len(paras)
    slots = []
    before = 0
    for o in ordered:
        if o['type'] != 'text':
            ratio = before / n
            slots.append((int(ratio * m + 0.5), o))
        else:
            before += 1

    result = []
    pi = 0
    for slot, anchor in slots:
        while pi < min(slot, m):
            result.append({'type': 'text', 'content': paras[pi]})
            pi += 1
        result.append(anchor)
    while pi < m:
        result.append({'type': 'text', 'content': paras[pi]})
        pi += 1
    return result

def trim_incomplete_tail(items):
    """Drop a trailing AI paragraph that was cut off before a sentence ended."""
    items = list(items)
    while items and items[-1]['type'] == 'text':
        text = items[-1]['content'].strip()
        if text and text[-1] in '。！？…’"”』」）.!?…':
            break
        items.pop()
    return items

def llm_article(title, description, article_text):
    has_full = len(article_text) > 200
    if has_full:
        prompt = '请将以下英文新闻翻译成流畅自然的中文新闻稿。保持原文的段落数量，每个段落用两个换行分隔。直接输出中文。\n\n标题：' + title + '\n英文原文：\n' + article_text[:5000] + '\n\n中文翻译：'
    else:
        prompt = '你是资深中文财经编辑。根据以下线索写一篇完整中文新闻稿（4-6段，每个段落用两个换行分隔，600-1000字）。直接输出中文。\n\n标题：' + title + '\n线索：' + description[:800] + '\n\n中文新闻稿：'
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

def machine_translate(text):
    """Translate a text chunk through the public Google Translate endpoint."""
    url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=' + urllib.parse.quote(text)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))
    parts = []
    for seg in data[0]:
        if seg and seg[0]:
            parts.append(seg[0])
    return ''.join(parts)

def full_machine_translate(text):
    """Translate the full text in chunks while preserving paragraph breaks."""
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current = ''
    for p in paras:
        if len(current) + len(p) + 2 > 2800 and current:
            chunks.append(current)
            current = p
        else:
            current = (current + '\n\n' + p).strip()
    if current:
        chunks.append(current)

    translated = []
    for chunk in chunks:
        for attempt in range(2):
            try:
                translated.append(machine_translate(chunk))
                break
            except Exception as e:
                if attempt == 1:
                    raise
                time.sleep(0.5)
    return '\n\n'.join(translated)

def translate_article_full(title, description, article_text):
    """Use machine translation for full text, with local LLM as fallback."""
    if len(article_text) > 100:
        try:
            cn = full_machine_translate(article_text)
            if cn and len(cn.strip()) > 20:
                return cn
        except Exception as e:
            print('    Machine translate error: ' + str(e))
    return llm_article(title, description, article_text)


DISPLAY_TEXT_ZH = {
    "Google Just Shared the Easiest Way to Start a Side Hustle With AI": "谷歌刚刚分享了利用人工智能开展副业的最简单方法",
    "At Age 16, He Started a Side Hustle That Hit $150K in Under a Year. He Used Amazon and ChatGPT to ‘Rinse and Repeat’ Sales.": "16 岁时他开启副业，一年内收入 15 万美元；他使用亚马逊和聊天生成模型重复销售",
    "I Asked ChatGPT How Retirees Can Generate $2K Monthly in Passive Income in 2026: Here’s What It Recommended": "我问聊天生成模型，退休人员如何在 2026 年每月获得 2000 美元被动收入，以下是它的建议",
    "I Asked ChatGPT To Build a $500 a Month Passive Income Stream — Here's the Exact Plan It Gave Me": "我问聊天生成模型如何每月获得 500 美元被动收入，以下是它给出的具体计划",
    "ChatGPT": "聊天生成模型",
    "Claude": "克劳德",
    "FTC": "美国联邦贸易委员会",
    "AI": "人工智能",
}


def translate_display_text(text):
    text = (text or '').strip()
    for english, chinese in DISPLAY_TEXT_ZH.items():
        text = text.replace(english, chinese)
    if not any('a' <= ch <= 'z' or 'A' <= ch <= 'Z' for ch in text):
        return text
    try:
        translated = machine_translate(text)
        if translated and translated != text:
            return translated.strip()
    except Exception:
        pass
    return text


def localize_ordered_items(items):
    for item in items:
        if item.get('type') == 'heading':
            item['content'] = translate_display_text(item['content'])
    return items

def gen_page_ordered(title, source_url, region, pubdate, ordered_items, en_text='', content_notice=''):
    """Generate detail page with images at their original paragraph positions."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    pub_str = (pubdate or '')[:19]

    body_html = ''
    for item in ordered_items:
        if item["type"] == "image":
            img_src = escape(item["src"], quote=True)
            body_html += (
                '<figure style="margin:26px 0;text-align:center;">'
                '<img src="' + img_src + '" style="max-width:100%;height:auto;border-radius:8px;'
                'background:#f1f5f9;" alt="" loading="lazy" '
                "onerror=\"this.style.display='none'\"/></figure>\n"
            )
        elif item["type"] == "heading":
            level = min(max(int(item.get("level", 2)), 2), 3)
            if level == 2:
                style = 'font-size:24px;line-height:1.45;margin:30px 0 10px;font-weight:800;color:#0f172a;'
            else:
                style = 'font-size:20px;line-height:1.5;margin:24px 0 8px;font-weight:700;color:#111827;'
            body_html += '<h' + str(level) + ' style="' + style + '">' + escape(item["content"]) + '</h' + str(level) + '>\n'
        else:
            body_html += (
                '<p style="font-size:18px;color:#334155;line-height:1.9;'
                'margin:16px 0;">' + escape(item["content"]) + '</p>\n'
            )

    partial_notice = ''
    if en_text and len(en_text.strip()) < 200:
        partial_notice = '<p style="font-size:13px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 12px;margin:16px 0;line-height:1.6;">该来源为付费内容，当前只能获取到开头，新闻正文不完整。</p>\n'

    notice_html = ''
    if content_notice:
        notice_html = (
            '<div style="margin:18px 0;padding:12px 14px;background:#fffbeb;'
            'border-left:4px solid #f59e0b;color:#92400e;font-size:14px;line-height:1.7;">'
            + escape(content_notice) + '</div>\n'
        )

    en_section = ''
    if en_text and len(en_text.strip()) > 50:
        en_section = '<details style="margin-top:20px;padding:14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"><summary style="font-size:13px;color:#64748b;cursor:pointer;">英文原文（全文）</summary><p style="font-size:14px;color:#64748b;line-height:1.8;margin:10px 0 0;white-space:pre-wrap;">' + escape(en_text) + '</p></details>\n'

    safe_url = escape(source_url, quote=True)
    css = (
        '<style>*{margin:0;padding:0;box-sizing:border-box}'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;'
        'background:#fff;color:#334155;padding:20px 16px 40px;line-height:1.75}'
        'main{max-width:640px;margin:0 auto;padding:0}'
        'h1{font-size:30px;line-height:1.4;color:#0f172a;margin:12px 0;font-weight:800}'
        '.meta{font-size:13px;color:#64748b;padding-bottom:16px;border-bottom:1px solid #e2e8f0;'
        'margin-bottom:8px;display:flex;flex-wrap:wrap;gap:8px 18px}'
        'h2,h3{color:#0f172a}'
        'p{font-size:17px;line-height:1.85;color:#334155;margin:14px 0}'
        'figure{overflow:hidden;margin:26px 0}'
        'img{max-width:100%;height:auto;display:block;border-radius:8px}'
        '.back{display:inline-block;margin-top:28px;color:#2563eb;text-decoration:none;'
        'font-size:15px;font-weight:600}'
        '.source{margin-top:20px;font-size:12px;color:#94a3b8;padding-top:14px;'
        'border-top:1px solid #e2e8f0}'
        '.source a{color:#64748b;word-break:break-all;text-decoration:none}'
        '@media(max-width:600px){body{padding:16px 12px 32px}h1{font-size:26px}p{font-size:16px;line-height:1.8}}'
        '</style>'
    )
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>' + escape(title) + '</title>\n' + css + '\n</head>\n<body>\n<main>\n'
        '<h1>' + escape(title) + '</h1>\n'
        '<div class="meta"><span>' + region + '</span><span>' + pub_str + '</span><span>生成于 ' + now + '</span></div>\n'
        + body_html + '\n' + partial_notice + notice_html + en_section
        + '<div class="source">原文来源：<a href="' + safe_url + '">查看原文</a></div>\n'
        '<a href="javascript:history.back()" class="back">&larr; 返回</a>\n</main>\n</body>\n</html>'
    )

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
                elif cmt.startswith('<!-- SRC:'): article['source_name'] = cmt[8:-3].strip().lstrip(':')
                elif cmt.startswith('- [') or cmt.startswith('# ') or cmt.startswith('---'): break
                j += 1
            items.append(article)
            i = j
        else:
            i += 1

    total = min(MAX_DETAILS, len(items))
    print('\nGenerating ordered detail pages (' + str(total) + ' items)...\n')
    detail_map = {}
    map_path = os.path.join(OUT, 'detail_map.json')
    if os.path.exists(map_path):
        with open(map_path, 'r', encoding='utf-8') as map_file:
            detail_map = json.load(map_file)

    selected_items = list(enumerate(items[:total]))
    if len(sys.argv) > 1:
        selected_ids = {int(arg) for arg in sys.argv[1:]}
        selected_items = [
            pair for pair in selected_items if pair[0] in selected_ids
        ]

    for idx, article in selected_items:
        title = article['title']
        display_title = translate_display_text(title)
        url = article['url']
        rgn = {'US':'美国','CN':'中国','GB':'英国'}.get(article['region'], article['region'])
        pubdate = article['pubdate']
        desc = article.get('desc', '')
        newsapi_img = (article.get('image_url') or '').lstrip(':').strip()
        newsapi_content = article.get('content', '')
        source_name = article.get('source_name', '')
        content_notice = ''

        print('[' + str(idx+1) + '/' + str(total) + '] ' + display_title[:50] + '...')

        ordered = None
        all_imgs = []
        en_text = ''
        source_url = _resolve_google_news(url)
        html = _fetch(source_url, timeout=15)
        if html:
            ordered, all_imgs = extract_ordered_content(html, source_url)
            # Collect all text for LLM
            texts = [o["content"] for o in ordered if o["type"] == "text"]
            en_text = '\n\n'.join(texts) if texts else ''

        direct_images = list(all_imgs)
        direct_text_count = sum(1 for item in (ordered or []) if item.get('type') == 'text')
        reader_used = False
        if not ordered or direct_text_count < 3 or len(en_text) < 700:
            reader_markdown = _fetch_jina_reader(source_url)
            reader_ordered, reader_images = _markdown_to_ordered(reader_markdown)
            reader_text_count = sum(
                1 for item in reader_ordered if item.get('type') == 'text'
            )
            if reader_ordered and reader_text_count >= 2:
                reader_used = True
                if not reader_images and direct_images:
                    first_text = next(
                        (
                            index
                            for index, item in enumerate(reader_ordered)
                            if item.get('type') == 'text'
                        ),
                        0,
                    )
                    for offset, src in enumerate(direct_images[:3]):
                        position = min(len(reader_ordered), first_text + 1 + offset * 2)
                        reader_ordered.insert(position, {'type': 'image', 'src': src})
                    reader_images = direct_images[:3]
                ordered = reader_ordered
                all_imgs = reader_images
                reader_texts = [
                    item['content'] for item in ordered if item['type'] == 'text'
                ]
                en_text = '\n\n'.join(reader_texts)
                print(
                    '  Reader fallback: '
                    + str(reader_text_count)
                    + ' texts, '
                    + str(len(reader_images))
                    + ' images'
                )

        if not reader_used and direct_text_count < 2 and len(en_text.strip()) < 300:
            content_notice = '该文章来源设置了访问限制或付费墙，当前无法获取完整原文；以下内容为基于已有信息的自动生成摘要。'

        if not ordered or not any(o["type"] == "text" for o in ordered):
            print('  Using fallback layout')
            if direct_text_count == 0:
                all_imgs = []
            ordered = None

        if not all_imgs:
            bing_image, bing_description = _fetch_bing_metadata(title, source_url)
            if bing_image:
                all_imgs = [bing_image]
            if bing_description and not desc:
                desc = bing_description

        # Generate Chinese content
        context = en_text if len(en_text) > 100 else (newsapi_content + '\n\n' + desc)
        cn_text = translate_article_full(title, desc, context)

        if ordered and cn_text and len(cn_text) > 20:
            cn_paras = [p.strip() for p in cn_text.split('\n\n') if p.strip()]
            if len(cn_paras) < 2:
                cn_paras = [p.strip() for p in cn_text.split('\n') if p.strip() and len(p.strip()) > 15]
            merged = merge_translation_with_ordered(ordered, cn_paras)
            merged = trim_incomplete_tail(merged)
            merged = localize_ordered_items(merged)
            print('  CN: ' + str(len(cn_text)) + ' chars, images kept in original order')
            page = gen_page_ordered(display_title, source_url, rgn, pubdate, merged, en_text if en_text else '', content_notice)
        elif ordered:
            fallback_text = en_text.strip() if len(en_text.strip()) > 100 else desc
            fallback_paras = [p.strip() for p in fallback_text.split('\n\n') if p.strip()]
            if not fallback_paras:
                fallback_paras = [fallback_text or title]
            merged = merge_translation_with_ordered(ordered, fallback_paras)
            merged = localize_ordered_items(merged)
            print('  LLM failed/fallback, images kept in original order')
            page = gen_page_ordered(display_title, source_url, rgn, pubdate, merged, en_text if en_text else '', content_notice)
        elif cn_text and len(cn_text) > 20:
            # Fallback: no ordered content, use traditional layout
            cn_paras = [p.strip() for p in cn_text.split('\n\n') if p.strip()]
            simple_ordered = [{"type": "text", "content": p} for p in cn_paras]
            # Put images at top as fallback
            img_ordered = [{"type": "image", "src": img} for img in all_imgs[:5]]
            if newsapi_img and newsapi_img.startswith('http') and newsapi_img not in all_imgs:
                img_ordered.insert(0, {"type": "image", "src": newsapi_img})
            # Interleave: image after every 2 paras
            result_ordered = []
            pi = 0
            for img_item in img_ordered:
                # Add up to 2 paragraphs before each image
                added = 0
                while pi < len(simple_ordered) and added < 2:
                    result_ordered.append(simple_ordered[pi])
                    pi += 1
                    added += 1
                result_ordered.append(img_item)
            # Remaining paragraphs
            while pi < len(simple_ordered):
                result_ordered.append(simple_ordered[pi])
                pi += 1
            if not img_ordered:
                result_ordered = simple_ordered
            print('  CN: ' + str(len(cn_text)) + ' chars, interleaved layout')
            page = gen_page_ordered(display_title, source_url, rgn, pubdate, result_ordered, en_text if en_text else '', content_notice)
        else:
            print('  LLM failed, using description')
            simple = [{"type": "text", "content": desc if desc else display_title}]
            page = gen_page_ordered(display_title, source_url, rgn, pubdate, simple, en_text if en_text else '', content_notice)

        detail_name = 'detail_' + format(idx, '03d') + '.html'
        with open(os.path.join(OUT, detail_name), 'w', encoding='utf-8') as f:
            f.write(page)
        detail_map[str(idx)] = detail_name
        time.sleep(0.5)

    with open(os.path.join(OUT, 'detail_map.json'), 'w', encoding='utf-8') as f:
        json.dump(detail_map, f, ensure_ascii=False, indent=2)
    print('\nDone! ' + str(total) + ' detail pages.\n')

if __name__ == '__main__':
    main()


