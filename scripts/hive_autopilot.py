#!/usr/bin/env python3
"""hive_autopilot.py — 🚀 HIVE-AUTOPILOT: самолечение находок ревизора (волна ×15).

Канон: OSPS Baseline v2026.08.28 — AC-03.01 (enforcement-механизм на primary
branch) и AC-04.01 (CI/CD по умолчанию в минимальных привилегиях).

Два безопасных класса лечения (больше ничего — закон автопилота):
  1. Workflow без top-level `permissions:` → добавить умолчание
     `permissions: contents: read` (job-level гранты НЕ трогаются: там, где
     нужен write, они уже стоят — факт ревизии ×14). Прямое следствие AC-04.01.
  2. Репо с незащищённой default-веткой → ruleset enforcement=active:
     запрет force-push и удаления (~DEFAULT_BRANCH). Прямые push Хозяина
     НЕ ломаются (required-PR намеренно НЕ ставим — улье solo-flow).

Канон доктора: план (--apply=false) → лечение (--apply=true). Идемпотент:
лечит только то, что ревизор нашёл СЕЙЧАС; повторный прогон — ноль правок.
Артефакты: hive_autopilot_ledger.jsonl (append-only) + печать в stdout.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hive_auditor as H  # noqa: E402  (токен, api, paginate, audit_repo — один источник правды)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = H.ROOT
RUNBOOK_REPO = "rtynbirf/github-runbook"


def api(path, method="GET", body=None, accept="application/vnd.github+json"):
    return H.api(path, method=method, body=body, accept=accept)


def raw_file(repo, path):
    qname = urllib.parse.quote(repo, safe="")
    qpath = urllib.parse.quote(path, safe="/")
    req = urllib.request.Request(H.API + f"/repos/{H.OWNER}/{qname}/contents/{qpath}")
    req.add_header("Authorization", f"Bearer {H.TOKEN}")
    req.add_header("Accept", "application/vnd.github.raw")
    req.add_header("User-Agent", "hive-autopilot")
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", "replace")


def get_file_sha(repo, path):
    qname = urllib.parse.quote(repo, safe="")
    qpath = urllib.parse.quote(path, safe="/")
    st, d = api(f"/repos/{H.OWNER}/{qname}/contents/{qpath}")
    return d.get("sha") if st == 200 else None


def patch_permissions(repo, path):
    """Top-level permissions: contents:read (AC-04.01). Возврат: None = не менял."""
    text = raw_file(repo, path)
    if H.PERM_RE.search(text):
        return None  # уже лечён
    new_text = text.rstrip("\n") + "\n\npermissions:\n  contents: read\n"
    st, d = api(
        f"/repos/{H.OWNER}/{urllib.parse.quote(repo, safe='')}/contents/{urllib.parse.quote(path, safe='/')}",
        method="PUT",
        body={
            "message": "🚀 автопилот ×15: top-level permissions contents:read (OSPS AC-04.01)",
            "content": __import__("base64").b64encode(new_text.encode()).decode(),
            "sha": get_file_sha(repo, path),
        },
    )
    return st


def ensure_ruleset(repo, db):
    """Ruleset: запрет force-push/удаления primary (AC-03.01), прямые push живы."""
    qname = urllib.parse.quote(repo, safe="")
    st, existing = api(f"/repos/{H.OWNER}/{qname}/rulesets")
    if st == 200 and isinstance(existing, list):
        for r in existing:
            if str(r.get("name", "")).startswith("автопилот"):
                return "уже есть"
    body = {
        "name": "автопилот: защита primary (OSPS-AC-03.01)",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
        "bypass_actors": [],
    }
    st, d = api(f"/repos/{H.OWNER}/{qname}/rulesets", method="POST", body=body)
    if st in (201, 202):
        return f"ruleset id {d.get('id')}"
    return f"HTTP {st}: {d.get('message', 'ошибка')[:80]}"


def has_deletion_ruleset(repo):
    """→ True если есть active-ruleset с запретом удаления (OSPS AC-03.02).
    Грабля: LIST rulesets НЕ возвращает поле rules — нужен GET каждого ruleset."""
    q = urllib.parse.quote(repo, safe="")
    st, rules = api(f"/repos/{H.OWNER}/{q}/rulesets")
    if st != 200 or not isinstance(rules, list):
        return False
    for r in rules:
        if r.get("enforcement") != "active":
            continue
        st2, full = api(f"/repos/{H.OWNER}/{q}/rulesets/{r['id']}")
        if st2 == 200 and any(
            x.get("type") == "deletion" for x in full.get("rules", [])
        ):
            return True
    return False


def main():
    apply = "--apply=true" in sys.argv
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = H.paginate("/user/repos?visibility=all&sort=full_name")
    active = [r for r in repos if not r.get("archived")]

    plan = []
    for r in active:
        res = H.audit_repo(r)
        for p in res["no_permissions_files"]:
            plan.append(("permissions", r["name"], p))
        if res["unprotected"]:
            plan.append(("ruleset", r["name"], res["default_branch"]))
        elif not res["empty"] and not r.get("private") and not has_deletion_ruleset(r["name"]):
            # OSPS AC-03.02: непубличные непустые репо без правил защиты.
            # Приватные пропускаем: rulesets там платформенно заперты за GitHub Pro (живой 403 §×16).
            plan.append(("ruleset", r["name"], res["default_branch"]))

    print(f"🚀 АВТОПИЛОТ {now}: план лечения {len(plan)} позиц.")
    for kind, repo, obj in plan:
        if not apply:
            print(f"  [ПЛАН] {kind}: {repo} → {obj}")
            continue
        if kind == "permissions":
            out = patch_permissions(repo, obj)
            print(f"  [ЛЕЧУ] permissions: {repo}/{obj} → {'PUT ' + str(out) if out else 'пропуск'}")
        else:
            out = ensure_ruleset(repo, obj)
            print(f"  [ЛЕЧУ] ruleset: {repo} → {out}")

    entry = {"ts": now, "apply": apply, "planned": len(plan),
             "actions": [{"kind": k, "repo": r, "target": o} for k, r, o in plan]}
    with open(os.path.join(ROOT, "hive_autopilot_ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if not plan:
        print("✅ флоту лечение не нужно — ревизор чист")
    return 0


if __name__ == "__main__":
    sys.exit(main())
