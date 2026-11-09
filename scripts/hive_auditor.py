#!/usr/bin/env python3
"""hive_auditor.py — 🧬 HIVE-AUDITOR · РЕВИЗОР-2026: четвёртый слой роя.

Воплощает тренды мировой разведки 2026 (GitHub Actions Security Roadmap 2026,
OpenSSF) как УЛЕВОГО РЕВИЗОРА на весь флот:

  1. Secure defaults    — каждый `uses:` в workflow обязан быть запинен на SHA-40;
                          mutable-пины (теги/ветки) = находка.
  2. Least privilege    — workflow без блока `permissions:` = неявный write-all,
                          находка.
  3. Policy controls    — `pull_request_target` = опасный триггер-класс, находка;
                          незащищённая default-ветка и ноль rulesets = находка.
  4. Observability      — живой реестр-лидер hive_auditor_ledger.jsonl
                          (append-only) + HIVE-AUDIT.md + аларм в issue #10
                          с дедупом по отпечатку находок.

stdlib-only, идемпотент по файлам, красные прогоны не трогает (чужие слои).
Токен: env GH_TOKEN, иначе /tmp/.gt (закон №11: токен живой, проба 2026-11-09).
"""

import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# грабля №55: на раннере LANG=C → stdout/файлы в ascii — кириллица роняет скрипт.
# Броня: принудительный UTF-8 на все потоки и записи.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "https://api.github.com"
OWNER = "rtynbirf"
RUNBOOK = f"{OWNER}/github-runbook"
ALARM_ISSUE = 10
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
USES_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)", re.M)
PERM_RE = re.compile(r"^permissions:", re.M)
PRT_RE = re.compile(r"^\s*pull_request_target:", re.M)


def load_token():
    t = os.environ.get("GH_TOKEN", "").strip()
    if not t:
        with open("/tmp/.gt") as f:
            t = f.read().strip()
    return t


TOKEN = load_token()


def api(path, method="GET", body=None, accept="application/vnd.github+json"):
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", accept)
    req.add_header("User-Agent", "hive-auditor")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {}


