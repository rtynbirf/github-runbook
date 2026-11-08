#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Часовой реестра ключей (П-74, github-runbook): ноль вечных ключей.

Читает token-registry.json и по полю expires_at считает дни до истечения:
  ≤ 7 дней (или ключ уже истёк) → 🔴 и exit 1;
  ≤ 30 дней → 🟡;
  иначе → 🟢.
Классический PAT в реестре — всегда 🔴: целевая схема это запрещает.
Нарушение схемы реестра — exit 2 (схема описана в token-registry.README.md).
Только stdlib. --selftest проверяет логику на встроенной синтетике без сети.
"""

import argparse
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RED, YELLOW, GREEN = "🔴", "🟡", "🟢"
KINDS = {"classic", "fine-grained", "app"}
DATE_LEN = 10  # длина YYYY-MM-DD


class SchemaError(ValueError):
    """Реестр не соответствует схеме из token-registry.README.md."""


def _check_date(value, field, label):
    # дата строго в формате YYYY-MM-DD, иначе реестр считается битым
    if not isinstance(value, str) or len(value) != DATE_LEN:
        raise SchemaError("%s: %s ожидался YYYY-MM-DD, получено %r" % (label, field, value))
    y, m, d = value.split("-")
    try:
        date(int(y), int(m), int(d))
    except ValueError:
        raise SchemaError("%s: %s не является датой: %r" % (label, field, value))


def validate_entry(entry, index):
    """Проверяет одну запись по схеме и возвращает её же."""
    label = "запись #%d" % index
    if not isinstance(entry, dict):
        raise SchemaError("%s: ожидался объект" % label)
    if not isinstance(entry.get("label"), str) or not entry["label"].strip():
        raise SchemaError("%s: label должен быть непустой строкой" % label)
    if entry.get("kind") not in KINDS:
        raise SchemaError("%s: kind должен быть из %s" % (label, sorted(KINDS)))
    if not isinstance(entry.get("scopes"), list):
        raise SchemaError("%s: scopes должен быть массивом" % label)
    if not isinstance(entry.get("note"), str):
        raise SchemaError("%s: note должен быть строкой" % label)
    for field in ("expires_at", "rotated_at"):
        if entry.get(field) is not None:
            _check_date(entry[field], field, entry["label"])
    return entry


def load_entries(path):
    """Читает реестр: массив сверху или объект с ключом 'entries'."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return [validate_entry(e, i) for i, e in enumerate(data["entries"])]
    if isinstance(data, list):
        return [validate_entry(e, i) for i, e in enumerate(data)]
    raise SchemaError("верхний уровень реестра: ожидался объект с 'entries' или массив")


def days_left(expires_at, today):
    """Целое число дней до истечения (отрицательное — уже истёк)."""
    y, m, d = (int(p) for p in expires_at.split("-"))
    return (date(y, m, d) - today).days


def verdict(entry, today):
    """Возвращает (вердикт, дней или None, пояснение) для валидной записи."""
    kind = entry["kind"]
    if kind == "classic":
        return RED, None, "классический PAT запрещён целевой схемой — заменить и отозвать"
    expires = entry["expires_at"]
    if expires is None:
        if kind == "app":
            return GREEN, None, "app-токен без фиксированного срока (короткоживущий)"
        return YELLOW, None, "expires_at не задан — внести дату истечения в реестр"
    left = days_left(expires, today)
    if left < 0:
        return RED, left, "истёк %d дн. назад — отозвать немедленно" % abs(left)
    if left <= 7:
        return RED, left, "истекает через %d дн. — ротировать сейчас" % left
    if left <= 30:
        return YELLOW, left, "плановая замена по календарю конверта"
    return GREEN, left, "запас больше 30 дней"


def _width(cell):
    # видимая ширина: эмодзи (код выше BMP) занимают две колонки терминала
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in cell)


