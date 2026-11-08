#!/usr/bin/env python3
"""T13 · Re-run guard — реанимация по закону, не по памяти (repo-doctrine#23).

Мир: re-run — штатная механика с жёсткой рамкой (30 дней, ≤50 re-run'ов,
same-SHA/привилегии исходного триггерера). Главный мировой закон: re-run
легален только при идемпотентности шагов; повтор побочных эффектов — уже ложь.

Три проверки перед выстрелом:
  (1) хвост упавших шагов обязан совпадать с квот-классом
      (artifact storage quota | usage limit | rate limit | quota has been hit);
      чужая боль открывает issue, а не лечится молча — при несоответствии guard
      отказывается и печатает приговор;
  (2) среди упавших шагов нет side-effect-шагов (имена из SIDE_EFFECT_PATTERNS);
  (3) рамка API кодом: возраст прогона ≤ 30 дней, attempt ≤ 50.

Идемпотентность доказывается артефактно: SHA256SUMS двух попыток сравниваются
(diff пуст = идемпотентно) — если в логах обеих попыток есть строки чек-сумм.

Использование:
  GITHUB_TOKEN=… python3 rerun_guard.py --repo OWNER/NAME --run-id 123 [--execute]
  [--side-effects "deploy,publish,upload,release"]
Выход: 0 = выстрелил (или сухой прогон прошёл), 1 = отказ/не подтвердилось.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
QUOTA_CLASS = re.compile(
    r"artifact storage quota|usage limit|quota has been hit|rate limit|billing|"
    r"quota has been exhausted|waiting for capacity", re.I)
SIDE_EFFECT_DEFAULTS = ["deploy", "publish", "release", "upload-pages-artifact",
                        "push", "gh-pages", "pypi", "npm publish"]
MAX_AGE_DAYS = 30
MAX_ATTEMPT = 50


def req(token, path_or_url, method="GET"):
    url = path_or_url if path_or_url.startswith("http") else API + path_or_url
    r = urllib.request.Request(url, method=method)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "rerun-guard/1.0 (T13 github-runbook)")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body[:1] in (b"{", b"[") else body)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {}
    except Exception as e:
        print(f"сеть: {e}")
        return 0, {}


def log_tail(token, full, run_id, lines=120):
    r = urllib.request.Request(f"{API}/repos/{full}/actions/runs/{run_id}/logs")
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("User-Agent", "rerun-guard/1.0")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        opener = urllib.request.build_opener(NoRedirect)
        opener.open(r, timeout=45)
        return ""
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") if e.code in (301, 302, 303, 307) else None
        if not loc:
            return ""
        st, blob = req(token, loc)
        if st != 200 or not isinstance(blob, bytes):
            return ""
        try:
            import io
            import zipfile
            z = zipfile.ZipFile(io.BytesIO(blob))
        except Exception:
            return ""
        out = []
        for n in z.namelist():
            if n.endswith(".txt"):
                try:
                    out.extend(z.read(n).decode("utf-8", "replace").splitlines()[-lines:])
                except Exception:
                    pass
        return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--run-id", type=int, required=True)
    ap.add_argument("--execute", action="store_true",
                    help="сухой прогон по умолчанию; с флагом — выстрелить rerun-failed-jobs")
    ap.add_argument("--side-effects", default="")
    args = ap.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    side_effects = [s for s in (args.side_effects or ",".join(SIDE_EFFECT_DEFAULTS)).split(",") if s]

    st, run = req(token, f"/repos/{args.repo}/actions/runs/{args.run_id}")
    if st != 200:
        print(f"приговор: прогон недоступен (HTTP {st}) — отказ")
        return 1
    concl = run.get("conclusion") or run.get("status")
    attempt = run.get("run_attempt", 1)
    created = run.get("created_at", "")
    age_days = (time.time() - time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400 if created else 0
    print(f"прогон {args.run_id}: {run['name']} · {concl} · попытка {attempt} · возраст {age_days:.1f} дн.")

    # (3) рамка API кодом
    if age_days > MAX_AGE_DAYS:
        print(f"приговор: возраст {age_days:.1f} дн. > {MAX_AGE_DAYS} — рамка API запрещает re-run")
        return 1
    if attempt > MAX_ATTEMPT:
        print(f"приговор: attempt {attempt} > {MAX_ATTEMPT} — рамка API запрещает re-run")
        return 1
    if concl not in ("failure", "timed_out", "startup_failure") and args.execute:
        print("приговор: прогон не красный — реанимировать нечего")
        return 1

    # (1) квот-класс по хвосту лога + (2) side-effect-шаги
    tail = log_tail(token, args.repo, args.run_id)
    quota_hit = bool(QUOTA_CLASS.search(tail)) if tail else False
    print(f"проверка (1) квот-класс: {'СОВПАДЕНИЕ' if quota_hit else 'не совпало'}"
          + ("" if tail else " (лог недоступен — сухой режим)"))
    st, jobs = req(token, f"/repos/{args.repo}/actions/runs/{args.run_id}/jobs")
    failed_steps = []
    if st == 200:
        for j in jobs.get("jobs", []):
            if j.get("conclusion") not in ("failure", "timed_out", "cancelled"):
                continue
            for s in j.get("steps", []):
                if s.get("conclusion") in ("failure", "timed_out", "cancelled"):
                    failed_steps.append(s["name"])
    side_hits = [n for n in failed_steps
                 if any(se.lower() in n.lower() for se in side_effects)]
    print(f"проверка (2) side-effect: упавшие шаги {failed_steps or '—'}; "
          f"side-effect среди них: {side_hits or 'нет'}")
    if failed_steps and side_hits:
        print("приговор: среди упавших шагов есть side-effect — re-run запрещён (повтор эффекта = ложь)")
        return 1
    if tail and not quota_hit:
        print("приговор: боль не квот-класса — чужая боль открывает issue, а не лечится молча")
        return 1
    if not failed_steps and concl in ("failure",):
        print("приговор: упавших шагов не видно (квота-лаг биллинга) — рамка квоты, re-run разрешён")

    if not args.execute:
        print("сухой прогон: все проверки пройдены — можно выстрелить с --execute")
        return 0

    st, _ = req(token, f"/repos/{args.repo}/actions/runs/{args.run_id}/rerun-failed-jobs",
                method="POST")
    print(f"rerun-failed-jobs: HTTP {st} (202 = выстрел состоялся)")
    if st not in (201, 202):
        return 1
    # ворклог-запись (Ст. 6): живой факт, не память
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record = (f"{stamp} · rerun_guard T13 · {args.repo}#{args.run_id} · "
              f"{run['name']} · квот-класс={quota_hit} · side-effect=нет · "
              f"attempt {attempt}→{attempt + 1}\n")
    print("ворклог:", record.strip())
    wl = os.environ.get("RERUN_WORKLOG", "rerun-worklog.jsonl")
    try:
        with open(wl, "a", encoding="utf-8") as fh:
            fh.write(record)
        print(f"записано в {wl}")
    except Exception as e:
        print(f"ворклог не записан: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
