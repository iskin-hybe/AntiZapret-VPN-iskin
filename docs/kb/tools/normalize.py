"""Нормализация выгрузки Telegram: анонимизация авторов и вычистка секретов.

Запуск: python3 -I normalize.py <result.json> <out_dir> [from_id=МЕТКА ...]
Необязательные пары from_id=МЕТКА дают особые метки (например, сотрудникам хостера:
channel2142793587=ХОСТЕР). from_id берётся из поля from_id выгрузки.
Пишет: all.txt (все сообщения), by-month/YYYY-MM.txt, stats.txt.
Карта ников НЕ сохраняется на диск — только условные метки.
"""
import json, re, sys, os, collections

src, out = sys.argv[1], sys.argv[2]
special = dict(a.split("=", 1) for a in sys.argv[3:])
os.makedirs(os.path.join(out, "by-month"), exist_ok=True)
d = json.load(open(src, encoding="utf-8"))
msgs = [m for m in d["messages"] if m.get("type") == "message"]

def text_of(m):
    t = m.get("text", "")
    if isinstance(t, list):
        parts = []
        for x in t:
            if isinstance(x, str):
                parts.append(x)
            else:
                # для ссылок с подписью оставляем подпись, сам href не нужен
                parts.append(x.get("text", ""))
        t = "".join(parts)
    return t

RX = [
    (re.compile(r'\b(vless|vmess|trojan|ss|ssr|hysteria2?|hy2|tuic|wireguard|awg|amneziawg)://\S+', re.I), r'<\1-ссылка>'),
    (re.compile(r'https?://\S*/(sub|subscription|s|api/sub)/\S+', re.I), '<ссылка-подписки>'),
    (re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b'), '<токен-бота>'),
    (re.compile(r'\b[A-Za-z0-9+/]{42,43}=(?![A-Za-z0-9+/=])'), '<ключ>'),
    (re.compile(r'(?i)\b(PrivateKey|PresharedKey|password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+'), r'\1 = <скрыто>'),
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'), '<email>'),
    (re.compile(r'(?<!\d)(\+7|8)[\s(-]*9\d{2}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)'), '<телефон>'),
    (re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I), '<uuid>'),
    (re.compile(r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b'), lambda mm: f"{mm.group(1)}.{mm.group(2)}.{mm.group(3)}.x"
        if all(0 <= int(g) <= 255 for g in mm.groups()) else mm.group(0)),
]

def clean(t):
    for rx, rep in RX:
        t = rx.sub(rep, t)
    return re.sub(r'[ \t]+', ' ', t).strip()

# условные метки авторов: АВТОР для GubernievS, остальные U1..Un по убыванию активности
counts = collections.Counter(m.get("from_id") for m in msgs)
author_id = next((m.get("from_id") for m in msgs if (m.get("from") or "") == "GubernievS"), None)
label = {}
n = 0
for fid, _ in counts.most_common():
    if fid in special:
        label[fid] = special[fid]
    elif fid == author_id:
        label[fid] = "АВТОР"
    else:
        n += 1
        label[fid] = f"U{n}"

lines_by_month = collections.defaultdict(list)
all_lines = []
for m in msgs:
    t = clean(text_of(m))
    if not t:
        continue
    t = t.replace("\n", " ⏎ ")
    rep = m.get("reply_to_message_id")
    line = f"#{m['id']} [{m['date'][:16].replace('T', ' ')}] {label.get(m.get('from_id'), 'U?')}" \
           + (f" ↩#{rep}" if rep else "") + f": {t}"
    all_lines.append(line)
    lines_by_month[m["date"][:7]].append(line)

open(os.path.join(out, "all.txt"), "w", encoding="utf-8").write("\n".join(all_lines) + "\n")
for mon, ls in lines_by_month.items():
    open(os.path.join(out, "by-month", f"{mon}.txt"), "w", encoding="utf-8").write("\n".join(ls) + "\n")
with open(os.path.join(out, "stats.txt"), "w", encoding="utf-8") as f:
    f.write(f"messages_with_text={len(all_lines)} authors={len(label)}\n")
    for mon in sorted(lines_by_month):
        ls = lines_by_month[mon]
        f.write(f"{mon}: {len(ls)} msgs, {sum(len(x) for x in ls)} chars\n")
print(open(os.path.join(out, "stats.txt"), encoding="utf-8").read())
