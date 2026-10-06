#!/usr/bin/env python3
"""把 TG 抓到的 reaction 数（scripts/tg-reactions-seed.json）并进服务器计数。

只在"服务器上还没有这个 (帖子, emoji)"时写入，且取两边最大值，
所以人工点出来的数不会被抓取覆盖。
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(REPO, "scripts", "tg-reactions-seed.json")
REMOTE = "/srv/zlblog/reactions.json"


def ssh(cmd, stdin=None):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "x99", cmd],
                          input=stdin, capture_output=True, text=True)


def norm_emoji(e):
    """老版本的抓取把 emoji 写成 **👍**（markdown 加粗），这里统一洗干净。"""
    return str(e).replace("*", "").strip()


def main():
    if not os.path.exists(SEED):
        print("没有 seed 文件，跳过")
        return
    seed = {pid: {norm_emoji(e): int(n) for e, n in ems.items()}
            for pid, ems in json.load(open(SEED, encoding="utf-8")).items()}
    r = ssh("sudo -n cat %s" % REMOTE)
    if r.returncode != 0:
        print("读取服务器计数失败：%s" % r.stderr.strip())
        sys.exit(1)
    try:
        raw = json.loads(r.stdout or "{}")
    except Exception:
        raw = {}
    cur = {}
    for pid, ems in raw.items():                     # 顺手洗掉服务器上已有的脏键
        for em, n in ems.items():
            e = norm_emoji(em)
            if e:
                cur.setdefault(pid, {})[e] = max(cur.get(pid, {}).get(e, 0), int(n))
    added = 0
    for pid, ems in seed.items():
        for em, n in ems.items():
            old = int((cur.get(pid) or {}).get(em, 0))
            if old < n:
                cur.setdefault(pid, {})[em] = int(n)
                added += 1
    payload = json.dumps(cur, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    w = ssh("sudo -n bash -c 'cat > %s.tmp && mv %s.tmp %s && chown OYZH:OYZH %s'"
            % (REMOTE, REMOTE, REMOTE, REMOTE), stdin=payload)
    if w.returncode != 0:
        print("写回失败：%s" % w.stderr.strip())
        sys.exit(1)
    print("reaction 播种完成：%d 项（服务器现有 %d 个帖子）" % (added, len(cur)))


if __name__ == "__main__":
    main()
