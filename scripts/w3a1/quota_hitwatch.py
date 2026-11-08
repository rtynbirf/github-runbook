#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Квота-дозор: ловец внезапных «quota has been hit» (Волна ×3, W3-A1, issue #4).

Дополнение к пульсу волны A (wave3-quota-pulse.yml + scripts/wave3/quota_pulse.py):
пульс смотрит ВПЕРЁД (биллимые байты против 500 МБ), дозор — НАЗАД за 30 дней:
по логам красных прогонов ищет следы убийства квоты и печатает строку
«КВОТА-УДАРЫ: N/30д». Ноль находок — живое свидетельство критерия 2
(«ноль внезапных quota hit за 30 дней»). Обнаружил удар — сам поднимает
немедленную гигиену: удаляет ТОЛЬКО свои расходники текущего репо старше
ARTIFACT_TTL_HOURS, не дожидаясь утреннего пульса. media-vault — СВЯТОЕ
владельца: его логи не читаем и ничего в нём не удаляем.

Только stdlib 3.11. Сеть трогается при прогоне в Actions; локально без токена —
честный стоп без ошибки. Состояния нет: чистая функция от API (ход для роя),
записи только дополняются (step summary открывается в режиме append).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
DAYS_BACK = 30                    # окно критерия 2: «ноль внезапных quota hit за 30 дней»
ARTIFACT_TTL_HOURS = 24           # глубина немедленной гигиены при обнаружении удара
MAX_LOG_BYTES = 1 << 20           # потолок чтения одного лога — не глотаем гигабайты
MAX_RUNS_PER_REPO = 50            # потолок красных прогонов на репо за один проход
PROTECTED_REPOS = {"media-vault"}  # СВЯТОЕ: ни чтения логов, ни удаления, без исключений
# Реальные следы смерти квоты (кейс из §Мировые практики предложения):
QUOTA_MARKS = ("quota has been hit", "storage quota")

def api(method, path, token, raw=False):
    req = urllib.request.Request(
        API + path, method=method,
        headers={"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(MAX_LOG_BYTES if raw else None)
            return resp.status, (body.decode("utf-8", "replace") if raw else json.loads(body or b"{}"))
    except urllib.error.HTTPError as err:
        return err.code, ("" if raw else {})

def paged(token, path, cap=None):
    out, page = [], 1
    while True:
        st, data = api("GET", path + ("&" if "?" in path else "?") + "per_page=100&page=%d" % page, token)
        if st != 200 or not isinstance(data, list):
            return out, st
        out.extend(data)
        if len(data) < 100 or (cap and len(out) >= cap):
            return (out[:cap] if cap else out), st
        page += 1

def hits_last_days(token, owner, repo, since):
    """Чистая функция: API → (число красных прогонов со следами квоты, статус).
    Считаются ПРОГОНЫ (не джобы): один прогон — максимум один удар."""
    q = "/repos/%s/%s/actions/runs?status=failure&created:>=%s" % (owner, repo, since)
    runs, st = paged(token, q, cap=MAX_RUNS_PER_REPO)
    if st != 200:
        return None, st
    found = 0
    for run in runs:
        st2, jobs = api("GET", "/repos/%s/%s/actions/runs/%s/jobs?per_page=100" % (owner, repo, run["id"]), token)
        if st2 != 200 or not isinstance(jobs, dict):
            continue
        struck = False
        for job in jobs.get("jobs", []):
            if struck or job.get("conclusion") != "failure":
                continue
            st3, log = api("GET", "/repos/%s/%s/actions/jobs/%s/logs" % (owner, repo, job["id"]), token, raw=True)
            if st3 == 200 and any(mark in log.lower() for mark in QUOTA_MARKS):
                struck = True
                print("УДАР: %s · %s · run %s · job %s" % (repo, run.get("name"), run.get("id"), job.get("name")))
        found += 1 if struck else 0
    return found, 200

def hygiene_now(token, owner, repo, now):
    """Немедленная гигиена: ТОЛЬКО свои расходники старше TTL; СВЯТОЕ — мимо."""
    if repo in PROTECTED_REPOS:
        print("ГИГИЕНА: %s — СВЯТОЕ, удаление запрещено, выходим." % repo)
        return 0
    cutoff = now.timestamp() - ARTIFACT_TTL_HOURS * 3600
    deleted = 0
    arts, _ = paged(token, "/repos/%s/%s/actions/artifacts" % (owner, repo))
    for art in arts:
        created = datetime.fromisoformat(art["created_at"].replace("Z", "+00:00"))
        if created.timestamp() >= cutoff:
            continue
        st, _ = api("DELETE", "/repos/%s/%s/actions/artifacts/%d" % (owner, repo, art["id"]), token)
        if st == 204:
            deleted += 1
            print("ГИГИЕНА: удалён свой расходник id=%s (старше %dч)" % (art["id"], ARTIFACT_TTL_HOURS))
        else:
            print("ГИГИЕНА: id=%s не удалён (HTTP %s) — дописано в отчёт, идём дальше" % (art["id"], st))
    return deleted

def emit(line, extra=()):
    """Append-only вывод: step summary только дополняется, перезаписи нет."""
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            for x in extra:
                fh.write(x + "\n")

def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    pat = os.environ.get("PAT_TOKEN") or ""
    if not token and not pat:
        print("КВОТА-УДАРЫ: локальный режим без токена — живых цифр нет,")
        print("КВОТА-УДАРЫ: (заполняется скриптом при прогоне в Actions).")
        return 0
    if pat:
        token = pat
        st, me = api("GET", "/user", token)
        owner = me.get("login", "") if st == 200 and isinstance(me, dict) else ""
        repos, _ = paged(token, "/user/repos?affiliation=owner&visibility=all")
        repos = [r["name"] for r in repos]
    elif os.environ.get("GITHUB_REPOSITORY"):
        owner, repo = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        repos = [repo]
        print("ОБЗОР: только своё репо — PAT_TOKEN не выдан, аккаунтный обзор сузился (честно).")
    else:
        print("КВОТА-УДАРЫ: не заданы ни PAT_TOKEN, ни GITHUB_REPOSITORY — дозорить нечего.")
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    total, skipped = 0, []
    for repo in repos:
        if repo in PROTECTED_REPOS:
            continue  # СВЯТОЕ: даже логи не читаем
        n, st = hits_last_days(token, owner, repo, since)
        if n is None:
            skipped.append("%s (HTTP %s)" % (repo, st))
        else:
            total += n
    line = "КВОТА-УДАРЫ: %d/30д" % total
    print(line, flush=True)
    emit(line, ("недоступны для чтения: " + ", ".join(skipped)) if skipped else ())
    if total and os.environ.get("QUOTA_HYGIENE_ON_HIT") == "1" and os.environ.get("GITHUB_REPOSITORY"):
        o, r = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        n = hygiene_now(token, o, r, datetime.now(timezone.utc))
        print("ГРАД: удар обнаружен — немедленная гигиена своего репо, удалено %d расходников." % n)
    elif total:
        print("ГРАД: удары есть, но QUOTA_HYGIENE_ON_HIT != 1 — гигиену не поднимаем, только рапорт.")
    else:
        print("ГРАД: чисто за %d дней — свидетельство критерия 2 дополнено." % DAYS_BACK)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