def render_table(rows):
    """Текстовая таблица для stdout и $GITHUB_STEP_SUMMARY."""
    headers = ("label", "kind", "expires_at", "дней", "вердикт", "пояснение")
    body = [[str(c) for c in row] for row in rows]
    widths = [max([_width(h)] + [_width(r[i]) for r in body]) for i, h in enumerate(headers)]
    out = ["  ".join(h.ljust(widths[i] + len(h) - _width(h)) for i, h in enumerate(headers))]
    out.append("-" * len(out[0]))
    for r in body:
        out.append("  ".join(r[i].ljust(widths[i] + len(r[i]) - _width(r[i])) for i in range(len(headers))))
    return "\n".join(out)


def audit(entries, today):
    """Возвращает (строки таблицы, список 🔴-записей (label, пояснение))."""
    rows, reds = [], []
    for e in entries:
        mark, left, why = verdict(e, today)
        if mark == RED:
            reds.append((e["label"], why))
        rows.append((e["label"], e["kind"], str(e["expires_at"]),
                     "-" if left is None else str(left), mark, why))
    return rows, reds


def selftest():
    """Встроенная синтетика: пара дат + границы порогов + чтение файла через tempfile."""
    today = date(2026, 11, 9)  # фиксированная дата для воспроизводимости

    def shift(n):
        return (today + timedelta(days=n)).isoformat()

    def sample(kind, expires):
        return {"label": "syn-" + kind, "kind": kind, "scopes": [],
                "expires_at": expires, "rotated_at": None, "note": ""}

    cases = [
        ("syn-fine-red", sample("fine-grained", shift(3)), RED),
        ("syn-fine-warn", sample("fine-grained", shift(20)), YELLOW),
        ("syn-fine-ok", sample("fine-grained", shift(45)), GREEN),
        ("syn-classic", sample("classic", None), RED),
        ("syn-app", sample("app", None), GREEN),
    ]
    for name, entry, expected in cases:
        got = verdict(entry, today)[0]
        assert got == expected, (name, got, expected)
    # границы порогов: ровно 7 дней — уже 🔴, ровно 8 — ещё 🟡
    assert verdict(sample("fine-grained", shift(7)), today)[0] == RED
    assert verdict(sample("fine-grained", shift(8)), today)[0] == YELLOW
    # истёкший ключ — 🔴 с отрицательным числом дней
    mark, left, _ = verdict(sample("fine-grained", shift(-2)), today)
    assert mark == RED and left == -2, (mark, left)
    # схема: неизвестный kind должен упасть
    try:
        validate_entry({"label": "x", "kind": "super", "scopes": [], "note": ""}, 0)
    except SchemaError:
        pass
    else:
        raise AssertionError("схема пропустила неизвестный kind")
    # чтение файла {"entries": [...]} через временный каталог
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "token-registry.json"
        reg.write_text(json.dumps({"entries": [e for _, e, _ in cases]}, ensure_ascii=False),
                       encoding="utf-8")
        loaded = load_entries(reg)
        assert len(loaded) == 5, loaded
        rows, reds = audit(loaded, today)
        assert len(rows) == 5 and len(reds) == 2, (rows, reds)
        table = render_table(rows)
        assert "syn-classic" in table and RED in table
    print("SELFTEST OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Часовой реестра ключей П-74 (token-registry.json)")
    ap.add_argument("--registry", default="token-registry.json",
                    help="путь к реестру (по умолчанию token-registry.json)")
    ap.add_argument("--selftest", action="store_true", help="встроенная проверка без сети")
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    try:
        entries = load_entries(args.registry)
    except FileNotFoundError:
        print("реестр не найден: %s (создай по token-registry.README.md)" % args.registry,
              file=sys.stderr)
        return 2
    except (SchemaError, json.JSONDecodeError) as exc:
        print("реестр не соответствует схеме: %s" % exc, file=sys.stderr)
        return 2
    today = date.today()
    rows, reds = audit(entries, today)
    if rows:
        print(render_table(rows))
    else:
        print("реестр пуст: ключей нет (целевое состояние — держать так)")
    yellow = sum(1 for r in rows if r[4] == YELLOW)
    print("итого: %d ключ(ей), 🔴 %d, 🟡 %d (на %s)" % (len(rows), len(reds), yellow, today.isoformat()))
    if reds:
        print("🔴 ротировать немедленно:")
        for label, why in reds:
            print("  - %s: %s" % (label, why))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
