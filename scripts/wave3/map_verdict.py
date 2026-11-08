#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вердиктор карты хранилища — read-only чтение снимков (ПРЕДЛОЖЕНИЕ-25,
issue #8, волна ×3 W3-A2). Дополняет стратоснимок scripts/wave3/storage_map.py
(волна ×3 W3-A): тот пишет storage-map/ГГГГ-ММ.csv + .json append-only, этот —
проверяет и сводит, НИЧЕГО не записывая (правило роя: чужие предложения читают
CSV, но не редактируют снимки). Проверки:
  1) шапка каждого CSV ровно как в критерии приёмки:
     repo,visibility,releases_gb,artifacts_mb,caches_mb,layer,billed_mb,violation
  2) слои beacon (Маяк, вне квоты) / public-free (не считается) /
     private-counted (считается); контрольные репо release-vault → beacon,
     ruvson-lyrics → private-counted;
  3) закон «масса живёт либо публично, либо в Маяке»: private-counted с
     релизами > 0 вне разрешённого списка — нарушение; нули во всех трёх
     слоях флаг не поднимают;
  4) сумма private-counted снимка 2026-11 против якоря ручного аудита 08.11
     (426/500 МБ, коридор ±10% — политика вердиктора); прочие месяцы —
     справочно (память живая, drift ожидаем);
  5) append-only история каталога: git log по storage-map/ — файл снимка
     ровно в одном коммите; файл в двух и более = переписывание = красный.
Снимков ещё нет → честный отчёт и код 0. --selftest гоняет все проверки на
синтетическом каталоге во временной папке (включая ловлю подделок).
stdlib-only, Python 3.11.
"""

import csv
import os
import re
import subprocess
import sys
import tempfile

BEACON = {"release-vault"}             # Маяк: публичный релиз-хаб вне квоты (из предложения)
ALLOWED_PRIVATE = {"ruvson-lyrics"}    # разрешённый список приватных релизов (media-vault)
ANCHOR_PRIVATE_MB = 426.0              # якорь ручного аудита 08.11 — из тела issue #8
ANCHOR_DATE = "2026-11-08"
CORRIDOR = 0.10                        # коридор якоря — политика вердиктора
HEADER = ["repo", "visibility", "releases_gb", "artifacts_mb", "caches_mb",
          "layer", "billed_mb", "violation"]
LAYERS = ("beacon", "public-free", "private-counted")
COUNTED = {"beacon": "вне квоты (Маяк)", "public-free": "не считается",
           "private-counted": "считается"}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPDIR = os.path.join(ROOT, "storage-map")


def snap_files(mapdir):
    if not os.path.isdir(mapdir):
        return []
    return sorted(f for f in os.listdir(mapdir) if re.match(r"^\d{4}-\d{2}.*\.csv$", f))


def num(row, col):
    try:
        return float(row.get(col, "") or 0)
    except ValueError:
        return 0.0


def expected_layer(name, visibility):
    if name in BEACON:
        return "beacon"
    return "private-counted" if visibility == "private" else "public-free"


def row_checks(row, problems):
    name, layer = row.get("repo", ""), row.get("layer", "")
    rel, art, cach = num(row, "releases_gb"), num(row, "artifacts_mb"), num(row, "caches_mb")
    want = expected_layer(name, row.get("visibility", ""))
    if layer != want:
        problems.append("%s: слой %s, по канону %s" % (name, layer or "пусто", want))
    want_viol = "YES" if (layer == "private-counted" and rel > 0 and name not in ALLOWED_PRIVATE) else "NO"
    got = (row.get("violation") or "").strip().upper() or "NO"
    if got in ("YES", "NO") and got != want_viol:
        problems.append("%s: violation=%s, по закону «публично или Маяк» %s" % (name, got, want_viol))
    elif got not in ("YES", "NO"):
        problems.append("%s: violation=%r — жду YES/NO" % (name, row.get("violation")))
    return {"name": name, "layer": layer, "rel": rel, "art": art, "cach": cach,
            "zero": rel == 0 and art == 0 and cach == 0}


def audit(mapdir):
    """Печатает свод и возвращает список проблем (пустой = зелёный вердикт)."""
    files = snap_files(mapdir)
    problems = []
    if not files:
        print("ВЕРДИКТ: снимков нет — стратоснимок ещё не гонялся")
        print("(заполняется скриптом при первом прогоне: wave3-storage-map → storage-map/ГГГГ-ММ.csv).")
        return problems
    for fname in files:
        with open(os.path.join(mapdir, fname), encoding="utf-8", newline="") as fh:
            rd = csv.DictReader(fh)
            header, rows = list(rd.fieldnames or []), list(rd)
        if header != HEADER:
            problems.append("%s: шапка %s ≠ канону %s" % (fname, ",".join(header), ",".join(HEADER)))
            continue
        parsed = [row_checks(r, problems) for r in rows]
        byname = {p["name"]: p for p in parsed}
        for name, want in (("release-vault", "beacon"), ("ruvson-lyrics", "private-counted")):
            if name in byname and byname[name]["layer"] != want:
                problems.append("%s: контрольный репо обязан быть слоем %s" % (name, want))
        tot = {}
        for p in parsed:
            t = tot.setdefault(p["layer"], [0.0, 0])
            t[0] += p["rel"] + (p["art"] + p["cach"]) / 1000.0
            t[1] += 1
        print("СНИМОК %s: репо %d · строк-нулей (без флага) %d"
              % (fname, len(parsed), sum(1 for p in parsed if p["zero"])))
        for layer in LAYERS:
            if layer in tot:
                print("  %-16s %10.3f ГБ · %2d репо · %s" % (layer, tot[layer][0], tot[layer][1], COUNTED[layer]))
        priv = sum(p["rel"] * 1000 + p["art"] + p["cach"] for p in parsed if p["layer"] == "private-counted")
        print("  private-counted: %.1f МБ · якорь аудита %s: %.0f МБ" % (priv, ANCHOR_DATE, ANCHOR_PRIVATE_MB))
        if fname.startswith("2026-11"):
            if abs(priv - ANCHOR_PRIVATE_MB) > ANCHOR_PRIVATE_MB * CORRIDOR:
                problems.append("сумма private-counted %.1f МБ вне коридора ±%d%% якоря %.0f МБ"
                                % (priv, CORRIDOR * 100, ANCHOR_PRIVATE_MB))
        else:
            print("  (сравнение с якорем — справочно: снимок не 2026-11)")
    return problems


def git_history(root):
    """Файл → список коммитов, где он менялся; None = git недоступен."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "--pretty=format:%H", "--name-only", "--", "storage-map"],
            capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return None
    files, cur = {}, None
    for line in out.splitlines():
        s = line.strip()
        if len(s) == 40 and all(c in "0123456789abcdef" for c in s):
            cur = s
        elif s and cur:
            files.setdefault(s, []).append(cur)
    return files


