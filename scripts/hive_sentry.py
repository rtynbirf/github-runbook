#!/usr/bin/env python3
"""hive_sentry.py — HIVE-SENTRY: детерминированный страж-фантомолов роя.

Мировой тренд 2026 — self-healing CI (Semaphore, devopsboys); мир лечит вслепую
(retry:3 маскирует регрессии) или AI-классификаторами (дорого, недетерминировано).
Плюс документированная дыра GitHub: startup_failure прогоны нельзя ре-рануть
через API (community/207957) — их лечит ТОЛЬКО dispatch.

SENTRY делает по-домскому (факт = байты, без ИИ):
  КЛАССИФИКАЦИЯ красного прогона на HEAD:
    PHANTOM-STARTUP  — conclusion=failure, jobs=0            → лечится dispatch
    PHANTOM-VERDICT  — conclusion=failure, все jobs success/skipped → лечится dispatch
    REAL-RED         — есть хотя бы один job=failure        → НЕ трогаем (не маскируем регрессии)
    MANUAL           — workflow без workflow_dispatch (напр. native pages) → только запись
  ЛЕЧЕНИЕ: dispatch workflow на ту же голову, ≤1 курс на workflow за 24 ч
    (по журналу), ≤ MAX_CURES за прогон — никаких бесконечных петель.
  ВЕРИФИКАЦИЯ: записи журнала младше 48 ч проверяются — dispatch дал зелёный
    на той же голове → CURED; остался красным → RE-PHANTOM (к руке волны).

Выходы: SENTRY-REPORT.md, hive_sentry_ledger.jsonl (append-only).

    GH_TOKEN=... python3 scripts/hive_sentry.py [--state HIVE-STATE.json] [--out .]
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = "rtynbirf"
MSK = timezone(timedelta(hours=3))
MAX_CURES = 10
CURE_COOLDOWN_H = 24
VERIFY_WINDOW_H = 48


def tok():
    t = os.environ.get("GH_TOKEN") or ""
    if not t and os.path.exists("/tmp/.gt"):
        with open("/tmp/.gt") as f:
            t = f.read().strip()
    if not t:
        sys.exit("нет токена: GH_TOKEN или /tmp/.gt")
    return t


def api(url, t, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {t}", "Accept": "application/vnd.github.v3+json"},
        method=method,
    )
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code, "message": e.read().decode(errors="replace")[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="HIVE-STATE.json")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    t = tok()
    now = datetime.now(MSK)

    if not os.path.exists(args.state):
        sys.exit(f"нет {args.state} — сначала гоняй hive-control (пульт публикует снимок)")

    state = json.load(open(args.state))
    reds = state.get("reds", [])
    if reds:
        print(f"красных в снимке: {len(reds)}")
    else:
        print("красных нет — сенрюлю нечего ловить (честный ноль)")
        return

    ledger_path = os.path.join(args.out, "hive_sentry_ledger.jsonl")
    ledger = []
    if os.path.exists(ledger_path):
        with open(ledger_path) as f:
            ledger = [json.loads(ln) for ln in f if ln.strip()]

    report, events, cures = [], [], 0
    report.append("# 🫁 HIVE-SENTRY · страж-фантомолов роя")
    report.append(f"\n**Смена: {now.strftime('%d.%m.%Y %H:%M МСК')} · факт = байты**\n")

    # 1) Верификация вчерашних курсов
    report.append("## Проверка курсов прошлого цикла")
    pending_verify = [
        e for e in ledger
        if e.get("action") == "cure-dispatched"
        and datetime.fromisoformat(e["ts"]) >= now - timedelta(hours=VERIFY_WINDOW_H)
        and not e.get("verified")
    ]
    if not pending_verify:
        report.append("\n— курсов на проверку нет.\n")
    for e in pending_verify:
        runs = api(
            f"https://api.github.com/repos/{OWNER}/{e['repo']}/actions/runs"
            f"?head_sha={e['head_sha']}&event=workflow_dispatch&per_page=10", t)
        verdict = "?"
        for r in runs.get("workflow_runs", []):
            if r["name"] == e["workflow"]:
                verdict = r["conclusion"] or r["status"]
                break
        e["verified"] = verdict
        e["verified_ts"] = now.isoformat()
        if verdict == "success":
            e["result"] = "CURED"
            report.append(f"- ✅ CURED `{e['repo']}` · {e['workflow']} на {e['head_sha']} (прогон стал 🟢)")
        elif verdict in ("failure", "startup_failure"):
            e["result"] = "RE-PHANTOM"
            report.append(f"- 🔁 RE-PHANTOM `{e['repo']}` · {e['workflow']} на {e['head_sha']} — к руке волны")
        else:
            e["result"] = f"PENDING ({verdict})"
            report.append(f"- ⏳ {e['result']} `{e['repo']}` · {e['workflow']} на {e['head_sha']}")
        events.append({**e, "action": "cure-verified"})

    # 2) Свежий обход красных пульта
    report.append("## Обход красных (снимок пульта)")
    for red in reds:
        repo, wf_name = red["repo"], red["name"]
        row0 = next((row for row in state.get("rows", []) if row["repo"] == repo), {})
        sha_full = row0.get("head_sha_full")
        if not sha_full:
            # снимки старого формата без полного sha — берём голову живьём (грабля: API runs?head_sha не принимает короткий SHA — даёт тихий пустой список)
            br = row0.get("default_branch", "main")
            head = api(f"https://api.github.com/repos/{OWNER}/{repo}/commits/{br}", t)
            sha_full = head.get("sha") if isinstance(head, dict) else None
        if not sha_full:
            continue
        # свежий факт: последний прогон этого workflow на этой голове
        runs = api(
            f"https://api.github.com/repos/{OWNER}/{repo}/actions/runs"
            f"?head_sha={sha_full}&per_page=30", t)
        run = next((r for r in runs.get("workflow_runs", []) if r["name"] == wf_name), None)
        if not run or run["conclusion"] != "failure":
            continue  # уже зажив (брат успел) — не трогаем
        jobs = api(f"https://api.github.com/repos/{OWNER}/{repo}/actions/runs/{run['id']}/jobs?per_page=100", t)
        jlist = jobs.get("jobs", []) if isinstance(jobs, dict) else []
        fails = [j for j in jlist if j.get("conclusion") == "failure"]
        if fails:
            cls = "REAL-RED"
            report.append(f"- 🔴 REAL-RED `{repo}` · {wf_name} #{run['run_number']} — job(ы): {', '.join(j['name'] for j in fails[:3])}. Регрессия не маскируется — работа для волны.")
            events.append({"ts": now.isoformat(), "action": "classified", "repo": repo,
                           "workflow": wf_name, "cls": cls, "run_id": run["id"]})
            continue
        cls = "PHANTOM-STARTUP" if not jlist else "PHANTOM-VERDICT"

        # курс уже был недавно?
        recent = [e for e in ledger if e.get("action") == "cure-dispatched"
                  and e.get("repo") == repo and e.get("workflow") == wf_name
                  and datetime.fromisoformat(e["ts"]) >= now - timedelta(hours=CURE_COOLDOWN_H)]
        if recent:
            report.append(f"- ⏳ {cls} `{repo}` · {wf_name} — курс уже выдан {recent[0]['ts'][11:16]}, верификация завтра (не дублируем).")
            continue

        # dispatch доступен? (честные байты: файл workflow содержит workflow_dispatch)
        row0 = next((row for row in state.get("rows", []) if row["repo"] == repo), {})
        wf_path = run.get("path", "")
        src = api(f"https://api.github.com/repos/{OWNER}/{repo}/contents/{wf_path}?ref={row0.get('default_branch','main')}", t)
        src_text = ""
        if isinstance(src, dict) and src.get("content"):
            try:
                src_text = base64.b64decode(src["content"]).decode(errors="replace")
            except Exception:
                src_text = ""
        dispatchable = "workflow_dispatch" in src_text
        if not dispatchable:
            report.append(f"- 🖐 {cls} `{repo}` · {wf_name} — без workflow_dispatch (MANUAL). Лечение руками: ре-ран или фикс триггера.")
            events.append({"ts": now.isoformat(), "action": "classified", "repo": repo,
                           "workflow": wf_name, "cls": "MANUAL", "run_id": run["id"]})
            continue

        if cures >= MAX_CURES:
            report.append(f"- ⚠️ лимит курсов за смену ({MAX_CURES}) исчерпан — `{repo}` · {wf_name} ждёт следующей смены.")
            continue

        ref = None
        for row in state.get("rows", []):
            if row["repo"] == repo:
                ref = row.get("default_branch", "main")
        code = api(f"https://api.github.com/repos/{OWNER}/{repo}/actions/workflows/{wf_path}/dispatches",
                   t, method="POST", payload={"ref": ref or "main"})
        ok = not isinstance(code, dict) or "__http_error__" not in code
        cures += 1
        if ok:
            report.append(f"- 💉 {cls} `{repo}` · {wf_name} #{run['run_number']} — курс выдан (dispatch на {ref}), верификация завтра.")
            events.append({"ts": now.isoformat(), "action": "cure-dispatched", "repo": repo,
                           "workflow": wf_name, "cls": cls, "head_sha": sha_full, "ref": ref})
        else:
            report.append(f"- ❌ {cls} `{repo}` · {wf_name} — dispatch не прошёл (HTTP {code.get('__http_error__')}): {code.get('message','')[:120]}")
            events.append({"ts": now.isoformat(), "action": "cure-failed", "repo": repo,
                           "workflow": wf_name, "cls": cls, "http": code.get("__http_error__")})

    report.append(f"\n**Итог смены: курсов выдано {cures}/{MAX_CURES}, классификаций {len([e for e in events if e['action']=='classified'])}.**")
    report.append("\nДоктрина: регрессии (REAL-RED) не маскируются — только фантомы лечатся, и по одному курсу за 24 ч на workflow.")

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "SENTRY-REPORT.md"), "w") as f:
        f.write("\n".join(report) + "\n")
    with open(ledger_path, "a") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"HIVE-SENTRY: курсов {cures}, событий {len(events)}")
    for ln in report:
        if ln.startswith(("- 💉", "- 🔴", "- ✅", "- 🔁")):
            print("  " + ln[:110])


if __name__ == "__main__":
    main()
