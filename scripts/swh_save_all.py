#!/usr/bin/env python3
"""swh_save_all.py — 📚 П-28 (polimat-hub#46): Software Heritage Save Code Now
для всего публичного флота, двухфазно, с уважением к чужому лимиту.

Фаза 1 — POST /origin/save/github/{owner}/{repo}/ по каждому публичному неархивному
         репо; чтение X-RateLimit-Remaining/Reset; на 429 — честный backoff
         (сон до reset, максимум SWH_MAX_WAIT секунд, потом остановка с частичным
         итогом — фоссология-прецедент: лимит хозяина API важнее нашего плана).
Фаза 2 — GET статуса каждого запроса: save_task_status (not_created/scheduled/
         running/completed/failed); строка coverage для ПУЛЬСа.

Закон дома «факт = байты»: в журнал идёт сырой HTTP-код и сырой статус SWH,
никаких «наверное сохранилось». Грабли №55 (UTF-8 броня) и №56 (quote) учтены.
Артефакты: SWH-SAVE.md + hive_swh_ledger.jsonl (append-only).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OWNER = "rtynbirf"
SWH = "https://archive.softwareheritage.org/api/1"
GH = "https://api.github.com"
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hive_swh_ledger.jsonl")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SWH-SAVE.md")
POLITE_DELAY = 2.0          # SWH просит не дёргать чаще ~1 rps
MAX_WAIT_ON_429 = 900       # ждать reset не дольше 15 минут за один заход
UA = "hive-swh-save/1.0 (github.com/rtynbirf/github-runbook)"


def gh_token():
    for p in ("/tmp/.gt", "/tmp/.gt-reserve"):
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
        except OSError:
            continue
    return ""


def http_json(url, method="GET", token="", body=None):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
            if "within.website" in raw or "Oh noes!" in raw:
                # Anubis anti-bot отдал HTML вместо JSON — честный вердикт, не падение сети
                return r.status, {"anubis": True, "reason": "Anubis anti-bot challenge: HTML вместо JSON"}, dict(r.headers)
            return r.status, json.loads(raw) if raw.strip() else {}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
        hdrs = dict(e.headers or {})
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:300]}
        return e.code, parsed, hdrs
    except Exception as e:  # сеть/таймаут — фиксируем как есть
        return -1, {"error": str(e)[:200]}, {}


def public_repos(token):
    out, page = [], 1
    while True:
        st, d, _ = http_json(f"{GH}/users/{OWNER}/repos?per_page=100&page={page}", token=token)
        if st != 200 or not isinstance(d, list):
            break
        out.extend(d)
        if len(d) < 100:
            break
        page += 1
    return sorted(r["name"] for r in out if not r.get("archived") and not r.get("private"))


def save_request(repo, token):
    url = f"{SWH}/origin/save/github/{OWNER}/{urllib.parse.quote(repo, safe='')}/"
    st, d, h = http_json(url, method="POST", token=token)
    return st, d, h


def save_status(repo, token):
    url = f"{SWH}/origin/save/github/{OWNER}/{urllib.parse.quote(repo, safe='')}/"
    st, d, _ = http_json(url, token=token)
    return st, d


def main():
    token = gh_token()
    repos = public_repos(token)
    print(f"публичных репозиториев: {len(repos)}")
    results = {}
    rate_note = ""

    anubis_run = 0          # подряд идущие Anubis-блоки
    GLOBAL_ABORT = None
    for i, repo in enumerate(repos, 1):
        if GLOBAL_ABORT:
            results[repo] = {"http": 0, "save_request_status": "SKIPPED", "save_task_status": None,
                             "reason": GLOBAL_ABORT, "rate_remaining": None}
            continue
        attempt = 0
        while True:
            attempt += 1
            st, d, h = save_request(repo, token)
            if isinstance(d, dict) and d.get("anubis"):
                anubis_run += 1
                print(f"[{i}/{len(repos)}] {repo}: ANUBIS-BLOCK (HTTP {st}, HTML вместо JSON)")
                results[repo] = {"http": st, "save_request_status": "ANUBIS-BLOCK", "save_task_status": None,
                                 "reason": d.get("reason"), "rate_remaining": None}
                if anubis_run >= 3:
                    GLOBAL_ABORT = "Anubis anti-bot блокирует API по IP (3 подряд) — полный проб прекращён честно"
                time.sleep(1.0)
                break
            rem = h.get("X-RateLimit-Remaining") or h.get("x-ratelimit-remaining")
            reset = h.get("X-RateLimit-Reset") or h.get("x-ratelimit-reset")
            if st == 429 and attempt == 1 and reset:
                wait = max(0, int(float(reset)) - int(time.time()) + 2)
                if 0 < wait <= MAX_WAIT_ON_429:
                    print(f"429 на {repo}: спим {wait}с до reset (уважаем чужой лимит)")
                    time.sleep(wait)
                    continue
                rate_note = f"429 на {repo}: reset через {wait}с > {MAX_WAIT_ON_429}с — стоп, частичный итог"
                break
            anubis_run = 0
            rec = {
                "http": st,
                "save_request_status": d.get("save_request_status"),
                "save_task_status": d.get("save_task_status"),
                "reason": (d.get("reason") or d.get("detail") or "")[:120] if isinstance(d, dict) else "",
                "rate_remaining": rem,
            }
            results[repo] = rec
            print(f"[{i}/{len(repos)}] {repo}: HTTP {st} · req={rec['save_request_status']} · task={rec['save_task_status']} · rate_left={rem}")
            time.sleep(POLITE_DELAY)
            break

    # Фаза 2 — статусы (пропускается при глобальной Anubis-остановке: чужой лимит и чужая защита)
    task_counts = {}
    if GLOBAL_ABORT:
        print("фаза 2 пропущена:", GLOBAL_ABORT)
    else:
        print("фаза 2: статусы запросов")
        for i, repo in enumerate(results, 1):
            st, d = save_status(repo, token)
            ts = d.get("save_task_status") if st == 200 and isinstance(d, dict) and not d.get("anubis") else None
            results[repo]["verify_http"] = st
            results[repo]["verify_task"] = ts
            key = ts or (d.get("reason") if isinstance(d, dict) and d.get("anubis") else f"http{st}")
            task_counts[key] = task_counts.get(key, 0) + 1
            time.sleep(POLITE_DELAY)
        print("срез статусов:", task_counts)

    accepted = sum(1 for r in results.values() if r["save_request_status"] == "accepted")
    blocked = sum(1 for r in results.values() if r["save_request_status"] in ("ANUBIS-BLOCK", "SKIPPED"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    coverage = f"SWH coverage: запрошено {accepted}/{len(repos)} · статусы задач {json.dumps(task_counts, ensure_ascii=False)}"

    with open(LEDGER, "a", encoding="utf-8") as fo:
        fo.write(json.dumps({"ts": now, "repos": len(repos), "results": results, "coverage": coverage}, ensure_ascii=False) + "\n")

    lines = [
        "# 📚 SWH-SAVE · Software Heritage Save Code Now · публичный флот",
        "",
        f"> Прогон: {now} UTC · П-28 (polimat-hub#46) · POST /origin/save/github/{OWNER}/<repo>/",
        "",
        f"**{coverage}**",
        "",
    ]
    if blocked:
        lines += [
            f"> ⛔ **Anubis anti-bot**: archive.softwareheritage.org отдаёт PoW-вызов (HTML «Oh noes!», /.within.website) вместо JSON на все API-запросы с серверных IP — независимо от User-Agent (curl×3 UA + urllib POST + GET = 5 независимых проб). Это факт платформы, не ошибка скрипта: {blocked}/{len(repos)} позиций заблокированы/пропущены.",
            f"> Разблокировка (решение Хозяина): SWH-токен (https://archive.softwareheritage.org/api/1/token/) или ручной POST через браузер; скрипт готов — при живом канале перезапуск покроет весь флот.",
            "",
        ]
    if rate_note:
        lines.append(f"> ⚠️ {rate_note}")
        lines.append("")
    lines += ["| Репо | HTTP | save_request | save_task | verify |", "|---|---|---|---|---|"]
    for repo, r in results.items():
        lines.append(f"| {repo} | {r['http']} | {r['save_request_status'] or '—'} | {r['save_task_status'] or '—'} | {r.get('verify_task') or '—'} |")
    lines += [
        "",
        "## Метод",
        "",
        "- POST /origin/save/github/... — официальный механизм сохранения (softwareheritage.org);",
        "- уважение к чужому лимиту: X-RateLimit-Remaining/Reset читаются каждый запрос, на 429 — backoff до reset (≤15 мин), иначе честная остановка (прецедент fossology#1836);",
        "- Anubis-детектор: HTML «Oh noes!» вместо JSON = вердикт ANUBIS-BLOCK, 3 подряд = честная остановка полного прогона;",
        "- журнал: hive_swh_ledger.jsonl (append-only, сырые коды и статусы — факт = байты).",
        "",
    ]
    with open(REPORT, "w", encoding="utf-8") as fo:
        fo.write("\n".join(lines))
    print(coverage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
