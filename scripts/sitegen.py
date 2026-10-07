#!/usr/bin/env python3
"""把 TG 同步下来的碎碎念组织成站点：月份时间线 / 总览 / 内容索引 / 成绩数据。

分工：
  tg_sync.py   每篇碎碎念的页面本体（落点由后台状态决定） + scripts/tg_posts.json
  sitegen.py   派生件：/notes/ 总览、/notes/<月>/ 时间线、assets/content.json、
               /record/records-notes.json（识别出来的成绩）、曲绘

后台状态由 X99 上的 /srv/zlblog/content.json 维护，--pull 拉回 scripts/site_state.json。
（页面已经按同一份状态生成过；这里再叠一次是兜底，免得只跑 sitegen 时状态落后。）

  python scripts/sitegen.py --pull     # 拉后台状态 + 成绩 + 曲绘，然后生成
  python scripts/sitegen.py            # 只用本地已有的状态生成
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "src")
NOTES = os.path.join(SRC, "notes")
RECORD = os.path.join(SRC, "record")
CACHE = os.path.join(REPO, "scripts", "tg_posts.json")
SITE_STATE = os.path.join(REPO, "scripts", "site_state.json")
RECORDS_POST = os.path.join(REPO, "scripts", "records_post.json")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "x99"]
WEEK = "一二三四五六日"
TYPE_TXT = {"mutter": "碎碎念", "post": "博文", "score": "音游成绩"}
ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def esc(s):
    return "".join(ESC.get(c, c) for c in str(s if s is not None else ""))


CHANGED = []


def write(path, text):
    """内容没变就不落盘 —— mtime 一抖，mkdocs 的 sitemap lastmod 就跟着变，
    10 分钟一次的轻量同步就会变成 10 分钟一次的空提交。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            if open(path, encoding="utf-8").read() == text:
                return
        except Exception:
            pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    CHANGED.append(os.path.relpath(path, REPO))


# ---------------------------------------------------------------- 从 X99 拉状态

def pull():
    def cat(remote, local):
        p = subprocess.run(SSH + ["cat " + remote], capture_output=True)
        if p.returncode != 0 or not p.stdout.strip():
            print("  ! 拉取失败 %s（沿用本地那份）" % remote)
            return False
        try:
            json.loads(p.stdout.decode("utf-8"))
        except Exception as e:                    # 别把错误页/半截文件写进仓库
            print("  ! %s 不是合法 JSON（%s）" % (remote, e))
            return False
        with open(local, "wb") as f:
            f.write(p.stdout)
        print("  ✓ %s" % remote)
        return True

    cat("/srv/zlblog/content.json", SITE_STATE)
    cat("/srv/zlblog/arc/records_post.json", RECORDS_POST)
    # 曲绘：服务端只暂存识别结果用到的那几张
    os.makedirs(os.path.join(RECORD, "jackets"), exist_ok=True)
    p = subprocess.run(SSH + ["tar czf - -C /srv/zlblog/arc jackets 2>/dev/null"], capture_output=True)
    if p.returncode == 0 and p.stdout:
        t = subprocess.run(["tar", "xzf", "-", "-C", RECORD.replace("\\", "/")],
                           input=p.stdout, capture_output=True)
        if t.returncode != 0:
            print("  ! 曲绘解包失败：%s" % t.stderr.decode("utf-8", "replace")[:160])
        else:
            n = len(os.listdir(os.path.join(RECORD, "jackets")))
            print("  ✓ 曲绘 %d 张" % n)
    else:
        print("  ! 曲绘没拉到（服务端还没有识别结果？）")


# ---------------------------------------------------------------- 数据

