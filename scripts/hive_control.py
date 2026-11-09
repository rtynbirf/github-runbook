#!/usr/bin/env python3
"""hive_control.py — ЖИВОЙ ПУЛЬТ РОЯ (42 репо) · HIVE-CONTROL.

Единый снимок здоровья всего дома одним прогоном:
  • на каждый репо: HEAD, вердикты всех workflow на HEAD (fact=bytes),
    открытые issues/PR, dependabot.yml, артефакты (МБ)
  • вердикт репо: 🟢 GREEN / 🔴 RED / ⚪ EMPTY / 🗄 ARCHIVED
  • выходы: HIVE-DASHBOARD.md (таблица+сводка), HIVE-STATE.json (машина),
    hive_ledger.jsonl (append-only история снимков), HIVE-BADGE.svg (бейдж README)

Мировая практика 2026 (reusable workflows, SHA-pin, least-privilege) уже в доме;
этого инструмента у мира НЕТ: ни GitHub native, ни gitfitcheck (только публичные
данные, без приватных репо и CI-on-HEAD), ни Grafana-экспортеры не дают
приватный 42-репо пульт с автофантом-проверкой. Только stdlib.

    GH_TOKEN=... python3 scripts/hive_control.py [--out DIR] [--quiet]

После волны: результат коммитит workflow hive-control.yml (сообщение с [skip ci]).
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = "rtynbirf"
MSK = timezone(timedelta(hours=3))


def tok():
    t = os.environ.get("GH_TOKEN") or ""
    if not t and os.path.exists("/tmp/.gt"):
        with open("/tmp/.gt") as f:
            t = f.read().strip()
    if not t:
        sys.exit("нет токена: GH_TOKEN или /tmp/.gt")
    return t


def api(url, t, method="GET"):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {t}", "Accept": "application/vnd.github.v3+json"},
        method=method,
    )
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    t = tok()

    repos = []
    page = 1
    while True:
        try:
            chunk = api(f"https://api.github.com/user/repos?per_page=100&visibility=all&page={page}", t)
        except urllib.error.HTTPError as e:
            sys.exit(
                f"GET /user/repos → HTTP {e.code}: токен без user-контекста "
                f"(GITHUB_TOKEN раннера — токен-установка, ему весь дом не виден). "
                f"Нужен PAT: положи его секретом HIVE_TOKEN в репо и берись "
                f"env GH_TOKEN: ${{{{ secrets.HIVE_TOKEN }}}}."
            )
        if not chunk:
            break
        repos.extend(chunk)
        page += 1

    rows, reds, open_issues, artifacts_mb = [], [], 0, 0.0
    for r in sorted(repos, key=lambda x: x["name"]):
        name = r["name"]
        row = {"repo": name, "archived": bool(r["archived"]), "default_branch": r["default_branch"]}
        if r["archived"]:
            row.update(grade="🗄 ARCHIVED", workflows=[], open_issues=0, open_prs=0)
            rows.append(row)
            continue

        sha = api(f"https://api.github.com/repos/{OWNER}/{name}/commits/{r['default_branch']}", t)
        sha = sha["sha"] if sha else ""
        runs = api(
            f"https://api.github.com/repos/{OWNER}/{name}/actions/runs?head_sha={sha}&per_page=100",
            t,
        ) or {"workflow_runs": []}
        latest = {}
        for w in runs.get("workflow_runs", []):
            n = w["name"]
            if n not in latest or w["created_at"] > latest[n]["created_at"]:
                latest[n] = w
        wfs = [
            {
                "name": n,
                "conclusion": w["conclusion"],
                "run_number": w["run_number"],
                "url": w["html_url"],
            }
            for n, w in sorted(latest.items())
        ]
        red_wfs = [w for w in wfs if w["conclusion"] == "failure"]
        reds.extend([{"repo": name, **w} for w in red_wfs])

        issues = api(
            f"https://api.github.com/repos/{OWNER}/{name}/issues?state=open&per_page=100", t
        ) or []
        pulls = api(
            f"https://api.github.com/repos/{OWNER}/{name}/pulls?state=open&per_page=100", t
        ) or []
        dep = api(f"https://api.github.com/repos/{OWNER}/{name}/contents/.github/dependabot.yml", t)
        arts = api(
            f"https://api.github.com/repos/{OWNER}/{name}/actions/artifacts?per_page=100", t
        ) or {"artifacts": []}
        amb = sum(a["size_in_bytes"] for a in arts.get("artifacts", [])) / 1024 / 1024
        artifacts_mb += amb

        open_issues += len(issues)
        if not wfs:
            grade = "⚪ EMPTY (нет workflow)"
        elif red_wfs:
            grade = f"🔴 RED ×{len(red_wfs)}"
        else:
            grade = "🟢 GREEN"
        row.update(
            grade=grade,
            head_sha=sha[:7],
            head_sha_full=sha,
            workflows=wfs,
            open_issues=len(issues),
            open_prs=len(pulls),
            dependabot=bool(dep),
            artifacts_mb=round(amb, 2),
        )
        rows.append(row)

    now = datetime.now(MSK)
    ts = now.strftime("%d.%m.%Y %H:%M МСК")
    g = sum(1 for x in rows if x["grade"].startswith("🟢"))
    rd = sum(1 for x in rows if x["grade"].startswith("🔴"))
    em = sum(1 for x in rows if x["grade"].startswith("⚪"))
    ar = sum(1 for x in rows if x["grade"].startswith("🗄"))

    os.makedirs(args.out, exist_ok=True)
    state = {
        "timestamp": ts,
        "repos_total": len(rows),
        "green": g,
        "red": rd,
        "empty": em,
        "archived": ar,
        "open_issues": open_issues,
        "reds": reds,
        "artifacts_mb": round(artifacts_mb, 2),
        "rows": rows,
    }
    with open(os.path.join(args.out, "HIVE-STATE.json"), "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)

    lines = [
        "# 🐝 HIVE-CONTROL · живой пульт роя",
        "",
        f"**Снимок: {ts} · факт = байты (API)**",
        "",
        f"**{len(rows)} репо** · 🟢 {g} · 🔴 {rd} · ⚪ {em} · 🗄 {ar} · открытых issues **{open_issues}** · артефактов {artifacts_mb:.1f} МБ",
        "",
        "| Репо | Вердикт | Workflow на HEAD | Issues | PR | dependabot | Артефакты |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in rows:
        wfs = (
            "<br>".join(
                f"{'🔴' if w['conclusion']=='failure' else '🟡' if w['conclusion']=='skipped' else '🟢' if w['conclusion']=='success' else '⚪'} {w['name']}"
                for w in x["workflows"][:6]
            )
            or "—"
        )
        more = f" (+{len(x['workflows'])-6})" if len(x["workflows"]) > 6 else ""
        lines.append(
            f"| `{x['repo']}` | {x['grade']} | {wfs}{more} | {x.get('open_issues',0)} | {x.get('open_prs',0)} | "
            f"{'✅' if x.get('dependabot') else '—'} | {x.get('artifacts_mb',0)} МБ |"
        )
    if reds:
        lines += ["", "## 🔴 Живые красные (ссылки для дожима)", ""]
        for w in reds:
            lines.append(f"- `{w['repo']}` · {w['name']} #{w['run_number']} → {w['url']}")
    else:
        lines += ["", "## ✅ Живых красных нет — честный ноль.", ""]
    with open(os.path.join(args.out, "HIVE-DASHBOARD.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    with open(os.path.join(args.out, "hive_ledger.jsonl"), "a") as f:
        f.write(
            json.dumps(
                {
                    "ts": now.isoformat(),
                    "repos": len(rows),
                    "green": g,
                    "red": rd,
                    "empty": em,
                    "open_issues": open_issues,
                    "reds": [f"{w['repo']}:{w['name']}" for w in reds],
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="330" height="20" role="img" aria-label="HIVE">
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".3"/></linearGradient>
  <clipPath id="r"><rect width="330" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="90" height="20" fill="#555"/><rect x="90" width="240" height="20" fill="{'#4c1' if rd==0 else '#dfb317' if rd<6 else '#e05d44'}"/>
    <rect width="330" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="45" y="14">HIVE</text>
    <text x="210" y="14">{len(rows)} репо · 🟢 {g} · 🔴 {rd} · ⬜ {open_issues}</text>
  </g>
</svg>
'''
    with open(os.path.join(args.out, "HIVE-BADGE.svg"), "w") as f:
        f.write(svg)

    if not args.quiet:
        print(f"HIVE-CONTROL {ts}")
        print(f"  репо {len(rows)} | 🟢 {g} | 🔴 {rd} | ⚪ {em} | 🗄 {ar} | issues {open_issues} | артефакты {artifacts_mb:.1f} МБ")
        if reds:
            print("  красные:")
            for w in reds:
                print(f"    - {w['repo']} · {w['name']} #{w['run_number']}")


if __name__ == "__main__":
    main()
