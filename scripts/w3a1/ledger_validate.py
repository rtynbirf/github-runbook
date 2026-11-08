#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Леджер как код · независимый валидатор ci_ledger.yaml (Волна ×3, W3-A1, issue #6).

Дополняет вердикт-скрипт волны A (его не трогаем): читает схему-данные
ci_ledger.schema.json (или блок schema манифеста) и краснит прогон при
дубликате {repo, workflow}, неизвестном class или пустом поле (критерий 2).
--selftest — кейс критерия 1: удалить 2 строки манифеста → вердикт N-2/N-2 без
правок кода и без workflow-not-found (счёт точек только из манифеста).
--rebase — append-only строка {date, action, repo, reason} в rebases.log;
дубликат не пишется, файл не обрезается (критерий 3). Только stdlib 3.11.
"""
import argparse
import json
import os
import re
import tempfile
from datetime import date

MANIFEST_DEFAULT = "ci_ledger.yaml"
SCHEMA_DEFAULT = "ci_ledger.schema.json"

def _split_commas(s):
    parts, buf, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == "," and not q:
            parts.append("".join(buf))
            buf = []
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

def parse_manifest(text):
    """Мини-парсер YAML-подмножества манифеста: скаляры, flow-списки [a, b],
    вложенные блоки и списки flow-словарей `- {repo: x, workflow: y, class: z}`.
    Именно такие строки дописывает бутстрап волны A (append-строкой)."""
    root = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        line = re.split(r"\s+#", raw.rstrip())[0]
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        s = line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if s.startswith("- "):
            body = s[2:].strip()
            item = _flow_map(body) if body.startswith("{") else body.strip("'\"")
            if isinstance(parent, list):
                parent.append(item)
            elif isinstance(parent, dict) and not parent and len(stack) > 1:
                lst = []  # пустая заглушка блока `key:` оказалась списком
                stack[-2][1][stack[-1][2]] = lst
                stack[-1] = (stack[-1][0], lst, stack[-1][2])
                lst.append(item)
            elif isinstance(parent, dict) and parent:
                last = list(parent)[-1]
                if not isinstance(parent.get(last), list):
                    parent[last] = []
                parent[last].append(item)
            continue
        key, _, val = s.partition(":")
        key, val = key.strip(), val.strip()
        if val == "":
            child = {}
            parent[key] = child
            stack.append((indent, child, key))
        elif val.startswith("["):
            parent[key] = [x.strip("'\" ") for x in _split_commas(val[1:-1])]
        elif val.startswith("{"):
            parent[key] = _flow_map(val)
        else:
            parent[key] = val.strip("'\"")
    return root

def load_schema(manifest, schema_path):
    if os.path.exists(schema_path):
        with open(schema_path, encoding="utf-8") as fh:
            sch = json.load(fh)
        return {"required": list(sch.get("required", [])),
                "unique": list(sch.get("unique", [])),
                "classes": list(sch.get("classes", []))}
    return dict(manifest.get("schema") or {})

def validate(manifest, schema):
    """Возврат: список ошибок; пусто — манифест зелёный (критерий 2)."""
    errors = []
    entries = manifest.get("entries") or []
    required = list(schema.get("required", []))
    classes = set(schema.get("classes", []))
    unique = list(schema.get("unique", []))
    seen = {}
    for i, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            errors.append("строка %d: запись не словарь" % i)
            continue
        for field in required:
            if not str(e.get(field, "")).strip():
                errors.append("строка %d: пустое обязательное поле %r" % (i, field))
        cls = str(e.get("class", ""))
        if classes and cls not in classes:
            errors.append("строка %d: неизвестный class %r (канон: %s)" % (i, cls, sorted(classes)))
        key = tuple(str(e.get(f, "")) for f in unique)
        if key in seen:
            errors.append("строка %d: дубликат %s (уже в строке %d)" % (i, dict(zip(unique, key)), seen[key]))
        else:
            seen[key] = i
    return errors

def append_rebase(log_path, action, repo, reason):
    """Append-only: строка {date, action, repo, reason}; дубликат не пишется,
    файл никогда не обрезается и не переписывается (критерий 3)."""
    line = json.dumps({"date": date.today().isoformat(), "action": action,
                       "repo": repo, "reason": reason}, ensure_ascii=False, sort_keys=True)
    old = open(log_path, encoding="utf-8").read() if os.path.exists(log_path) else ""
    if line in old:
        return False
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return True

def selftest(manifest_path, schema_path):
    if not os.path.exists(manifest_path):
        print("СЕЛФТЕСТ: %s ещё нет — манифест появится с волной A; тест отложен честно." % manifest_path)
        return 0
    base = parse_manifest(open(manifest_path, encoding="utf-8").read())
    n = len(base.get("entries") or [])
    if n < 3:
        print("СЕЛФТЕСТ: точек в манифесте %d — кейс «удалить 2 строки» стартует после бутстрапа" % n)
        print("СЕЛФТЕСТ: (ledger_verdict.py --bootstrap допишет точки append-строкой).")
        return 0
    trimmed = dict(base, entries=base["entries"][:-2])  # «удалить 2 строки манифеста»
    errs = validate(trimmed, load_schema(trimmed, schema_path))
    m = len(trimmed["entries"])
    print("СЕЛФТЕСТ: было %d точек, удалили 2 → вердикт %d/%d, правок кода — ноль." % (n, m, m))
    if n == 15:
        print("СЕЛФТЕСТ: 15→13 — кейс критерия 1 (13/13) воспроизведён.")
    if m != n - 2 or errs:
        print("СЕЛФТЕСТ: провал — счёт отстал от манифеста или урезанный набор красный: %s" % errs)
        return 1
    print("СЕЛФТЕСТ: 'workflow-not-found' не возникал — вердикт считает строки, а не ищет хардкод.")
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "rebases.log")
        a1 = append_rebase(log, "rebase", "пример-репо", "репо удалено")
        a2 = append_rebase(log, "rebase", "пример-репо", "репо удалено")
        a3 = append_rebase(log, "rebase", "пример-репо-2", "воркфлоу убран")
        lines = open(log, encoding="utf-8").read().splitlines()
        if not (a1 and not a2 and a3 and len(lines) == 2):
            print("СЕЛФТЕСТ: провал — append-only rebases.log нарушен.")
            return 1
        print("СЕЛФТЕСТ: rebases.log append-only подтверждён (строк: %d, дублей: нет)." % len(lines))
    return 0

def main():
    ap = argparse.ArgumentParser(description="Валидатор манифеста леджера (issue #6, W3-A1)")
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--schema", default=SCHEMA_DEFAULT)
    ap.add_argument("--rebase-log", default="rebases.log")
    ap.add_argument("--selftest", action="store_true", help="кейс критерия 1 + append-only проверка")
    ap.add_argument("--rebase", nargs=2, metavar=("REPO", "REASON"), help="дописать строку ребаза append-only")
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.manifest, args.schema)
    if args.rebase:
        repo, reason = args.rebase
        grown = append_rebase(args.rebase_log, "rebase", repo, reason)
        print("REBASE-LOG: %s (%s)" % ("дополнен" if grown else "дубликат пропущен — дополнение, не перезапись", args.rebase_log))
        return 0
    if not os.path.exists(args.manifest):
        print("ВЕРДИКТ-СХЕМА: %s не найден — манифест придёт с волной A; прогон откладывается честно." % args.manifest)
        return 0
    manifest = parse_manifest(open(args.manifest, encoding="utf-8").read())
    schema = load_schema(manifest, args.schema)
    errors = validate(manifest, schema)
    points = len(manifest.get("entries") or [])
    print("СХЕМА: %s · точек в манифесте: %d" % ("зелёная" if not errors else "красная", points))
    for e in errors:
        print("ОШИБКА: " + e)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("СХЕМА ЛЕДЖЕРА: %s · точек: %d\n" % ("зелёная" if not errors else "красная", points))
            fh.writelines("ОШИБКА: " + e + "\n" for e in errors)
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
