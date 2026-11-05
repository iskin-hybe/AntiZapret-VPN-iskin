"""Тематический поиск по нормализованной переписке с контекстом веток.

Запуск: python3 -I topic_search.py <all.txt> <out.txt> [since=YYYY-MM]
"""
import re, sys, collections

src, out = sys.argv[1], sys.argv[2]
since = sys.argv[3] if len(sys.argv) > 3 else "0000-00"

CATS = {
    "op":       r"\byota\b|йот[аеуы]\b|скартел|мегафон|megafon|\bмтс\b|\bmts\b|билайн|beeline|теле2|tele2|\bт2\b",
    "mobile":   r"мобильн|\blte\b|\b4g\b|\b5g\b|сотов|с телефона на симк|на симке|моб\.? ?инет",
    "restrict": r"глушил|белы[йеих]\s*спис|whitelist|вайтлист|белого списка|ограничени[яей] (мобильн|интернет)|отключени[яей] (мобильн|интернет)|шатдаун",
    "throttle": r"тспу|\bdpi\b|замедл|режет|режут|душит|через (минуту|пару минут|\d+ ?мин)|отвалива|обрыва|блокиру[ею]т (впн|vpn|протокол)|детект",
    "relay":    r"каскад|\brelay\b|\bреле\b|\bмост|bridge|proxy\.sh|прокси.?сервер|ру.?(сервер|впс|vps|нод)|российск\S* (сервер|vps|впс|хостинг|облак|нод)|рф.?(сервер|vps|впс)|входн\S* (сервер|нод|точк)|внутри рф",
    "stealth":  r"vless|reality|xray|hysteria|xhttp|sing-?box|3x-?ui|marzban|remnawave|\bsni\b|маскир|обфускац",
    "hoster":   r"yandex.?cloud|яндекс.?облак|selectel|селектел|timeweb|таймвеб|vk.?cloud|cloud\.ru|reg\.ru|beget|бегет|\baeza\b|4vps|vdsina|рувдс|ruvds|firstbyte|jino",
}
RX = {k: re.compile(v, re.I) for k, v in CATS.items()}

lines = open(src, encoding="utf-8").read().splitlines()
by_id, parent, children = {}, {}, collections.defaultdict(list)
for ln in lines:
    m = re.match(r"#(\d+) \[(\S+) \S+\] (\S+)(?: ↩#(\d+))?: ", ln)
    if not m:
        continue
    mid = int(m.group(1)); by_id[mid] = ln
    if m.group(4):
        parent[mid] = int(m.group(4)); children[int(m.group(4))].append(mid)

def cats(ln):
    return {k for k, rx in RX.items() if rx.search(ln)}

hits = {}
for mid, ln in by_id.items():
    date = ln.split("[", 1)[1][:7]
    if date < since:
        continue
    c = cats(ln)
    core = ("restrict" in c) or ("relay" in c and ("mobile" in c or "op" in c or "restrict" in c or "throttle" in c)) \
        or (("op" in c or "mobile" in c) and ("throttle" in c or "stealth" in c or "relay" in c))
    if core:
        hits[mid] = c

keep = set(hits)
for mid in list(hits):
    if mid in parent: keep.add(parent[mid])
    keep.update(children.get(mid, [])[:6])

with open(out, "w", encoding="utf-8") as f:
    for mid in sorted(keep):
        if mid in by_id:
            mark = "★" if mid in hits else " "
            f.write(f"{mark} {by_id[mid]}\n")

per_month = collections.Counter(by_id[m].split('[', 1)[1][:7] for m in hits)
print("core hits:", len(hits), "| with context:", len(keep))
print("per month:", dict(sorted(per_month.items())))
print("author among hits:", sum(1 for m in hits if '] АВТОР' in by_id[m]))
print("chars:", sum(len(by_id[m]) for m in keep if m in by_id))
