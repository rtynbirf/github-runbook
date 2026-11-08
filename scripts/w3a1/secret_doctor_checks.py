#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Секрет-врач · независимые гейги проверки (Волна ×3, W3-A1, issue #7).

Дополнение к врачу волны A (wave3-secret-doctor.yml + scripts/wave3/
secret_doctor.py, их не трогаем): врач ЛЕЧИТ, эти гейги ПРОВЕРЯЮТ врача и
реестр. Только stdlib 3.11, сеть не нужна — всё локально и детерминированно.
coverage — каждое имя secrets.X из воркфлоу должно быть в secret_ttl.yaml
(«ПОКРЫТИЕ: X/Y», выход 1 при дыре — критерий 3а); ttl-warn — за
warn_before_days (14) до ttl_days (90) печатает [SECRET-TTL-WARNING],
отдельный канал от инцидентного (критерий 3б); redline — в файлах не должно
быть ЗНАЧЕНИЙ секретов, печатается только файл:строка и класс формы, никогда
само совпадение (критерий 2); scan — прогон лога через append-only словарь
doctors_patterns.yaml; drill — дрилл учебного инцидента (критерий 1):
run_id и имя секрета-кандидата найдены, маркер SECRET-INCIDENT есть, значений нет.
"""
import argparse, glob, os, re
from datetime import date, timedelta

SECRET_REF = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")
# Формы ЗНАЧЕНИЙ (не имён): найденное совпадение никогда не печатается.
TOKEN_SHAPES = [
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"), "github classic token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github fine-grained PAT"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws access key id"),
    (re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"), "приватный ключ"),
]

def _split_commas(s):
    parts, buf, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == "," and not q:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p for p in parts if p.strip()]

def _flow_map(s):
    out = {}
    for part in _split_commas(s.strip()[1:-1]):
        k, _, v = part.partition(":")
        if k.strip():
            out[k.strip()] = v.strip().strip("'\"")
    return out

def parse_simple(text):
    """Мини-парсер реестров волны A (secret_ttl.yaml, doctors_patterns.yaml):
    скаляры, пустые и заполненные списки строк/flow-словарей. Только stdlib."""
    root, cur = {}, None
    for raw in text.splitlines():
        line = re.split(r"\s+#", raw.rstrip())[0]
        if not line.strip() or line.strip().startswith("#"):
            continue
        s = line.strip()
        if s.startswith("- "):
            if cur is not None:
                body = s[2:].strip()
                cur.append(_flow_map(body) if body.startswith("{") else body.strip("'\""))
            continue
        key, _, val = s.partition(":")
        key, val = key.strip(), val.strip()
        if val == "":
            cur = []
            root[key] = cur
        elif val.startswith("["):
            cur = None
            root[key] = [x.strip("'\" ") for x in _split_commas(val[1:-1])]
        elif val.startswith("{"):
            cur = None
            root[key] = _flow_map(val)
        else:
            cur = None
            root[key] = val.strip("'\"")
    return root

def load(path, what):
    if not os.path.exists(path):
        print("%s: %s не найден — придёт с волной A или бутстрапом; откладываю честно." % (what, path))
        return None
    return parse_simple(open(path, encoding="utf-8").read())

def _summary(text):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p and text:
        with open(p, "a", encoding="utf-8") as fh:  # append-only, перезаписи нет
            fh.write(text)

def cmd_coverage(args):
    ttl = load(args.ttl, "TTL-реестр")
    if ttl is None:
        return 0
    names = {str(e.get("name", "")).strip() for e in (ttl.get("secrets") or []) if isinstance(e, dict)}
    refs = set()
    for wf in sorted(glob.glob(os.path.join(args.workflows_dir, "*.y*ml"))):
        refs |= set(SECRET_REF.findall(open(wf, encoding="utf-8").read()))
    holes = sorted(r for r in refs if r not in names)
    line = "ПОКРЫТИЕ: %d/%d имён из воркфлоу прикрыто реестром secret_ttl.yaml" % (len(refs) - len(holes), len(refs))
    print(line, flush=True)
    for h in holes:
        print("ДЫРА: secrets.%s — имени нет в реестре (добавляется append-строкой)" % h)
    _summary(line + "\n" + "".join("ДЫРА: secrets.%s\n" % h for h in holes))
    return 1 if holes else 0

def cmd_ttl_warn(args):
    ttl = load(args.ttl, "TTL-реестр")
    if ttl is None:
        return 0
    ttl_days = int(ttl.get("ttl_days", 90))
    warn_days = int(ttl.get("warn_before_days", 14))
    today = date.fromisoformat(args.today) if args.today else date.today()
    rows, expired = [], 0
    for e in ttl.get("secrets") or []:
        rotated = str(e.get("rotated", "")).strip()
        if not rotated:
            continue
        deadline = date.fromisoformat(rotated) + timedelta(days=ttl_days)
        if deadline <= today:
            expired += 1
        if deadline - timedelta(days=warn_days) <= today < deadline:
            rows.append("[SECRET-TTL-WARNING] %s: ротирован %s, срок %s (TTL %d, предупреждаю за %d дн.)"
                        % (e.get("name"), rotated, deadline.isoformat(), ttl_days, warn_days))
    for r in rows:
        print(r, flush=True)
    print("TTL: предупреждений в %d-дневном окне: %d; просрочено: %d" % (warn_days, len(rows), expired))
    _summary("\n".join(rows) + ("\n" if rows else ""))
    return 0

def cmd_redline(args):
    bad = 0
    for path in args.files:
        for i, ln in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
            for rx, shape in TOKEN_SHAPES:
                if rx.search(ln):
                    bad += 1
                    print("УТЕЧКА(%s): %s:%d — форма токена; совпадение НЕ печатается" % (shape, path, i))
    print("КРАСНАЯ ЛИНИЯ: %s (проверено файлов: %d)" % ("НАРУШЕНА" if bad else "чисто", len(args.files)))
    _summary("КРАСНАЯ ЛИНИЯ: %s\n" % ("НАРУШЕНА" if bad else "чисто"))
    return 1 if bad else 0

def cmd_scan(args):
    """Словарь паттернов пополняется только добавлением строк — старые правила не ломаются."""
    pats = load(args.patterns, "Словарь паттернов")
    if pats is None:
        return 0
    rules = [p for p in (pats.get("patterns") or []) if isinstance(p, dict) and p.get("match")]
    for path in args.files:
        text = open(path, encoding="utf-8", errors="replace").read().lower()
        for p in rules:
            if str(p["match"]).lower() in text:
                print("ПАТТЕРН %s → %s (%s)" % (p["id"], p.get("incident") or "журнал", p.get("meaning")))
    return cmd_redline(args)

def cmd_drill(args):
    body = open(args.issue_file, encoding="utf-8", errors="replace").read()
    problems = []
    if args.run_id and str(args.run_id) not in body:
        problems.append("run_id %s не упомянут" % args.run_id)
    if args.secret and args.secret not in body:
        problems.append("имя секрета-кандидата %s не упомянуто" % args.secret)
    if "SECRET-INCIDENT" not in body:
        problems.append("маркера SECRET-INCIDENT нет")
    if cmd_redline(argparse.Namespace(files=[args.issue_file])) != 0:
        problems.append("красная линия нарушена: в issue просочилась форма значения")
    if problems:
        print("ДРИЛЛ: провал — " + "; ".join(problems))
        return 1
    print("ДРИЛЛ: ок — run_id и имя секрета на месте, значений нет (критерий 1, шаг проверки).")
    return 0

def main():
    ap = argparse.ArgumentParser(description="Гейги секрет-врача (issue #7, W3-A1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coverage", help="100% имён секретов в реестре")
    c.add_argument("--workflows-dir", default=".github/workflows")
    c.add_argument("--ttl", default="secret_ttl.yaml"); c.set_defaults(fn=cmd_coverage)
    t = sub.add_parser("ttl-warn", help="предупреждение за 14 дн. до 90-дневного TTL")
    t.add_argument("--ttl", default="secret_ttl.yaml")
    t.add_argument("--today", default="", help="ГГГГ-ММ-ДД; по умолчанию сегодня"); t.set_defaults(fn=cmd_ttl_warn)
    r = sub.add_parser("redline", help="в файлах нет значений секретов")
    r.add_argument("files", nargs="+"); r.set_defaults(fn=cmd_redline)
    s = sub.add_parser("scan", help="паттерны врача + красная линия")
    s.add_argument("files", nargs="+")
    s.add_argument("--patterns", default="doctors_patterns.yaml"); s.set_defaults(fn=cmd_scan)
    d = sub.add_parser("drill", help="учебный инцидент: сверка issue врача")
    d.add_argument("issue_file")
    d.add_argument("--run-id", default="")
    d.add_argument("--secret", default=""); d.set_defaults(fn=cmd_drill)
    args = ap.parse_args()
    return args.fn(args)

if __name__ == "__main__":
    raise SystemExit(main())
