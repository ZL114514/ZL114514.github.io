#!/usr/bin/env python3
"""Sync the public Telegram channel preview (t.me/s/<channel>) into blog posts.

Idempotent: each post records a content hash in its front matter, so a re-run
leaves untouched posts (and any manual edits, including hand-fixed categories)
alone. Media is downloaded and recompressed into src/assets/tg/<id>/.

  python scripts/tg_sync.py --full        # first import / backfill everything
  python scripts/tg_sync.py               # incremental (stops at known ids)
"""
import argparse
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "src")
POSTS_DIR = os.path.join(SRC, "blog", "posts")
MEDIA_DIR = os.path.join(SRC, "assets", "tg")
STATE = os.path.join(REPO, "scripts", ".tg_state.json")
SITE_STATE = os.path.join(REPO, "scripts", "site_state.json")   # 后台状态快照（sitegen --pull 拉回）
CACHE = os.path.join(REPO, "scripts", "tg_posts.json")          # 抓取结果缓存（--from-cache 用，免二次抓 TG）
NOTES_DIR = os.path.join(SRC, "notes")
REVIEW = os.path.join(REPO, "scripts", "tg-review.md")
CH = "zlzlzl_ch"
CST = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0 Safari/537.36")
EMOJI_SET = ["👍", "❤", "😁", "🔥", "🥰", "😢"]
MAX_IMG_W = 1600
MAX_VIDEO_MB = 20
GROUP_WINDOW = 60   # 秒：与上一条间隔在此窗口内的连续帖合并成一篇（文字+媒体都并入）


def _dt(post):
    return datetime.fromisoformat(post["dt"])


def merge_groups(posts, window):
    """Merge bursts of consecutive messages into one pseudo post.

    Anything posted within `window` seconds of the previous message becomes one
    article — text *and* media, in the original order (that is how a same-moment
    burst reads on the web client). The merged post keeps the smallest message id
    as its key and remembers every original id.
    """
    groups, cur = [], []
    for p in posts:
        if cur and 0 <= (_dt(p) - _dt(cur[-1])).total_seconds() <= window:
            cur.append(p)
            continue
        if cur:
            groups.append(cur)
        cur = [p]
    if cur:
        groups.append(cur)
    merged = []
    for g in groups:
        if len(g) == 1:
            g[0]["ids"] = [g[0]["id"]]
            merged.append(g[0])
            continue
        head, rx = g[0], {}
        for x in g:
            for r in x["reactions"]:
                rx[r["emoji"]] = rx.get(r["emoji"], 0) + r["count"]
        views = (str(sum(int(x["views"]) for x in g)) if all((x["views"] or "").isdigit() for x in g)
                 else head["views"])
        merged.append({
            "id": head["id"], "ids": [x["id"] for x in g], "dt": head["dt"],
            "text": "\n\n".join(x["text"].strip() for x in g if x["text"].strip()),
            "photos": [u for x in g for u in x["photos"]],
            "videos": [v for x in g for v in x["videos"]],
            "docs": [d for x in g for d in x["docs"]],
            # 逐条保留顺序，render 按 parts 交叉排（每条的文字紧跟它自己的媒体）
            "parts": [{"text": x["text"].strip(), "n_photos": len(x["photos"]),
                       "videos": x["videos"], "docs": x["docs"], "link": x["link"]}
                      for x in g],
            "reactions": [{"emoji": k, "count": v} for k, v in rx.items()],
            "views": views, "link": head["link"], "merged": len(g),
        })
    return merged


# --- classification ---------------------------------------------------------
# 音游成绩: only keywords confident enough to auto-assign; everything else is
# 生活随想. Fixes belong in the post's own `categories:` (a re-run keeps them).
# 音游成绩: 只认足够确定的词（早期版本把 Android 源码里的"难度/曲目"也命中了），
# 其余一律 生活随想。图片型的成绩帖没法靠文字判，走 scripts/tg_category_overrides.json
# 或直接编辑帖子 md 的 `categories:`（重跑会保留）。
MUSIC_KEYS = [
    "音游", "maimai", "舞萌", "phigros", "arcaea", "cytus", "lanota", "chunithm",
    "音击", "舞立方", "osu!", "打歌", "收歌", "全连", "全连", "谱面", "定数",
    "rks", "音游狗", "曲包", "收掉了", "推分", "掉分", "断连",
]
MUSIC_KEYS_RE = re.compile("|".join(re.escape(k) for k in MUSIC_KEYS), re.I)
OVERRIDES_FILE = os.path.join(REPO, "scripts", "tg_category_overrides.json")

