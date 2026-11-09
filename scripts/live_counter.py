#!/usr/bin/env python3
"""live_counter.py — ЖИВОЙ СЧЁТЧИК issue #10 (МАСТЕР-ИНДЕКС недоделанного).

Закон «сделано → сразу отняли»: добил issue(и) живым зелёным прогоном —
СРАЗУ запусти этот скрипт. Он пересчитывает факты через API GitHub и
переписывает блок счётчика в теле issue #10 между маркерами
<!-- LIVE-COUNTER:START --> и <!-- LIVE-COUNTER:END -->.
История тела ниже маркеров не трогается. Idempotent: гоняй хоть после каждой пары.

Приём:
    python3 scripts/live_counter.py           # пересчёт + перепись блока
    python3 scripts/live_counter.py --stamp   # + короткий append-only штамп-комментарий

Токен: переменная окружения GH_TOKEN или /tmp/.gt (chmod 600).
Только stdlib. Правила дома: факт = байты; счётчик не ждёт конца волны.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "rtynbirf/github-runbook"
ISSUE = 10
MSK = timezone(timedelta(hours=3))


def token():
    tok = os.environ.get("GH_TOKEN") or ""
    if not tok and os.path.exists("/tmp/.gt"):
        with open("/tmp/.gt") as f:
            tok = f.read().strip()
    if not tok:
        sys.exit("нет токена: GH_TOKEN или /tmp/.gt")
    return tok


def api(url, tok, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    return json.load(urllib.request.urlopen(req))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", action="store_true", help="плюс штамп-комментарий")
    args = ap.parse_args()
    tok = token()

    # 1) Глобальные факты (search API считает и приватные репо)
    q_open = api(
        "https://api.github.com/search/issues?q=user:rtynbirf+is:issue+is:open&per_page=1", tok
    )["total_count"]
    q_closed = api(
        "https://api.github.com/search/issues?q=user:rtynbirf+is:issue+is:closed&per_page=1",
        tok,
    )["total_count"]
    q_pr = api(
        "https://api.github.com/search/issues?q=user:rtynbirf+is:pr+is:open&per_page=1", tok
    )["total_count"]

    # 2) Разрез по репо (issues API не возвращает PR)
    repos = []
    page = 1
    while True:
        chunk = api(
            f"https://api.github.com/user/repos?per_page=100&visibility=all&page={page}", tok
        )
        if not chunk:
            break
        repos.extend(chunk)
        page += 1

    per = {}
    for r in repos:
        n = 0
        pg = 1
        while True:
            chunk = api(
                f"https://api.github.com/repos/rtynbirf/{r['name']}/issues"
                f"?state=open&per_page=100&page={pg}",
                tok,
            )
            if not chunk:
                break
            n += len(chunk)
            pg += 1
        if n:
            per[r["name"]] = n

    if sum(per.values()) != q_open:
        print(
            f"ПРЕДУПРЕЖДЕНИЕ: разрез {sum(per.values())} != search {q_open} — гоняю скрипт ещё раз"
        )

    # 3) Сборка блока счётчика
    now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M МСК")
    total = q_open + q_closed
    pct = round(100 * q_closed / total, 1) if total else 0.0
    cut = " · ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda x: -x[1]))
    zero_repos = len(repos) - len(per)
    block = f"""<!-- LIVE-COUNTER:START -->
## 🔢 ЖИВОЙ СЧЁТЧИК · факт = байты · пересчёт: `scripts/live_counter.py`

**Последний пересчёт: {now}**

| Метрика | Число |
|---|---|
| Issues за всю историю дома | **{total}** |
| ✅ Сделано (закрыто) | **{q_closed}** ({pct}%) |
| ⬜ Не сделано (открыто) | **{q_open}** |
| Открытых PR | {q_pr} |

**Закон счётчика: сделанное сразу отнимается от несделанного.** Закрыл issue живым зелёным прогоном → сразу `python3 scripts/live_counter.py` — цифры выше переписаны. Не ждать конца волны.

**Разрез открытых ({q_open}):** {cut}{f' · остальные {zero_repos} репо — 0' if zero_repos else ''}

**Протокол:**
1. Issue закрывается ТОЛЬКО живым зелёным прогоном (закон дома), затем — пересчёт этого блока.
2. Штамп-комментарий волны — append-only, счётчик от него не зависит и не ждёт.
3. Скрипт меняет только блок между маркерами LIVE-COUNTER — история ниже неприкосновенна.
<!-- LIVE-COUNTER:END -->"""

    # 4) Перепись тела
    issue = api(f"https://api.github.com/repos/{REPO}/issues/{ISSUE}", tok)
    body = issue["body"] or ""
    if "<!-- LIVE-COUNTER:START -->" in body:
        pre = body.split("<!-- LIVE-COUNTER:START -->", 1)[0]
        post = body.split("<!-- LIVE-COUNTER:END -->", 1)[1]
        new_body = pre + block + post
    else:
        # Первичная вставка: после H1 + честное клеймо устаревшего снимка ×3
        lines = body.splitlines()
        out, inserted = [], False
        for ln in lines:
            out.append(ln)
            if not inserted and ln.startswith("# "):
                out.append("")
                out.append(block)
                inserted = True
        new_body = "\n".join(out) + ("\n" if body.endswith("\n") else "")
        new_body = new_body.replace(
            "## Живой снимок 08.11.2026 21:26 МСК",
            "## 🗄 Исторический снимок ×3 (08.11.2026 21:26 МСК) — счёт заморожён, живой счётчик выше",
        ).replace("## 0) Живой снимок 09.11", "## 🗄 Исторический снимок ×3–×4 (09.11) — счёт заморожён, живой счётчик выше")

    api(f"https://api.github.com/repos/{REPO}/issues/{ISSUE}", tok, method="PATCH", payload={"body": new_body})

    print(f"СЧЁТЧИК ПЕРЕПИСАН {now}")
    print(f"  всего {total} | закрыто {q_closed} ({pct}%) | открыто {q_open} | PR {q_pr}")
    print(f"  разрез: {cut}" + (f" | прочие {zero_repos} репо: 0" if zero_repos else ""))

    if args.stamp:
        stamp = (
            "🔢 **СЧЁТЧИК ПЕРЕСЧИТАН** (scripts/live_counter.py, факт = байты, живой API)\n\n"
            f"открыто **{q_open}** · закрыто **{q_closed}** ({pct}%) · всего {total} · PR {q_pr}\n\n"
            "Закон «сделано → сразу отняли» действует: добил issue — сразу пересчёт, не ждём конца волны."
        )
        api(f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments", tok, method="POST", payload={"body": stamp})
        print("штамп-комментарий оставлен")


if __name__ == "__main__":
    main()