def paginate(path, key=None):
    out, page = [], 1
    while True:
        st, d = api(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        if st != 200:
            break
        chunk = d[key] if key else d
        out.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
        if page > 30:
            break
    return out


def audit_workflow_text(text):
    """→ (mutable_uses, has_permissions, has_pull_request_target, mutable_names)"""
    mutable = []
    for m in USES_RE.finditer(text):
        ref = m.group(1)
        if "@" not in ref or ref.startswith("./"):
            continue  # локальный reusable — ок
        pin = ref.split("@", 1)[1]
        if not SHA_RE.match(pin):
            mutable.append(ref)
    return mutable, bool(PERM_RE.search(text)), bool(PRT_RE.search(text))


def audit_repo(repo):
    name = repo["name"]
    # грабля №56: кириллические имена репо/путей в URL ломают urllib (encode ascii)
    qname = urllib.parse.quote(name, safe="")
    res = {
        "repo": name,
        "private": repo.get("private", False),
        "archived": repo.get("archived", False),
        "empty": repo.get("size", 0) == 0,
        "default_branch": repo.get("default_branch") or "",
        "mutable_uses": [],
        "no_permissions": 0,
        "no_permissions_files": [],
        "pull_request_target": 0,
        "unprotected": False,
        "rulesets": 0,
        "workflows": 0,
        "findings": [],
    }
    if res["archived"]:
        res["findings"].append("archived (вне аудита)")
        return res

    # 1-2-3: workflows
    st, files = api(f"/repos/{OWNER}/{qname}/contents/.github/workflows")
    wf_names = []
    if st == 200 and isinstance(files, list):
        wf_names = [f["path"] for f in files if f["path"].endswith((".yml", ".yaml"))]
    res["workflows"] = len(wf_names)
    for path in wf_names:
        req = urllib.request.Request(API + f"/repos/{OWNER}/{qname}/contents/{urllib.parse.quote(path, safe='/')}")
        req.add_header("Authorization", f"Bearer {TOKEN}")
        req.add_header("Accept", "application/vnd.github.raw")
        req.add_header("User-Agent", "hive-auditor")
        with urllib.request.urlopen(req) as r:
            text = r.read().decode("utf-8", "replace")
        mutable, hasperm, prt = audit_workflow_text(text)
        res["mutable_uses"].extend(mutable)
        if not hasperm:
            res["no_permissions"] += 1
            res["no_permissions_files"].append(path)
        if prt:
            res["pull_request_target"] += 1

    # 4: защита default-ветки + rulesets
    db = res["default_branch"]
    if db:
        st3, _ = api(f"/repos/{OWNER}/{qname}/branches/{urllib.parse.quote(db, safe='')}/protection")
        st4, rules = api(f"/repos/{OWNER}/{qname}/rulesets")
        res["rulesets"] = len(rules) if (st4 == 200 and isinstance(rules, list)) else 0
        if st3 == 404 and res["rulesets"] == 0:
            res["unprotected"] = True

    # находки
    if res["mutable_uses"]:
        res["findings"].append(f"mutable uses ×{len(res['mutable_uses'])}")
    if res["no_permissions"]:
        res["findings"].append(f"без permissions ×{res['no_permissions']}")
    if res["pull_request_target"]:
        res["findings"].append("pull_request_target")
    if res["unprotected"]:
        res["findings"].append("default-ветка без защиты")
    return res


def score(res):
    s = 100
    s -= 10 * len(res["mutable_uses"])
    s -= 5 * res["no_permissions"]
    s -= 15 * res["pull_request_target"]
    s -= 10 if res["unprotected"] else 0
    return max(0, min(100, s))


def grade(s):
    return "A+" if s == 100 else "A" if s >= 90 else "B" if s >= 75 else "C" if s >= 60 else "D"


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = paginate("/user/repos?visibility=all&sort=full_name")
    active = [r for r in repos if not r.get("archived")]
    results = [audit_repo(r) for r in active]

    scored = sorted(results, key=score)
    hive_avg = round(sum(score(r) for r in results) / max(1, len(results)), 1)
    n_mut = sum(len(r["mutable_uses"]) for r in results)
    n_perm = sum(r["no_permissions"] for r in results)
    n_prt = sum(r["pull_request_target"] for r in results)
    n_unprot = sum(1 for r in results if r["unprotected"])

    # HIVE-AUDIT.md
    lines = [
        "# 🧬 HIVE-AUDIT · РЕВИЗОР-2026 · живой аудит флота",
        "",
        f"> Последняя ревизия: {now} UTC · тренды: GitHub Actions Security Roadmap 2026 · OpenSSF",
        "",
        f"| Показатель | Значение |",
        f"|---|---|",
        f"| Репозиториев в аудите | {len(results)} |",
        f"| Средний счёт флота | **{hive_avg}/100** |",
        f"| Mutable `uses:` (не SHA-40) | {n_mut} |",
        f"| Workflow без `permissions:` | {n_perm} |",
        f"| Опасный `pull_request_target` | {n_prt} |",
        f"| Default-ветка без защиты (и без rulesets) | {n_unprot} |",
        "",
        "| Репо | Счёт | Грейд | Находки |",
        "|---|---|---|---|",
    ]
    for r in scored:
        s = score(r)
        f = "; ".join(r["findings"]) if r["findings"] else "—"
        lines.append(f"| {r['repo']} | {s} | {grade(s)} | {f} |")
    lines += [
        "",
        "## Закон ревизора",
        "",
        "- находка ≠ приговор: ревизор ТОЛЬКО репортит, лечение — волна руками/доктором;",
        "- ledger append-only: hive_auditor_ledger.jsonl;",
        "- аларм в issue #10 — только при смене отпечатка находок (дедуп).",
        "",
    ]
    with open(os.path.join(ROOT, "HIVE-AUDIT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ledger append-only
    entry = {
        "ts": now,
        "repos": len(results),
        "hive_avg": hive_avg,
        "mutable_uses": n_mut,
        "no_permissions": n_perm,
        "pull_request_target": n_prt,
        "unprotected": n_unprot,
        "worst": [{"repo": r["repo"], "score": score(r)} for r in scored[:5]],
    }
    with open(os.path.join(ROOT, "hive_auditor_ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # дедуп-аларм
    fp = hashlib.md5(
        json.dumps(
            [[r["repo"], len(r["mutable_uses"]), r["no_permissions"], r["pull_request_target"], r["unprotected"]] for r in results],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    state_path = os.path.join(ROOT, "hive_auditor_state.json")
    prev = {}
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            prev = json.load(f)
    if prev.get("fingerprint") != fp:
        body = (
            f"🧬 **РЕВИЗОР-2026** · счёт флота {hive_avg}/100 · "
            f"mutable uses: {n_mut} · без permissions: {n_perm} · "
            f"pull_request_target: {n_prt} · без защиты ветки: {n_unprot} · "
            f"худшие: {', '.join(r['repo'] + ' ' + str(score(r)) for r in scored[:3])}\n\n"
            f"<!-- AUDITOR-FP:{fp} -->"
        )
        st, _ = api(
            f"/repos/{RUNBOOK}/issues/{ALARM_ISSUE}/comments",
            method="POST",
            body={"body": body},
        )
        print(f"аларм issue #10: HTTP {st} (отпечаток сменился)")
        prev["fingerprint"] = fp
    else:
        print("отпечаток без изменений — аларм подавлен (дедуп)")
    prev["last_run"] = now
    prev["hive_avg"] = hive_avg
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(prev, f, ensure_ascii=False, indent=1)

    print(f"РЕВИЗОР: {len(results)} репо · флот {hive_avg}/100 · mut={n_mut} perm={n_perm} prt={n_prt} unprot={n_unprot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