VOID = {"br", "img", "hr", "meta", "link", "input", "source"}


class Node:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.kids, self.parent = tag, attrs or {}, [], parent

    def cls(self):
        return (self.attrs.get("class") or "").split()

    def find(self, pred, deep=True):
        for k in self.kids:
            if isinstance(k, Node):
                if pred(k):
                    return k
                if deep:
                    r = k.find(pred, deep)
                    if r is not None:
                        return r
        return None

    def findall(self, pred, deep=True, out=None):
        out = [] if out is None else out
        for k in self.kids:
            if isinstance(k, Node):
                if pred(k):
                    out.append(k)
                if deep:
                    k.findall(pred, deep, out)
        return out


def by_class(name):
    return lambda n: name in n.cls()


class Dom(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, dict(attrs), self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def to_md(node):
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return "<br>"            # 裸 \n 会被 markdown 折成一行，用内联 <br> 保换行
    if node.tag == "img":
        return ""
    inner = "".join(to_md(k) for k in node.kids)
    t = node.tag
    if t in ("b", "strong"):
        # 用内联 HTML：TG 里常见"文字**😁**"这种紧贴写法，markdown 的 ** 不认，会露出星号
        return "<strong>%s</strong>" % inner if inner.strip() else inner
    if t in ("i", "em", "tg-emoji"):
        return inner
    if t in ("s", "strike", "del"):
        return "<del>%s</del>" % inner if inner.strip() else inner
    if t == "code":
        return "`%s`" % inner
    if t == "pre":
        return "\n```\n%s\n```\n" % inner.replace("<br>", "\n").strip("\n")
    if t == "a":
        href = node.attrs.get("href", "")
        return "[%s](%s)" % (inner, href) if inner.strip() else href
    if "spoiler" in node.cls():
        return "||%s||" % inner
    return inner


def text_of(n):
    return re.sub(r"\n{3,}", "\n\n", to_md(n)).strip()


def plain_of(n):
    """纯文本（不套 markdown 标记）——emoji 这种值必须用这个，否则会变成 **👍**。"""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        else:
            for k in x.kids:
                walk(k)

    walk(n)
    return "".join(out).strip()


def norm_emoji(e):
    """归一 emoji：去掉 markdown 加粗残留（**👍**）与变体选择符（❤️→❤），避免同一表情存成两个键。"""
    return (e or "").replace("*", "").replace("\ufe0f", "").strip()


def style_url(style):
    m = re.search(r"url\('([^']+)'\)", style or "")
    return m.group(1) if m else ""


def parse_page(page):
    dom = Dom()
    dom.feed(page)
    out = []
    for wrap in dom.root.findall(by_class("js-widget_message_wrap")):
        msg = wrap.find(lambda n: "js-widget_message" in n.cls() and "data-post" in n.attrs)
        if msg is None:
            msg = wrap.find(by_class("tgme_widget_message"))
        if msg is None:
            continue
        pid = (msg.attrs.get("data-post") or "").split("/")[-1]
        if not pid.isdigit():
            continue
        rec = {"id": int(pid), "text": "", "photos": [], "videos": [], "docs": [],
               "reactions": [], "views": None, "dt": None,
               "link": "https://t.me/%s/%s" % (CH, pid)}
        t = msg.find(by_class("js-message_text"))
        if t is not None:
            rec["text"] = text_of(t)
        for p in msg.findall(by_class("tgme_widget_message_photo_wrap")):
            u = style_url(p.attrs.get("style"))
            if not u:
                img = p.find(lambda n: n.tag == "img")
                u = img.attrs.get("src", "") if img else ""
            if u:
                rec["photos"].append(u if u.startswith("http") else "https:" + u)
        for v in msg.findall(lambda n: "js-message_video" in n.cls()):
            thumb = style_url(v.attrs.get("style"))
            if not thumb:
                img = v.find(lambda n: n.tag == "img")
                thumb = img.attrs.get("src", "") if img else ""
            dur = v.find(by_class("js-message_video_duration"))
            if thumb:
                rec["photos"].append(thumb if thumb.startswith("http") else "https:" + thumb)
            rec["videos"].append({"src": v.attrs.get("src", ""),
                                  "dur": text_of(dur) if dur is not None else ""})
        for d in msg.findall(by_class("tgme_widget_message_document")):
            title = d.find(by_class("tgme_widget_message_document_title"))
            extra = d.find(by_class("tgme_widget_message_document_extra"))
            rec["docs"].append({"name": text_of(title) if title is not None else "",
                                "size": text_of(extra) if extra is not None else ""})
        rx = msg.find(by_class("js-message_reactions"))
        if rx is not None:
            for sp in rx.findall(by_class("tgme_reaction")):
                b = sp.find(lambda n: n.tag == "b")
                emoji = norm_emoji(plain_of(b)) if b is not None else ""
                cnt = re.sub(r"\D", "", "".join(x for x in sp.kids if isinstance(x, str))) or "1"
                if emoji:
                    rec["reactions"].append({"emoji": emoji, "count": int(cnt)})
        v = msg.find(by_class("tgme_widget_message_views"))
        if v is not None:
            rec["views"] = text_of(v)
        tm = msg.find(lambda n: n.tag == "time" and n.attrs.get("datetime"))
        if tm is not None:
            rec["dt"] = tm.attrs["datetime"]
        out.append(rec)
    return out


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")


def scrape(full, known_ids):
    seen, before = {}, None
    for page_no in range(1, 300):
        url = "https://t.me/s/%s" % CH + ("?before=%d" % before if before else "")
        page = None
        for attempt in range(1, 4):
            try:
                page = fetch(url)
                break
            except Exception as e:
                print("  page %d 第 %d 次失败: %s" % (page_no, attempt, e))
                time.sleep(2 * attempt)
        if page is None:
            print("  !! page %d 连续失败，停止翻页（历史可能不完整）" % page_no)
            break
        msgs = parse_page(page)
        if not msgs:
            break
        fresh = [m for m in msgs if m["id"] not in seen]
        for m in fresh:
            seen[m["id"]] = m
        ids = [m["id"] for m in msgs]
        print("  page %-3d %d..%d  new=%d" % (page_no, min(ids), max(ids), len(fresh)))
        if min(ids) <= 1:
            break
        if not full and known_ids and min(ids) in known_ids:
            print("  已追上已知帖子，停止翻页")
            break
        before = min(ids)
        time.sleep(0.7)
    return [seen[k] for k in sorted(seen)]


RENDER_V = "r5"   # 渲染器版本：只改 render()/front matter 时把它 +1，否则帖子 hash 不变、老帖不会被重写


def sha(post, extra=""):
    """内容哈希。extra 用来把后台状态（碎碎念/博文/成绩/隐藏）也拌进去：
    后台改一次状态，这一篇就必须重写一次。"""
    raw = json.dumps([RENDER_V, post["id"], post["dt"], post["text"], post["photos"],
                      post["videos"], post["docs"], extra], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _load_overrides():
    try:
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            return {str(k): v for k, v in json.load(f).items()}
    except Exception:
        return {}


_OVER = _load_overrides()


def classify(post):
    for pid in post.get("ids", [post["id"]]):
        if str(pid) in _OVER:
            return _OVER[str(pid)]
    if MUSIC_KEYS_RE.search(post["text"] or ""):
        return "音游成绩"
    return "生活随想"


def download(url, path, recompress=False):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    try:
        data = fetch(url, binary=True)
    except Exception as e:
        print("     ! 下载失败 %s: %s" % (url[:60], e))
        return False
    if recompress:
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            if im.width > MAX_IMG_W:
                im = im.convert("RGB") if im.mode in ("P", "RGBA") else im
                im = im.resize((MAX_IMG_W, int(im.height * MAX_IMG_W / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            (im.convert("RGB") if im.mode in ("P", "RGBA") else im).save(
                buf, "JPEG", quality=82, optimize=True, progressive=True)
            if buf.tell() < len(data):
                data = buf.getvalue()
        except Exception as e:
            print("     ! 图片压缩跳过 (%s)" % e)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True


def write_if_changed(path, text):
    """内容没变就不落盘：文件 mtime 稳定，sitemap 的 lastmod 才不会每次同步都跳。"""
    if os.path.exists(path):
        try:
            if open(path, encoding="utf-8").read() == text:
                return False
        except Exception:
            pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def read_front_matter(path):
    if not os.path.exists(path):
        return {}, ""
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", txt, re.S)
    if not m:
        return {}, txt
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, m.group(2)


def title_of(post):
    """标题：优先正文首行，其次"日期 · N 张图"，避免 Material 用文件名生成 "Tg 326"。"""
    t = re.sub(r"<[^>]*>", "", post["text"] or "")
    t = re.sub(r"[#*`\[\]()>]", "", t.split("\n")[0]).strip()
    if t:
        return t[:40]
    n = len(post["photos"])
    if n:
        return "%s · %d 张图" % (post["dt"][:10], n)
    if post["docs"]:
        return "%s · %s" % (post["dt"][:10], post["docs"][0]["name"])
    return "Telegram %s" % post["dt"][:10]


def load_site_state():
    """后台改的状态快照（scripts/site_state.json，由 sitegen --pull 从 X99 拉回来）。"""
    with open(SITE_STATE, encoding="utf-8") as f:
        return (json.load(f).get("posts") or {})


def post_state(site_state, post):
    st = site_state.get(str(post["id"])) or {}
    return st if isinstance(st, dict) else {}


def state_sig(st):
    return json.dumps({k: st.get(k) for k in ("type", "hidden", "records")},
                      ensure_ascii=False, sort_keys=True)


def rel_dest(post, st):
    """落点：隐藏 -> None；分享成博文 -> blog/posts/；其余 -> notes/<月>/。"""
    if st.get("hidden"):
        return None
    if st.get("type") == "post":
        return os.path.join("blog", "posts", "tg-%d.md" % post["id"])
    return os.path.join("notes", post["dt"][:7], "tg-%d.md" % post["id"])


def note_excerpt(post, limit=280):
    """时间线卡片用的纯文本：换行保留，标签剥掉，裁到 limit 字。"""
    t = re.sub(r"<br\s*/?>", "\n", post.get("text") or "")
    t = re.sub(r"<[^>]*>", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t).strip()
    return t[:limit]


def local_images(post):
    """磁盘上已有的媒体（下载过就不再碰网络）。"""
    mdir = os.path.join(MEDIA_DIR, str(post["id"]))
    out = []
    for i in range(1, len(post.get("photos") or []) + 1):
        if os.path.exists(os.path.join(mdir, "%d.jpg" % i)):
            out.append("/assets/tg/%d/%d.jpg" % (post["id"], i))
    for i in range(1, len(post.get("videos") or []) + 1):
        if os.path.exists(os.path.join(mdir, "video-%d.mp4" % i)):
            out.append("/assets/tg/%d/video-%d.mp4" % (post["id"], i))
    return out


def local_media_slots(post):
    """按 photos 顺序逐张对位（缺的留空），供不联网重排时用——空位不能省，
    否则合并帖里每段的图会整体串位。"""
    mdir = os.path.join(MEDIA_DIR, str(post["id"]))
    out = []
    for i in range(1, len(post.get("photos") or []) + 1):
        rel = "/assets/tg/%d/%d.jpg" % (post["id"], i)
        out.append(rel if os.path.exists(os.path.join(mdir, "%d.jpg" % i)) else "")
    return out


def url_of(post, st, dest):
    dt = datetime.fromisoformat(post["dt"]).astimezone(CST)
    if st.get("type") == "post":
        return "/blog/%s/tg-%d/" % (dt.strftime("%Y/%m/%d"), post["id"])
    return "/notes/%s/tg-%d/" % (dt.strftime("%Y-%m"), post["id"]) if dest else None


def index_row(post, st, dest, manual_cats):
    """站点/后台共用的索引行（也是 scripts/tg_posts.json 里的 index）。"""
    dt = datetime.fromisoformat(post["dt"]).astimezone(CST)
    return {"id": post["id"], "month": dt.strftime("%Y-%m"), "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "title": title_of(post), "text": note_excerpt(post), "images": local_images(post),
            "n_photos": len(post.get("photos") or []), "views": post.get("views") or "-",
            "merged": post.get("merged") or 0, "tg_link": post["link"],
            "cats": manual_cats or [classify(post)],
            "type": st.get("type") or "mutter", "hidden": bool(st.get("hidden")),
            "records": st.get("records") or [], "url": url_of(post, st, dest)}


def score_cards(records):
    """识别出来的成绩卡（贴在碎碎念里，同时收进 /record/ 成绩库）。"""
    if not records:
        return ""
    cards = []
    for r in records:
        if not isinstance(r, dict):
            continue
        jacket = r.get("jacket") or ""
        src = r.get("src") or (("/record/jackets/" + jacket) if jacket else "/record/")
        img = '<img src="/record/jackets/%s" alt="" loading="lazy">' % jacket if jacket else ""
        score = r.get("score")
        num = "—" if score is None else re.sub(r"\B(?=(\d{3})+(?!\d))", "'", "%d" % score)
        title = html.escape(r.get("title") or r.get("song_id") or "")
        sub = html.escape(" · ".join(x for x in (r.get("artist"), r.get("set")) if x))
        grade = html.escape(r.get("grade") or "")
        cards.append(
            '<a class="arc-card" href="%s" target="_blank" rel="noopener" title="看原图">%s'
            '<span class="arc-cmeta"><b>%s</b><small>%s</small></span>'
            '<span class="arc-cnum">%s</span>%s</a>'
            % (src, img, title, sub, num,
               '<span class="arc-grade">%s</span>' % grade if grade else ""))
    if not cards:
        return ""
    return ('<div class="arc-cards">'
            '<p class="arc-cards-head">识别到的音游成绩 <span>曲绘匹配 + 自带字体模板，不用 OCR</span></p>'
            + "".join(cards) + "</div>")


def render(post, media, videos, manual_cats, st=None):
    st = st or {}
    dt = datetime.fromisoformat(post["dt"]).astimezone(CST)
    ym = dt.strftime("%Y-%m")
    typ = st.get("type") or "mutter"
    cats = manual_cats or [classify(post)]
    if typ == "post" and "碎碎念" not in cats:      # 从碎碎念分享出来的博文标一下
        cats = cats + ["碎碎念"]
    lines = ["---",
             "date: %s" % dt.isoformat(sep=" ", timespec="seconds"),
             'title: "%s"' % title_of(post).replace('"', "'"),
             "slug: tg-%d" % post["id"],
             "categories:",
             *["  - %s" % c for c in cats],
             "authors:",
             "  - zl",
             "tags:",
             "  - Telegram",
             *(["  - 音游"] if "音游成绩" in cats else []),
             "tg_id: %d" % post["id"],
             *(["tg_ids: [%s]" % ", ".join(str(i) for i in post["ids"])] if post.get("merged") else []),
             'tg_link: "%s"' % post["link"],
             'tg_views: "%s"' % (post["views"] or "-"),
             "tg_type: %s" % typ,
             "tg_hash: %s" % sha(post, state_sig(st)),
             "---", ""]
    body = []
    if typ != "post":                               # 碎碎念/成绩是独立页面，给个回时间线的入口
        body.append('<p class="note-back"><a href="/notes/%s/">← %s 碎碎念时间线</a></p>' % (ym, ym))
        body.append("")
    it = iter(media)
    parts = post.get("parts") or [{"text": post["text"], "n_photos": len(media),
                                   "videos": videos, "docs": post["docs"], "link": post["link"]}]
    n = 0
    for idx, part in enumerate(parts):       # 同段合并时按原顺序交叉排：每条文字紧跟其媒体
        if idx:
            body.append("")                  # 合并的多条消息之间留空行，否则 markdown 会折成一段
        for _ in range(part["n_photos"]):
            rel = next(it, None)
            if rel:
                n += 1
                body.append("![图片 %d](%s)" % (n, rel))
        for v in part["videos"]:
            if v.get("file"):
                body.append('<video controls preload="metadata" src="%s"></video>' % v["file"])
            else:
                body.append("> 视频（%s）未本地化，[在 Telegram 查看](%s)"
                            % (v.get("dur") or "?", part.get("link") or post["link"]))
        for d in part["docs"]:
            body.append("📎 **%s**（%s）— [在 Telegram 获取](%s)"
                        % (d["name"], d["size"], part.get("link") or post["link"]))
        if part["text"]:
            body.append(part["text"])
    cards = score_cards(st.get("records") or [])
    if cards:
        body.append("")
        body.append(cards)
    body.append("")
    body.append('<div class="tg-rx" data-post="%d"></div>' % post["id"])
    body.append("")
    if post.get("merged"):
        links = " · ".join("[%d](https://t.me/%s/%d)" % (i, CH, i) for i in post["ids"])
        body.append("— 合并自 Telegram %s · 共 %s 次浏览" % (links, post["views"] or "-"))
    else:
        body.append("— [Telegram 原帖](%s) · %s 次浏览" % (post["link"], post["views"] or "-"))
    return "\n".join(lines) + "\n".join(body) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="翻到底，重新检查全部历史")
    ap.add_argument("--limit", type=int, default=0, help="只处理最近 N 条")
    ap.add_argument("--no-media", action="store_true")
    ap.add_argument("--group-window", type=int, default=GROUP_WINDOW,
                    help="同一时段合并的时间窗（秒），0 = 不合并")
    ap.add_argument("--from-cache", action="store_true",
                    help="不抓 TG，用 scripts/tg_posts.json 里的缓存重排页面（后台改状态后的快速重排）")
    args = ap.parse_args()

    try:
        site_state = load_site_state()
    except Exception:
        site_state = {}
        print("! 没有 scripts/site_state.json（后台状态），一律按碎碎念处理")

    state = {}
    if os.path.exists(STATE):
        state = json.load(open(STATE, encoding="utf-8"))

    if args.from_cache:
        cache = json.load(open(CACHE, encoding="utf-8"))
        posts = cache.get("posts") or []
        print("用缓存重排 %d 条（不抓 TG）" % len(posts))
        args.no_media = True
    else:
        known = {int(k) for k in state.get("seen", {})}
        print("已知帖子 %d 条，开始抓取%s" % (len(known), "（全量）" if args.full else "（增量）"))
        posts = scrape(args.full, known if known else None)
        raw = len(posts)
        posts = merge_groups(posts, args.group_window) if args.group_window else posts
        if args.limit:
            posts = posts[-args.limit:]
        print("抓到 %d 条 -> 合并后 %d 条（%d 条为同段聚合）"
              % (raw, len(posts), sum(1 for p in posts if p.get("merged"))))

    os.makedirs(POSTS_DIR, exist_ok=True)
    stats = {"new": 0, "updated": 0, "skipped": 0, "moved": 0, "removed": 0,
             "media": 0, "video_bytes": 0, "img_bytes": 0}
    index = []
    for p in posts:
        st = post_state(site_state, p)
        rel = rel_dest(p, st)
        dest = os.path.join(SRC, rel) if rel else None
        # 上一篇可能落在另一个位置（刚分享出去 / 刚取消分享 / 刚隐藏），两处都找一遍
        cands = [c for c in [dest,
                             os.path.join(POSTS_DIR, "tg-%d.md" % p["id"]),
                             os.path.join(NOTES_DIR, p["dt"][:7], "tg-%d.md" % p["id"])] if c]
        old_path, old_fm = None, {}
        for c in cands:
            if os.path.exists(c):
                old_path, old_fm = c, read_front_matter(c)[0]
                break
        h = sha(p, state_sig(st))
        if dest and old_path == dest and old_fm.get("tg_hash") == h:
            stats["skipped"] += 1
            index.append(index_row(p, st, dest, None))
            continue
        media, videos = [], []
        if args.from_cache:                       # 缓存重排：直接用磁盘上已有的
            media = local_media_slots(p)
            videos = p.get("videos") or []
        elif args.no_media:
            media = local_media_slots(p)
            videos = p.get("videos") or []
        else:
            mdir = os.path.join(MEDIA_DIR, str(p["id"]))
            for i, u in enumerate(p["photos"], 1):
                rel = "/assets/tg/%d/%d.jpg" % (p["id"], i)
                if download(u, os.path.join(mdir, "%d.jpg" % i), recompress=True):
                    media.append(rel)
                    stats["media"] += 1
                    stats["img_bytes"] += os.path.getsize(os.path.join(mdir, "%d.jpg" % i))
            for vi, v in enumerate(p["videos"], 1):
                if not v["src"]:
                    continue
                try:
                    req = urllib.request.Request(v["src"], headers={"User-Agent": UA}, method="HEAD")
                    n = int(urllib.request.urlopen(req, timeout=30).headers.get("Content-Length") or 0)
                except Exception:
                    n = 0
                if n and n / 1e6 <= MAX_VIDEO_MB:
                    vp = os.path.join(mdir, "video-%d.mp4" % vi)
                    if download(v["src"], vp):
                        v["file"] = "/assets/tg/%d/video-%d.mp4" % (p["id"], vi)
                        stats["video_bytes"] += os.path.getsize(vp)
                videos.append(v)
        old_cats = None
        # 保留用户手改的分类：直接读原文件 front matter 的列表
        if old_path:
            txt = open(old_path, encoding="utf-8").read()
            m = re.search(r"^categories:\n((?:\s*-\s*.*\n)+)", txt, re.M)
            if m and old_fm.get("tg_hash"):
                cats = re.findall(r"-\s*(.+)", m.group(1))
                if cats and cats != [classify(p)]:
                    old_cats = [c.strip() for c in cats]
        if dest:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if write_if_changed(dest, render(p, media, videos, old_cats, st)):
                stats["updated" if old_path == dest else "new"] += 1
            else:
                stats["same"] = stats.get("same", 0) + 1
        for c in cands:                           # 换位置/隐藏：清掉旧文件
            if c != dest and os.path.exists(c):
                os.remove(c)
                stats["moved" if dest else "removed"] += 1
        index.append(index_row(p, st, dest, old_cats))

    # 播种表 / 待确认清单都按"全部帖子 + 已有文件"合并生成：
    # 增量运行只抓到最近一页，不能因此把这两份文件截断
    def _read_json(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    seed = {str(p["id"]): {norm_emoji(r["emoji"]): r["count"] for r in p["reactions"]}
            for p in posts if p["reactions"]}
    for pid, ems in _read_json(os.path.join(REPO, "scripts", "tg-reactions-seed.json"), {}).items():
        seed.setdefault(pid, {})
        for em, n in ems.items():                     # 顺手洗净历史遗留的 **👍** 脏键
            e = norm_emoji(em)
            if e:
                seed[pid].setdefault(e, n)

    rev_rows = {}
    try:
        with open(REVIEW, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\|\s*\[(\d+)\]\(https://t\.me/[^)]*\)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
                if m:
                    rev_rows[m.group(1)] = (m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
    except Exception:
        pass
    for p in posts:
        if classify(p) == "生活随想" and (not p["text"].strip() or len(p["text"]) <= 20):
            rev_rows[str(p["id"])] = (p["dt"][:10], (p["text"] or "").replace("\n", " ")[:34],
                                      str(len(p["photos"])))

    seen = {}
    for p in posts:
        for pid in p.get("ids", [p["id"]]):
            seen[str(pid)] = sha(p)
    # 增量运行只抓到最近一页：状态必须与旧文件合并，否则下次得从最新一路翻回 id 1
    for k, v in (state.get("seen") or {}).items():
        seen.setdefault(k, v)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "seen": seen}, f, indent=0)
    with open(os.path.join(REPO, "scripts", "tg-reactions-seed.json"), "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=1)
    with open(REVIEW, "w", encoding="utf-8") as f:
        f.write("# 待确认分类（生活随想 ← 图片/短配文帖）\n\n"
                "音游成绩帖多为无关键词的成绩截图，需要你标。改法二选一：\n\n"
                "1. 在 `scripts/tg_category_overrides.json` 里写 `{\"315\": \"音游成绩\"}`（推荐的批量方式）；\n"
                "2. 直接编辑对应 md 的 `categories:`（重跑同步会保留你的改动）。\n\n"
                "点标题可在 Telegram 里看原图确认。\n\n"
                "| id | 日期 | 配文 | 图数 | 现分类 |\n|---|---|---|---|---|\n")
        for pid in sorted(rev_rows, key=lambda x: int(x)):
            d, t, n = rev_rows[pid]
            f.write("| [%s](https://t.me/%s/%s) | %s | %s | %s | 生活随想 |\n"
                    % (pid, CH, pid, d, t.replace("|", "\\|"), n))
    with open(CACHE, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"version": 1, "render": RENDER_V,
                   "posts": posts, "index": index}, f, ensure_ascii=False, indent=0)
    by_type = {}
    for row in index:
        by_type[row["type"]] = by_type.get(row["type"], 0) + 1
    print("索引 -> scripts/tg_posts.json（%d 条：%s）"
          % (len(index), " / ".join("%s %d" % (k, v) for k, v in sorted(by_type.items()))))
    print("新增 %d / 更新 %d / 未变 %d / 跳过 %d / 换位置 %d / 移除 %d | 媒体 %d 张 %.1f MB | 视频 %.1f MB"
          % (stats["new"], stats["updated"], stats.get("same", 0), stats["skipped"], stats["moved"], stats["removed"],
             stats["media"], stats["img_bytes"] / 1e6, stats["video_bytes"] / 1e6))
    print("reaction 播种 %d 条帖子 -> scripts/tg-reactions-seed.json" % len(seed))
    print("待确认分类 %d 条 -> scripts/tg-review.md" % len(rev_rows))


if __name__ == "__main__":
    main()
