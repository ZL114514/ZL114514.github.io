#!/usr/bin/env python3
"""把早期批量识别的成绩补上日期：从原始截图文件名里取。

早期那批 records.json 的 screenshot 是 full_N.jpg（矫正后的图，文件名里没日期），
但原图是手机截图 Screenshot_YYYYMMDD-HHMMSS_Arcaea.png —— 日期就在名字里。
约定：shots/full_N.jpg 是原图按文件名排序后的第 N 张。

  python scripts/arc_dates.py --shots "C:/Users/ZL/Downloads/arcaea-shots"
  python scripts/arc_dates.py --shots ... --write     # 真写进 src/record/records.json

先 dry-run 看表格，确认顺序对得上再 --write。
"""
import argparse
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS = os.path.join(REPO, "src", "record", "records.json")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
# Screenshot_20250318-123954_Arcaea.png / Screenshot_20250318-123954.png / IMG_20250318_123954.jpg
PATTERNS = [
    re.compile(r"(?:Screenshot|IMG|Photo)[-_](\d{4})(\d{2})(\d{2})[-_](\d{2})(\d{2})(\d{2})", re.I),
    re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})[.:](\d{2})[.:](\d{2})"),
]


def stamp(name):
    """文件名 -> 'YYYY-MM-DD HH:MM:SS'，认不出就 None。"""
    for pat in PATTERNS:
        m = pat.search(name)
        if m:
            y, mo, d, h, mi, s = m.groups()
            return "%s-%s-%s %s:%s:%s" % (y, mo, d, h, mi, s)
    return None


def shot_index(rec):
    """full_209.jpg -> 209"""
    m = re.search(r"(\d+)", str(rec.get("screenshot") or ""))
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", required=True, help="原始截图目录")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.shots) if f.lower().endswith(IMG_EXT))
    dated = [(f, stamp(f)) for f in files]
    ok = [x for x in dated if x[1]]
    print("目录：%s" % a.shots)
    print("图片 %d 张，其中 %d 张文件名里带日期" % (len(files), len(ok)))
    if not ok:
        print("!! 一个日期都认不出来，先看文件名长什么样：")
        for f in files[:8]:
            print("   ", f)
        return 1
    if len(ok) != len(files):
        print("   认不出的（会被跳过，序号会错位，注意！）：")
        for f, d in dated:
            if not d:
                print("   ", f)

    by_index = {i + 1: d for i, (f, d) in enumerate(dated)}
    rows = json.load(io.open(RECORDS, encoding="utf-8"))
    hit = miss = 0
    for r in rows:
        if r.get("date"):
            continue
        n = shot_index(r)
        d = by_index.get(n)
        if d:
            r["date"] = d
            hit += 1
        else:
            miss += 1
    print("记录 %d 条：补上日期 %d 条，序号对不上 %d 条" % (len(rows), hit, miss))
    bad = [r for r in rows if not r.get("date")]
    if bad:
        print("   还没日期的（序号超出截图范围？）：%s"
              % ", ".join(sorted({str(r.get("screenshot")) for r in bad})[:12]))
    for r in sorted([x for x in rows if x.get("date")], key=lambda x: x["date"])[:6]:
        print("   %s  %-22s %s" % (r["date"], r.get("title"), r.get("score")))

    if a.write:
        with io.open(RECORDS, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("已写入 %s" % RECORDS)
    else:
        print("（dry-run；加 --write 才写文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
