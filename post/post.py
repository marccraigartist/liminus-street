"""LIMINUS STREET on Instagram (@liminus.street).

Once an hour the poster wakes, asks Instagram which tunnel hour it posted last, and posts the next hours that have
already happened, oldest first, as a 9-slide carousel: the whole tunnel, then the 8 walls (bays 1-4 wall A, then wall X).
It never chooses or changes anything: it shows each hour exactly as the tunnel painted it.

  python post/post.py plan  OUT_DIR [MAX]   decide which hours to post, render their slides, write OUT_DIR/plan.json
  python post/post.py publish OUT_DIR BASE_URL   post the planned hours (slides must be live at BASE_URL/<stamp>/<n>.jpg)

Needs IG_TOKEN (system-user token) in the environment for both steps.
"""
import sys, os, json, time, re, calendar, urllib.request, urllib.parse, urllib.error
from PIL import Image, ImageDraw, ImageFont

IG_USER = '17841464423884734'                  # @liminus.street
GRAPH = 'https://graph.facebook.com'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, 'post', 'fonts')
FIRST_HOUR = '2026-11-01T19'                   # the tunnel's first hour
RESUME_AFTER = '2026-11-04T09'                 # Instagram rest after its new-account block (2 Nov); nothing posts before this
W, H, BG = 1080, 1350, (11, 11, 13)
SEG_W, SEG_H, ROW_A, ROW_X = 1200, 550, 0, 574  # wall + its wet-floor reflection, as painted in each hour image
TAGS = '#liminusstreet #graffiti #streetart #generativeart #artificiallife #graffitiart #leakestreet #autonomousart'
LINE = re.compile(r'LIMINUS STREET · (\d{4}-\d{2}-\d{2}) (\d{2}):00 UTC')