def load_rows():
    with open(CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    rows = cache.get("index") or []
    try:
        with open(SITE_STATE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    posts = state.get("posts") if isinstance(state, dict) else None
    for r in rows:
        e = (posts or {}).get(str(r["id"])) or {}
        if not e:
            continue
        r["type"] = e.get("type") or "mutter"
        r["hidden"] = bool(e.get("hidden"))
        if e.get("records"):
            r["records"] = e["records"]
        r["url"] = url_of(r)
    return rows


def url_of(r):
    if r.get("type") == "post":
        d = (r.get("date") or "")[:10].replace("-", "/")
        return "/blog/%s/tg-%s/" % (d, r["id"])
    if r.get("hidden"):
        return None
    return "/notes/%s/tg-%s/" % (r["month"], r["id"])


def month_label(ym):
    y, m = ym.split("-")
    return "%s 年 %d 月" % (y, int(m))


def weekday_of(date):
    try:
        return WEEK[datetime.strptime(date[:10], "%Y-%m-%d").weekday()]
    except Exception:
        return ""


# ---------------------------------------------------------------- 片段

def score_cards(records):
    """和 tg_sync 里的同一套卡片（时间线上就地展开成绩）。"""
    cards = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        jacket = r.get("jacket") or ""
        img = '<img src="/record/jackets/%s" alt="" loading="lazy">' % esc(jacket) if jacket else ""
        score = r.get("score")
        num = "—" if score is None else re.sub(r"\B(?=(\d{3})+(?!\d))", "'", "%d" % score)
        sub = " · ".join(x for x in (r.get("artist"), r.get("set")) if x)
        cards.append('<a class="arc-card" href="%s" target="_blank" rel="noopener" title="看原图">%s'
                     '<span class="arc-cmeta"><b>%s</b><small>%s</small></span>'
                     '<span class="arc-cnum">%s</span>%s</a>'
                     % (esc(r.get("src") or ("/record/jackets/" + jacket)), img,
                        esc(r.get("title") or r.get("song_id")), esc(sub), num,
                        '<span class="arc-grade">%s</span>' % esc(r["grade"]) if r.get("grade") else ""))
    if not cards:
        return ""
    return ('<div class="arc-cards"><p class="arc-cards-head">识别到的音游成绩'
            '<span>曲绘匹配 + 自带字体模板，不用 OCR</span></p>' + "".join(cards) + "</div>")


def item_html(r):
    url = r.get("url") or "#"
    time_txt = (r.get("date") or "")[11:16]
    out = ['<article class="tl-item" data-post="%s">' % esc(r["id"])]
    out.append('<div class="tl-head">')
    out.append('<a class="tl-time" href="%s">%s</a>' % (esc(url), esc(time_txt or "?")))
    if r.get("type") == "score":
        out.append('<span class="badge b-score">音游成绩</span>')
    elif r.get("type") == "post":
        out.append('<span class="badge b-post">已分享到博客</span>')
    if r.get("records"):
        songs = [x.get("title") or x.get("song_id") for x in r["records"] if isinstance(x, dict)]
        if songs:
            out.append('<span class="tl-songs">%s</span>' % esc(" · ".join(songs[:3])))
    if r.get("tg_link"):
        out.append('<a class="tl-tg" href="%s" target="_blank" rel="noopener">TG</a>' % esc(r["tg_link"]))
    out.append('</div>')
    text = (r.get("text") or "").strip()
    if text:
        out.append('<div class="tl-text">%s</div>' % esc(text).replace("\n", "<br>"))
    imgs = [i for i in (r.get("images") or []) if i.endswith((".jpg", ".jpeg", ".png", ".webp"))]
    vids = [i for i in (r.get("images") or []) if i.endswith(".mp4")]
    if imgs or vids:
        out.append('<div class="tl-media">')
        for i in imgs[:6]:
            out.append('<a href="%s"><img src="%s" loading="lazy" alt=""></a>' % (esc(url), esc(i)))
        if len(imgs) > 6:
            out.append('<span class="tl-more">+%d 张</span>' % (len(imgs) - 6))
        if vids:
            out.append('<span class="tl-more">▶ %d 个视频</span>' % len(vids))
        out.append('</div>')
    cards = score_cards(r.get("records"))
    if cards:
        out.append(cards)
    out.append('<div class="tg-rx" data-post="%s"></div>' % esc(r["id"]))
    out.append('</article>')
    return "".join(out)


def timeline_html(rows):
    """按天分组的时间线（同一天一个日期桩）。"""
    days, out = [], []
    for r in rows:
        d = (r.get("date") or "")[:10]
        if not days or days[-1][0] != d:
            days.append((d, []))
        days[-1][1].append(r)
    out.append('<div class="tl">')
    for d, items in days:
        out.append('<div class="tl-day"><div class="tl-date"><b>%s</b><span>%s · 周%s</span></div>'
                   '<div class="tl-items">' % (esc(d[8:10]), esc(d), esc(weekday_of(d))))
        out.extend(item_html(r) for r in items)
        out.append('</div></div>')
    out.append('</div>')
    return "".join(out)


# ---------------------------------------------------------------- 页面

def month_page(ym, rows, months):
    i = months.index(ym)
    navl = []
    if i + 1 < len(months):
        navl.append('<a href="/notes/%s/">← %s</a>' % (months[i + 1], month_label(months[i + 1])))
    navl.append('<a href="/notes/">全部</a>')
    if i > 0:
        navl.append('<a href="/notes/%s/">%s →</a>' % (months[i - 1], month_label(months[i - 1])))
    with_img = sum(1 for r in rows if r.get("images"))
    scores = sum(len(r.get("records") or []) for r in rows)
    meta = ["%d 条" % len(rows)]
    if with_img:
        meta.append("%d 条带图" % with_img)
    if scores:
        meta.append("%d 个成绩" % scores)
    return ("---\ntitle: 碎碎念 · %s\n---\n\n# 碎碎念 · %s\n\n%s · %s\n\n%s\n"
            % (month_label(ym), month_label(ym), " · ".join(meta), " ".join(navl),
               timeline_html(rows)))


def overview_page(rows, months, counts):
    live = [r for r in rows if not r.get("hidden") and r.get("type") != "post"]
    parts = []
    if rows:
        parts.append("共 %d 条" % len(live))
        if counts.get("score"):
            parts.append("%d 条是音游成绩" % counts["score"])
        parts.append("%s → %s" % ((rows[-1].get("date") or "")[:10], (rows[0].get("date") or "")[:10]))
    months_html = ['<div class="nt-months">']
    for ym in months:
        n = sum(1 for r in live if r.get("month") == ym)
        if not n:
            continue
        img = sum(1 for r in live if r.get("month") == ym and r.get("images"))
        sc = sum(len(r.get("records") or []) for r in live if r.get("month") == ym)
        info = ["%d 条" % n]
        if img:
            info.append("%d 带图" % img)
        if sc:
            info.append("%d 成绩" % sc)
        months_html.append('<a class="nt-month" href="/notes/%s/"><b>%s</b><span>%s</span></a>'
                           % (ym, esc(month_label(ym)), esc(" · ".join(info))))
    months_html.append('</div>')
    latest = live[:12]
    return ("---\ntitle: 碎碎念\n---\n\n# 碎碎念\n\n"
            "Telegram 频道同步下来的零碎内容（不掺进 [博客](/blog/)）。"
            "音游成绩那部分识别出来的卡片，另在 [成绩库](/record/) 汇总。\n\n"
            "%s\n\n## 按月翻\n\n%s\n\n## 最新\n\n%s\n"
            % (" · ".join(parts), "".join(months_html), timeline_html(latest)))


def content_json(rows, counts):
    keep = ("id", "month", "date", "title", "text", "images", "url", "views", "merged",
            "tg_link", "type", "hidden", "records", "cats")
    out = [{k: r.get(k) for k in keep} for r in rows]
    out.sort(key=lambda r: (r.get("date") or "", int(r["id"])), reverse=True)
    return {"version": 1, "counts": counts, "posts": out}


def records_notes():
    """识别出来的成绩 -> /record/ 那一页的数据格式。"""
    try:
        with open(RECORDS_POST, encoding="utf-8") as f:
            src = json.load(f)
    except Exception:
        return []
    rows = []
    for r in src if isinstance(src, list) else []:
        if not isinstance(r, dict) or not r.get("song_id"):
            continue
        rows.append({"screenshot": r.get("src") or "", "game": "arcaea", "layout": "",
                     "song_id": r["song_id"], "title": r.get("title") or r["song_id"],
                     "artist": r.get("artist") or "", "set": r.get("set") or "",
                     "score": r.get("score"), "score_digits": "",
                     "grade": r.get("grade") or "", "jacket": r.get("jacket") or "",
                     "min_digit_conf": r.get("min_digit_conf"),
                     "song_ok": True, "score_ok": r.get("score") is not None,
                     "from": "碎碎念 #%s" % r.get("post"), "post": r.get("post"),
                     "date": r.get("date") or ""})
    return rows


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true", help="先从 X99 拉后台状态/成绩/曲绘")
    a = ap.parse_args()
    if a.pull:
        print("拉取后台状态：")
        pull()

    rows = load_rows()
    if len(rows) < 10:
        print("!! 索引只有 %d 条，拒绝生成（多半是 tg_posts.json 有问题）" % len(rows))
        return 1
    live = [r for r in rows if not r.get("hidden") and r.get("type") != "post"]
    for r in live:
        r["url"] = r.get("url") or url_of(r)
    months = sorted({r["month"] for r in live}, reverse=True)
    counts = {"total": len(rows), "live": len(live), "hidden": 0, "score": 0, "post": 0}
    for r in rows:
        t = r.get("type") or "mutter"
        counts[t] = counts.get(t, 0) + 1
        if r.get("hidden"):
            counts["hidden"] += 1

    # 月份时间线
    for ym in months:
        write(os.path.join(NOTES, ym, "index.md"),
              month_page(ym, [r for r in live if r["month"] == ym], months))
    write(os.path.join(NOTES, "index.md"), overview_page(rows, months, counts))
    # 清掉没有碎碎念的月份目录（页面都重建，产物不会残留；src 里的旧目录要删）
    for d in sorted(os.listdir(NOTES)) if os.path.isdir(NOTES) else []:
        full = os.path.join(NOTES, d)
        if os.path.isdir(full) and d not in months:
            shutil.rmtree(full)
            print("  - 删掉空月份目录 notes/%s" % d)

    # 站点索引（后台列表 + 前端即时覆盖都用它）
    write(os.path.join(SRC, "assets", "content.json"),
          json.dumps(content_json(rows, counts), ensure_ascii=False, indent=0) + "\n")
    # /record/ 的来源二：碎碎念里识别出来的成绩
    write(os.path.join(RECORD, "records-notes.json"),
          json.dumps(records_notes(), ensure_ascii=False, indent=1) + "\n")

    if CHANGED:
        print("改写 %d 个文件（%s…）" % (len(CHANGED), ", ".join(CHANGED[:3])))
    print("notes 总览 + %d 个月份时间线；碎碎念 %d / 已分享 %d / 音游成绩 %d / 隐藏 %d"
          % (len(months), counts.get("mutter", 0), counts.get("post", 0),
             counts.get("score", 0), counts["hidden"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
