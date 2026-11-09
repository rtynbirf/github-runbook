#!/usr/bin/env python3
"""hive_doctor.py — 🩺 HIVE-DOCTOR: самолечение ГИГИЕНЫ флота.

Слои улья: hive-sentry лечит CI-фантомов (dispatch), hive-doctor лечит гигиену:
  • нет SECURITY.md            → кладёт корневой SECURITY.md (флот-стандарт улья)
  • нет .github/dependabot.yml → кладёт ГРУППОВОЙ МЕСЯЧНЫЙ конфиг (практика
    GitHub Blog 2026 «Tame Dependabot»: одна проверяемая пачка вместо ручья PR)
  • пусто topics / description → PATCH ["hive"] / нейтральное описание
Безопасность: только stdlib; создаёт ТОЛЬКО отсутствующие файлы (идемпотент,
ничего не перезаписывает); патч settings требует admin — PAT улья его имеет.

    GH_TOKEN=... python3 scripts/hive_doctor.py --repo all|ИМЯ [--apply]

Без --apply — только план лечения (что бы сделано было), ничего не меняет.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

OWNER = "rtynbirf"
CAND = {
    "security": ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md"),
    "dependabot": (".github/dependabot.yml", ".github/dependabot.yaml"),
}
MANIFESTS = {
    "npm": ("package.json", "package-lock.json"),
    "pip": ("requirements.txt", "pyproject.toml"),
}

SECURITY_MD = """# 🛰 Политика безопасности (флот-стандарт улья rtynbirf)

## Как сообщить об уязвимости
- Открой issue в этом репозитории; для приватных деталей запроси закрытый канал.
- Прилагай факты (закон улья №2 «факт = байты»): репродукцию, версии, логи.

## Поддерживаемые версии
- ветка `main` — поддерживается.

## SLA
- подтверждение получения: 72 часа
- разбор и выпуск фикса: по критичности
"""

DEPENDABOT_HEAD = """\
# 🛰 hive-doctor: флот-стандарт улья — групповые месячные батчи
# (практика GitHub Blog 2026 «Tame Dependabot»: меньше шума, одна пачка на ревью).
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
    groups:
      monthly-batch:
        patterns: ["*"]
"""

DEPENDABOT_ENTRY = """
  - package-ecosystem: "{eco}"
    directory: "/"
    schedule:
      interval: "monthly"
    groups:
      monthly-batch:
        patterns: ["*"]
"""


def tok():
    for k in ("GH_TOKEN", "HIVE_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v.strip()
    if os.path.exists("/tmp/.gt"):
        with open("/tmp/.gt") as f:
            return f.read().strip()
    sys.exit("нет токена: GH_TOKEN/HIVE_TOKEN или /tmp/.gt")


T = tok()


def api(url, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {T}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        return e.code, body


def tree_paths(repo, branch):
    st, d = api(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    if st != 200:
        return None
    if d.get("truncated"):
        return "TRUNC"
    return {t["path"] for t in d.get("tree", []) if t.get("type") == "blob"}


def put_file(repo, branch, path, content, message):
    st, cur = api(f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}")
    sha = cur.get("sha") if st == 200 else None
    if sha:
        return False, "файл уже есть — не трогаю (идемпотент)"
    body = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    st, res = api(f"https://api.github.com/repos/{repo}/contents/{path}", method="PUT", payload=body)
    return st in (200, 201), f"HTTP {st}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="all")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--state", default="HIVE-STATE.json")
    args = ap.parse_args()

    rows = None
    if os.path.exists(args.state):
        with open(args.state) as f:
            state = json.load(f)
        rows = state.get("rows") or []
    targets = []
    if args.repo != "all":
        targets = [args.repo]
    elif rows:
        targets = [r["repo"] for r in rows if not r.get("archived")]
    else:
        st, d = api(f"https://api.github.com/users/{OWNER}/repos?per_page=100&sort=full_name")
        targets = [r["name"] for r in (d or []) if not r.get("archived")]

    plan, fixed = [], 0
    for name in targets:
        repo = f"{OWNER}/{name}"
        st, meta = api(f"https://api.github.com/repos/{repo}")
        time.sleep(0.15)
        if st != 200 or meta.get("archived"):
            plan.append(f"[SKIP] {name}: недоступен или архив")
            continue
        branch = meta.get("default_branch") or "main"
        paths = tree_paths(repo, branch)
        time.sleep(0.15)
        todo = []
        if paths is None:
            plan.append(f"[SKIP] {name}: пустой репо (нет ветки {branch})")
            continue
        truncated = paths == "TRUNC"
        def has(cands):
            if truncated:
                return any(api(f"https://api.github.com/repos/{repo}/contents/{p}?ref={branch}")[0] == 200 for p in cands)
            return any(c in paths for c in cands)

        if not has(CAND["security"]):
            todo.append(("security", name, branch, "SECURITY.md", SECURITY_MD,
                         "🛰 hive-doctor: +SECURITY.md (флот-стандарт улья)"))
        if not has(CAND["dependabot"]):
            extras = ""
            if not truncated:
                for eco, mans in MANIFESTS.items():
                    if any(m in paths for m in mans):
                        extras += DEPENDABOT_ENTRY.format(eco=eco)
            todo.append(("dependabot", name, branch, ".github/dependabot.yml",
                         DEPENDABOT_HEAD + extras,
                         "🛰 hive-doctor: +dependabot.yml (групповой месячный, GitHub Blog 2026)"))
        if not meta.get("topics") or not meta.get("description"):
            patch = {}
            if not meta.get("topics"):
                patch["topics"] = ["hive"]
            if not meta.get("description"):
                patch["description"] = "🛰 часть улья rtynbirf (fleet, hive-scorecard)"
            todo.append(("settings", name, branch, patch, None, "🛰 hive-doctor: topics/description"))

        if not todo:
            plan.append(f"[OK] {name}: гигиена полная — лечить нечего")
            continue
        plan.append(f"[PLAN] {name}: " + ", ".join(
            {"security": "+SECURITY.md", "dependabot": "+dependabot.yml",
             "settings": "+topics/description"}[t[0]] for t in todo))
        if args.apply:
            for kind, rname, br, obj, content, msg in todo:
                if kind == "settings":
                    st2, _ = api(f"https://api.github.com/repos/{OWNER}/{rname}",
                                 method="PATCH", payload=obj)
                    ok, info = st2 == 200, f"HTTP {st2}"
                else:
                    ok, info = put_file(repo, br, obj, content, msg)
                if ok:
                    fixed += 1
                    plan.append(f"[FIX] {rname}: {obj if isinstance(obj, str) else '+settings'} — {info}")
                else:
                    plan.append(f"[FAIL] {rname}: {obj if isinstance(obj, str) else '+settings'} — {info}")
                time.sleep(0.2)

    print("🩺 HIVE-DOCTOR", "— ЛЕЧЕНИЕ ПРИМЕНЕНО" if args.apply else "— ТОЛЬКО ПЛАН (--apply не задан)")
    for line in plan:
        print(" ", line)
    print(f"  итог: применено {fixed} правок по {len(targets)} репо")


if __name__ == "__main__":
    main()
