"""Готовит порции для базы знаний.

Слой 1: все сообщения АВТОРА + сообщения, на которые он отвечал, + до 2 прямых ответов на его сообщения.
Слой 2: развёрнутые сообщения (>= MINLEN символов) с SINCE, не вошедшие в слой 1.
Каждая порция ~ CHUNK символов, границы по сообщениям, в хронологическом порядке.

Запуск: python3 -I make_chunks.py <all.txt> <out_dir>
"""
import re, sys, os, collections

src, out = sys.argv[1], sys.argv[2]
CHUNK, MINLEN, SINCE = 200_000, 200, "2026-08"
os.makedirs(out, exist_ok=True)
P = re.compile(r"#(\d+) \[(\S+) \S+\] (\S+)(?: ↩#(\d+))?: (.*)")
rec, children = {}, collections.defaultdict(list)
for ln in open(src, encoding="utf-8").read().splitlines():
    m = P.match(ln)
    if not m:
        continue
    mid = int(m.group(1))
    par = int(m.group(4)) if m.group(4) else None
    rec[mid] = dict(month=m.group(2)[:7], who=m.group(3), par=par, text=m.group(5), line=ln)
    if par:
        children[par].append(mid)

tier1 = set()
for mid, r in rec.items():
    if r["who"] == "АВТОР":
        tier1.add(mid)
        if r["par"] in rec:
            tier1.add(r["par"])
        tier1.update(c for c in children.get(mid, [])[:2] if c in rec)
tier2 = {mid for mid, r in rec.items()
         if mid not in tier1 and r["month"] >= SINCE and len(r["text"]) >= MINLEN}

def write_chunks(ids, prefix):
    files, buf, size, n = [], [], 0, 1
    for mid in sorted(ids):
        ln = rec[mid]["line"]
        if size + len(ln) > CHUNK and buf:
            fn = os.path.join(out, f"{prefix}-{n:02d}.txt"); open(fn, "w", encoding="utf-8").write("\n".join(buf) + "\n")
            files.append((fn, len(buf), size, buf[0][buf[0].index('[')+1:][:10], buf[-1][buf[-1].index('[')+1:][:10]))
            buf, size, n = [], 0, n + 1
        buf.append(ln); size += len(ln) + 1
    if buf:
        fn = os.path.join(out, f"{prefix}-{n:02d}.txt"); open(fn, "w", encoding="utf-8").write("\n".join(buf) + "\n")
        files.append((fn, len(buf), size, buf[0][buf[0].index('[')+1:][:10], buf[-1][buf[-1].index('[')+1:][:10]))
    return files

for prefix, ids in (("t1-author", tier1), ("t2-recent", tier2)):
    for fn, nlines, size, d1, d2 in write_chunks(ids, prefix):
        print(f"{os.path.basename(fn)}: {nlines} msgs, {size} chars, {d1} .. {d2}")