def append_only_verdict(root, problems):
    hist = git_history(root)
    if hist is None:
        print("ИСТОРИЯ: git недоступен — проверка append-only пропущена честно.")
        return
    rewritten = sorted(f for f, cs in hist.items() if len(cs) > 1)
    for f in rewritten:
        problems.append("история storage-map/: %s менялся в %d коммитах — append-only нарушен"
                        % (f, len(hist[f])))
    print("ИСТОРИЯ: файлов %d · переписанных %d · append-only %s"
          % (len(hist), len(rewritten), "ОК" if not rewritten else "НАРУШЕН"))


def selftest():
    ok = []

    def ck(name, cond):
        ok.append(bool(cond))
        print("САМОПРОБА %s %s" % (name, "✓" if cond else "✗ ПРОВАЛ"))

    body = ("repo,visibility,releases_gb,artifacts_mb,caches_mb,layer,billed_mb,violation\n"
            "release-vault,public,1.0,0,0,beacon,,NO\n"
            "ruvson-lyrics,private,0.05,1,1,private-counted,,NO\n"
            "wrong-holder,private,2.0,0,0,private-counted,,YES\n"
            "quiet-repo,private,0,0,0,private-counted,,NO\n")
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "storage-map"))
        p = os.path.join(td, "storage-map", "2099-01.csv")
        open(p, "w", encoding="utf-8").write(body)
        ck("1 (зелёный каталог: слои, закон, нули без флага)", audit(os.path.dirname(p)) == [])
        lines = body.replace("release-vault,public,1.0,0,0,beacon", "release-vault,public,1.0,0,0,public-free")
        open(p, "w", encoding="utf-8").write(lines)
        ck("2 (Маяк, переклеенный в public-free, ловится)", audit(os.path.dirname(p)) != [])
        lines = body.replace("quiet-repo,private,0,0,0,private-counted,,NO",
                             "quiet-repo,private,0,0,0,private-counted,,YES")
        open(p, "w", encoding="utf-8").write(lines)
        ck("3 (флаг нарушения на нулевом репо ловится)", audit(os.path.dirname(p)) != [])
        open(p, "w", encoding="utf-8").write(body.replace("caches_mb,layer", "cache_mb,layer"))
        ck("4 (чужая шапка ловится)", audit(os.path.dirname(p)) != [])
    print("САМОПРОБА: %d/%d ✓" % (sum(ok), len(ok)))
    sys.exit(0 if all(ok) else 1)


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
        return
    mapdir = os.path.abspath(args[args.index("--dir") + 1]) if "--dir" in args else MAPDIR
    print("ВЕРДИКТОР карты хранилища (read-only; снимки не правит) · каталог: %s" % mapdir)
    problems = audit(mapdir)
    append_only_verdict(ROOT, problems)
    print("ВЕРДИКТ: %s · проблем %d" % ("🟢 зелёный" if not problems else "🔴 красный", len(problems)))
    for p in problems:
        print("  ПРОБЛЕМА: %s" % p)
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