def font(size, bold=False):
    return ImageFont.truetype(os.path.join(FONTS, 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)

def ts(stamp): return calendar.timegm(time.strptime(stamp, '%Y-%m-%dT%H'))
def when(stamp): return f'{stamp[:10]} {stamp[11:]}:00 UTC'

# ------------------------------------------------------------------ Instagram
def api(method, path, **params):
    params['access_token'] = os.environ['IG_TOKEN']
    data = urllib.parse.urlencode(params).encode()
    url = f'{GRAPH}/{path}'
    req = urllib.request.Request(url + ('?' + data.decode() if method == 'GET' else ''), data=None if method == 'GET' else data, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            if e.code >= 500 and attempt < 3: time.sleep(10 * (attempt + 1)); continue
            raise SystemExit(f'Instagram said {e.code} on {method} {path}: {body}')
        except urllib.error.URLError as e:
            if attempt < 3: time.sleep(10 * (attempt + 1)); continue
            raise SystemExit(f'could not reach Instagram: {e}')

def last_posted():
    """the newest tunnel hour already on the account, read from the first caption line of recent posts"""
    got = api('GET', f'{IG_USER}/media', fields='caption', limit=50)
    best = None
    for m in got.get('data', []):
        mt = LINE.search(m.get('caption') or '')
        if mt:
            s = f'{mt.group(1)}T{mt.group(2)}'
            if best is None or s > best: best = s
    return best

# ------------------------------------------------------------------ slides (format A: tall 4:5, text on the slide)
def card(seg, top, sub):
    c = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(c)
    s = seg.resize((W, round(seg.height * W / seg.width)), Image.LANCZOS)
    c.paste(s, (0, (H - s.height) // 2))
    d.text((48, 64), 'LIMINUS STREET', font=font(34, True), fill=(217, 216, 208))
    d.text((48, 112), top, font=font(28), fill=(232, 226, 200))
    d.text((48, H - 150), sub, font=font(26), fill=(160, 158, 150))
    return c

def names_line(ws, width=62):
    s = '  '.join(w['name'] for w in ws) or 'bare concrete'
    return s if len(s) <= width else s[:width - 1] + '…'

def render(hour, out):
    os.makedirs(out, exist_ok=True)
    im = Image.open(os.path.join(ROOT, hour['image'])).convert('RGB')
    gen = max(0, hour.get('generation', 0))
    card(im, f"{when(hour['hour'])}  ·  generation {gen}", 'the whole tunnel  ·  swipe for the 8 walls').save(os.path.join(out, '0.jpg'), quality=90)
    k = 1
    for body, y0 in (('A', ROW_A), ('X', ROW_X)):
        for b in range(4):
            seg = im.crop((b * SEG_W, y0, (b + 1) * SEG_W, y0 + SEG_H))
            ws = (hour.get('walls') or {}).get(f'{b + 1}{body}', [])
            card(seg, f"BAY {b + 1}  ·  WALL {body}  ·  {when(hour['hour'])}", names_line(ws)).save(os.path.join(out, f'{k}.jpg'), quality=90)
            k += 1
    return k

def caption(hour):
    gen = max(0, hour.get('generation', 0))
    L = [f"LIMINUS STREET · {when(hour['hour'])} · generation {gen}", '']
    for body in 'AX':
        for b in range(4):
            ws = (hour.get('walls') or {}).get(f'{b + 1}{body}', [])
            L.append(f'Bay {b + 1} · Wall {body}: ' + (', '.join(w['name'] + (' (gone over by Joe)' if w.get('joe') else '') for w in ws) or 'bare concrete'))
    L += ['', 'An autonomous graffiti tunnel painted by writers made only of maths. No human steering. A new hour every hour.', '', TAGS]
    return '\n'.join(L)[:2200]

# ------------------------------------------------------------------ steps
def plan(out, max_n=1, mode='latest'):
    man = json.load(open(os.path.join(ROOT, 'hours.json')))
    now = time.time()
    last = last_posted() or ''
    due = [h for h in man['hours'] if h['hour'] >= FIRST_HOUR and h['hour'] > last and ts(h['hour']) <= now]
    if now < ts(RESUME_AFTER): due = []        # still resting
    due = due[-1:] if mode == 'latest' else due[:max_n]   # 'latest': only the hour that has just arrived
    os.makedirs(out, exist_ok=True)
    for h in due: render(h, os.path.join(out, h['hour']))
    json.dump([dict(hour=h['hour'], caption=caption(h)) for h in due], open(os.path.join(out, 'plan.json'), 'w'), indent=1)
    print('last posted:', last or 'nothing yet', '| posting:', [h['hour'] for h in due] or 'nothing due')

def wait_live(url, tries=30):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=20) as r:
                if r.status == 200: return
        except Exception: pass
        time.sleep(10)
    raise SystemExit(f'slide never went live: {url}')

def wait_ready(cid, tries=30):
    for _ in range(tries):
        st = api('GET', cid, fields='status_code').get('status_code')
        if st == 'FINISHED': return
        if st in ('ERROR', 'EXPIRED'): raise SystemExit(f'Instagram could not process {cid}: {st}')
        time.sleep(5)
    raise SystemExit(f'Instagram took too long on {cid}')

def publish(out, base):
    todo = json.load(open(os.path.join(out, 'plan.json')))
    for p in todo:
        if (last_posted() or '') >= p['hour']: print('already on Instagram:', p['hour']); continue
        urls = [f"{base}/{p['hour']}/{k}.jpg" for k in range(9)]
        for u in urls: wait_live(u)
        kids = []
        for u in urls:
            kid = api('POST', f'{IG_USER}/media', image_url=u, is_carousel_item='true')['id']
            kids.append(kid)
        for kid in kids: wait_ready(kid)
        car = api('POST', f'{IG_USER}/media', media_type='CAROUSEL', children=','.join(kids), caption=p['caption'])['id']
        wait_ready(car)
        res = api('POST', f'{IG_USER}/media_publish', creation_id=car)
        print('posted', p['hour'], '->', res.get('id'))
        time.sleep(20)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'plan': plan(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1, sys.argv[4] if len(sys.argv) > 4 else 'latest')
    elif cmd == 'publish': publish(sys.argv[2], sys.argv[3].rstrip('/'))
    elif cmd == 'render':                      # local check without Instagram: render one hour's slides
        man = json.load(open(os.path.join(ROOT, 'hours.json')))
        h = next(x for x in man['hours'] if x['hour'] == sys.argv[3]); render(h, sys.argv[2]); print(caption(h))
