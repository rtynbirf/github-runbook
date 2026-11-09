#!/usr/bin/env python3
"""hive_scorecard.py — 🧬 HIVE-SCORECARD: третий слой роя.

Слои улья:  hive-control (пульт вердиктов) → hive-sentry (самопочинка CI-фантомов)
          → HIVE-SCORECARD (этот скрипт: счёт гигиены и CI 0–100 каждому репо).

Мировая практика 2026, вшитая в счёт:
  • OpenSSF Scorecard — эвристическая оценка безопасности 0–10, здесь адаптирована
    под приватный флот (веса: SECURITY.md 20, CODEOWNERS 10, LICENSE 10, README 10,
    description 10, topics 5, workflows 15, dependabot 10, зелёный CI на HEAD 10);
  • GitHub Blog «Tame Dependabot» (2026) — групповые месячные батчи (см. hive-doctor);
  • StepSecurity/Wiz hardening — SHA-pin и least-privilege во всех workflow дома.

У мира этого НЕТ: OpenSSF Scorecard не видит приватные репо и не ранжирует флот,
gitfitcheck и exporters не поднимают приватные 42 репо одним взглядом. Только stdlib.

Вход:  HIVE-STATE.json (fact = байты от hive-control) — вердикты CI на HEAD,
       dependabot, issues. Гигиена дерева дотягивается живым API.
Выход: HIVE-SCORECARD.md (ранжирование «худшие сверху»), HIVE-SCORES.json (машина),
       hive_scorecard_ledger.jsonl (append-only), аларм в issue #10 при 🔴
       (дедуп: тот же отпечаток красных в тот же день МСК не повторяется).

    GH_TOKEN=... python3 scripts/hive_scorecard.py [--state HIVE-STATE.json]
                   [--out .] [--dry-run] [--stamp] [--quiet]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = "rtynbirf"
MSK = timezone(timedelta(hours=3))
WEIGHTS = {
    "security": 20, "codeowners": 10, "license": 10, "readme": 10,
    "description": 10, "topics": 5, "workflows": 15, "dependabot": 10,
    "ci_green": 10,
}
GAP_NAMES = {
    "security": "sec", "codeowners": "co", "license": "lic", "readme": "readme",
    "description": "desc", "topics": "topics", "workflows": "wf", "dependabot": "dep",
}
CAND = {
    "security": ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md"),
    "codeowners": ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"),
    "license": ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", ".github/LICENSE"),
    "readme": ("README.md", "README", "readme.md", "README.rst", "README.MD"),
    "dependabot": (".github/dependabot.yml", ".github/dependabot.yaml"),
}


def tok():
    # HIVE_TOKEN (PAT улья) первичен: GITHUB_TOKEN в Actions может быть зажат
    # политикой аккаунта (без issues:write) — PAT гарантированно комментирует.
    for k in ("HIVE_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v.strip()
    if os.path.exists("/tmp/.gt"):
        with open("/tmp/.gt") as f:
            return f.read().strip()
    sys.exit("нет токена: HIVE_TOKEN/GH_TOKEN или /tmp/.gt")


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


def file_exists(repo, path, branch):
    st, _ = api(f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}")
    return st == 200


def wf_count(repo, branch):
    st, d = api(f"https://api.github.com/repos/{repo}/contents/.github/workflows?ref={branch}")
    if st == 200 and isinstance(d, list):
        return len(d)
    return 0


def hygiene(repo, branch, dep_known):
    h = {k: False for k in ("security", "codeowners", "license", "readme", "dependabot", "workflows")}
    paths = tree_paths(repo, branch)
    if paths == "TRUNC":
        for k in ("security", "codeowners", "license", "readme"):
            h[k] = any(file_exists(repo, p, branch) for p in CAND[k])
        h["dependabot"] = dep_known
        h["workflows"] = wf_count(repo, branch)
    elif isinstance(paths, set):
        for k in ("security", "codeowners", "license", "readme"):
            h[k] = any(c in paths for c in CAND[k])
        h["dependabot"] = dep_known or any(c in paths for c in CAND["dependabot"])
        h["workflows"] = sum(
            1 for p in paths
            if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
            and "/" not in p[len(".github/workflows/"):]
        )
    else:
        return None
    return h


def score_repo(h, meta, ci_ok):
    s = 0
    if h["security"]:
        s += WEIGHTS["security"]
    if h["codeowners"]:
        s += WEIGHTS["codeowners"]
    if h["license"]:
        s += WEIGHTS["license"]
    if h["readme"]:
        s += WEIGHTS["readme"]
    if meta.get("description"):
        s += WEIGHTS["description"]
    if meta.get("topics"):
        s += WEIGHTS["topics"]
    if h["workflows"] > 0:
        s += WEIGHTS["workflows"]
    if h["dependabot"]:
        s += WEIGHTS["dependabot"]
    if ci_ok:
        s += WEIGHTS["ci_green"]
    return s


def grade(s):
    if s >= 90:
        return "A+"
    if s >= 80:
        return "A"
    if s >= 65:
        return "B"
    if s >= 50:
        return "C"
    if s >= 30:
        return "D"
    return "E"


def gaps_of(h, meta):
    g = []
    for k, name in GAP_NAMES.items():
        if k == "description":
            if not meta.get("description"):
                g.append(name)
        elif k == "topics":
            if not meta.get("topics"):
                g.append(name)
        elif not h[k]:
            g.append(name)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="HIVE-STATE.json")
    ap.add_argument("--out", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    with open(args.state) as f:
        state = json.load(f)
    rows = state["rows"]
    reds = state.get("reds", [])
    now = datetime.now(MSK)
    ts = now.strftime("%d.%m.%Y %H:%M МСК")
    ledger_path = os.path.join(args.out, "hive_scorecard_ledger.jsonl")

    scores, grades_hist = [], {}
    for row in rows:
        name = row["repo"]
        repo = f"{OWNER}/{name}"
        rec = {"repo": name, "archived": bool(row.get("archived")),
               "private": None, "fork": None, "ci": "—", "open_issues": row.get("open_issues", 0),
               "push_days": None, "score": None, "grade": "—", "gaps": [], "gone": False}
        wfs = row.get("workflows") or []
        rec["ci"] = "🔴" if any(w.get("conclusion") == "failure" for w in wfs) else (
            "🟢" if wfs else "⚪")
        if row.get("archived"):
            rec["grade"] = "🗄"
            scores.append(rec)
            continue
        branch = row.get("default_branch") or "main"
        st, meta = api(f"https://api.github.com/repos/{repo}")
        time.sleep(0.15)
        if st != 200:
            rec["gone"] = True
            scores.append(rec)
            continue
        rec["private"] = bool(meta.get("private"))
        rec["fork"] = bool(meta.get("fork"))
        pushed = meta.get("pushed_at")
        if pushed:
            rec["push_days"] = max(0, (datetime.now(timezone.utc)
                                       - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days)
        h = hygiene(repo, branch, bool(row.get("dependabot")))
        time.sleep(0.15)
        if h is None:
            rec["gone"] = True
            scores.append(rec)
            continue
        ci_ok = bool(wfs) and all(w.get("conclusion") == "success" for w in wfs)
        s = score_repo(h, meta, ci_ok)
        rec.update(score=s, grade=grade(s), gaps=gaps_of(h, meta))
        grades_hist[rec["grade"]] = grades_hist.get(rec["grade"], 0) + 1
        scores.append(rec)

    scored = [r for r in scores if isinstance(r.get("score"), int)]
    avg = round(sum(r["score"] for r in scored) / len(scored), 1) if scored else 0
    red_repos = sorted({r["repo"] for r in scores if r["ci"] == "🔴"})
    total_open = sum(r["open_issues"] or 0 for r in scores)

    order = {"A+": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "—": 6, "🗄": 7}
    ranked = sorted(scores, key=lambda r: (order.get(r["grade"], 6), -(r["score"] or 0), r["repo"]))
    worst_first = sorted(scored, key=lambda r: (r["score"], r["repo"]))

    hist = " · ".join(f"{g}×{c}" for g, c in sorted(grades_hist.items())) or "—"
    lines = [
        "# 🧬 HIVE-SCORECARD · счёт гигиены и CI улья (0–100)",
        "",
        f"**Снимок: {ts} · факт = байты (API)**",
        "",
        f"**{len(rows)} репо** · средний счёт **{avg}/100** · 🔴 CI: {len(red_repos)} · "
        f"📥 открытых issues: {total_open}",
        f"Грейды: {hist}",
        "",
        "Слои улья: [HIVE-DASHBOARD.md](HIVE-DASHBOARD.md) — вердикты CI и артефакты "
        "(hive-control) · hive-sentry — самопочинка фантомов · **этот файл — счёт и пробелы гигиены**.",
        "",
        "| Репо | Счёт | Grade | CI | 📥 | Push | Пробелы гигиены |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ranked:
        link = f"[{r['repo']}](https://github.com/{OWNER}/{r['repo']})"
        lock = " 🔒" if r.get("private") else ""
        push = f"{r['push_days']}д" if r.get("push_days") is not None else "—"
        gaps = "·".join(r["gaps"]) if r["gaps"] else "✅"
        lines.append(f"| {link}{lock} | {r['score'] if r['score'] is not None else '—'} "
                     f"| {r['grade']} | {r['ci']} | {r['open_issues']} | {push} | {gaps} |")
    lines += [
        "",
        "## ⚖️ Вес счёта (эвристики OpenSSF Scorecard, адаптированы под флот)",
        "",
        "`SECURITY.md 20 · CODEOWNERS 10 · LICENSE 10 · README 10 · description 10 · "
        "topics 5 · workflows 15 · dependabot 10 · зелёный CI на HEAD 10`",
        "",
        "Грейды: **A+** ≥90 · **A** ≥80 · **B** ≥65 · **C** ≥50 · **D** ≥30 · **E** <30 · "
        "🗄 архив · — нет данных. Пуш свежее 180 дней считается нормой; колонка — справочная.",
        "",
        f"_{ts} · hive-scorecard v1 · append-only журнал: hive_scorecard_ledger.jsonl_",
    ]
    md = "\n".join(lines) + "\n"

    snapshot = {
        "timestamp": ts,
        "repos_total": len(rows),
        "avg_score": avg,
        "grades": grades_hist,
        "reds": red_repos,
        "open_issues": total_open,
        "repos": [
            {k: v for k, v in r.items() if k != "gone"} for r in ranked
        ],
    }

    md_path = os.path.join(args.out, "HIVE-SCORECARD.md")
    json_path = os.path.join(args.out, "HIVE-SCORES.json")
    with open(md_path, "w") as f:
        f.write(md)
    with open(json_path, "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    fingerprint = "|".join(
        f"{r.get('repo')}:{r.get('name')}" for r in sorted(reds, key=lambda x: (x.get("repo", ""), x.get("name", "")))
    ) or "clean"
    today = now.strftime("%Y-%m-%d")
    dedup_key = f"{today}:{fingerprint}"

    prev_dedup = ""
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        prev_dedup = json.loads(line).get("dedup", prev_dedup)
                    except Exception:
                        pass

    # Источник истины дедупа — сама issue (fact = байты): ищем маркер
    # в последних комментариях (сортировка sort= ненадёжен — пагинация + хвост).
    already_posted = False
    if reds:
        recent = []
        url_c = f"https://api.github.com/repos/{OWNER}/github-runbook/issues/10/comments?per_page=100"
        while url_c:
            req_c = urllib.request.Request(url_c, headers={
                "Authorization": f"Bearer {T}",
                "Accept": "application/vnd.github+json",
            })
            try:
                with urllib.request.urlopen(req_c) as r:
                    page = json.loads(r.read() or b"[]")
                    link = r.headers.get("Link") or ""
            except (urllib.error.HTTPError, urllib.error.URLError):
                break
            if not isinstance(page, list):
                break
            recent.extend(page)
            url_c = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    url_c = part[part.find("<") + 1:part.find(">")]
        marker = f"<!-- hive-scorecard {dedup_key}"
        already_posted = any(marker in (c.get("body") or "") for c in recent[-10:])

    commented = False
    want_comment = (reds or args.stamp) and not args.dry_run and not already_posted
    if want_comment:
        digest = [
            f"## 🧬 HIVE-SCORECARD: облёт улья {ts}",
            "",
            f"Репо **{len(rows)}** · средний счёт **{avg}/100** · 🔴 CI: {len(red_repos)} · "
            f"📥 открытых: {total_open}",
            f"Грейды: {hist}",
        ]
        if reds:
            digest += ["", f"**🔴 Красные на HEAD ({len(reds)}):**"]
            for r in reds:
                digest.append(f"- `{r.get('repo')}` / **{r.get('name')}** — "
                              f"[run]({r.get('url')})")
        if worst_first:
            digest += ["", "**Худшие 5 по счёту гигиены:**"]
            for r in worst_first[:5]:
                digest.append(f"- `{r['repo']}` — {r['score']}/100 ({r['grade']})"
                              f" · пробелы: {'·'.join(r['gaps']) or '✅'}")
        digest += [
            "",
            "Счёт целиком: [HIVE-SCORECARD.md](HIVE-SCORECARD.md) · "
            "пульт: [HIVE-DASHBOARD.md](HIVE-DASHBOARD.md)",
            "",
            f"<!-- hive-scorecard {dedup_key} -->",
        ]
        st, resp = api(
            f"https://api.github.com/repos/{OWNER}/github-runbook/issues/10/comments",
            method="POST", payload={"body": "\n".join(digest)},
        )
        commented = st in (200, 201)
        if not commented:
            print(f"⚠️ аларм-POST не прошёл: HTTP {st} {resp.get('message', '')}", file=sys.stderr)

    if not args.dry_run:
        # Дедуп пишется только когда комментарий реально поставлен (или не требовался):
        # неудачный POST не запоминается — следующий прогон ретраит аларм.
        ledger_dedup = dedup_key if (commented or not want_comment) else ""
        with open(ledger_path, "a") as f:
            f.write(json.dumps({
                "ts": ts, "dedup": ledger_dedup, "avg": avg,
                "reds": len(reds), "repos": len(rows),
                "grades": grades_hist,
                "alarm_posted": bool(commented),
            }, ensure_ascii=False) + "\n")

    if not args.quiet:
        print(f"🧬 счёт улья: {len(rows)} репо, средний {avg}/100, грейды {hist}")
        print(f"   🔴 CI: {len(red_repos) or 'нет'} · 📥 issues: {total_open}")
        if worst_first:
            for r in worst_first[:5]:
                print(f"   худший: {r['repo']} {r['score']}/100 ({r['grade']})")
        print(f"   файлы: {md_path}, {json_path} · аларм issue #10: {'да' if commented else 'нет/дедуп'}")


if __name__ == "__main__":
    main()
