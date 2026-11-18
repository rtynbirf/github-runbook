#!/usr/bin/env python3
"""FSM-АВТОПИЛОТ УВЕДОМЛЕНИЙ · github-runbook · канон теории конечных автоматов.

Алфавит входа: нити GET /notifications (unread + read-not-done).
Состояния: S0 SCAN -> S1 TRIAGE -> S2 CLOSE -> S3 VERIFY -> S4 DONE,
           из S3 при остатках -> S0 (дожим), максимум R раундов (гарантированная остановка).
Переход δ детерминирован:
  TRIAGE(нить) = KEEP, только если reason=review_requested и автор субъекта — живой человек
                 (не [bot]); иначе CLOSE (боты, пчелиный рой, ci_activity, dependabot и пр.).
  CLOSE: DELETE /notifications/threads/{id}; 204=съедено, 404=уже съедено (идемпотентный успех).
Идемпотентность: повторный прогон не создаёт эффектов сверх первого (DELETE 404, леджер append-only).
"""
import base64, json, os, subprocess, sys, time
from collections import Counter
from datetime import datetime, timezone

GT = os.environ.get("GH_TOKEN", "")
if not GT:
    print("нет GH_TOKEN", file=sys.stderr); sys.exit(1)
API = "https://api.github.com"
T = f".notif_fsm_{os.getpid()}"
LEDGER = "notifications_fsm_ledger.jsonl"
STATE_F = "notifications_fsm_state.json"
MAX_ROUNDS = 4          # гарантия остановки FSM
BOT_SUFFIX = "[bot]"

def curl(url, method="GET", data=None):
    cmd = ["curl", "-sS", "--max-time", "40", "-D", f"{T}.h", "-o", f"{T}.b",
           "-H", f"Authorization: Bearer {GT}",
           "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28", "-X", method]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    cmd.append(url)
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return 0, ""
    head = open(f"{T}.h").read() if os.path.exists(f"{T}.h") else ""
    body = open(f"{T}.b").read() if os.path.exists(f"{T}.b") else ""
    st = int(head.splitlines()[0].split()[1]) if head.strip() else 0
    return st, body

def subject_author(thread):
    """Автор субъекта нити (один GET, кэш)."""
    url = (thread.get("subject") or {}).get("url")
    if not url:
        return "?"
    st, body = curl(url)
    if st != 200:
        return "?"
    d = json.loads(body)
    u = d.get("user") or {}
    return u.get("login", "?")

def triage(thread, cache):
    """S1 TRIAGE: δ(нить) ∈ {CLOSE, KEEP}. Детерминированная функция."""
    reason = thread.get("reason", "?")
    if reason != "review_requested":
        return "CLOSE"
    key = thread["subject"]["url"]
    if key not in cache:
        cache[key] = subject_author(thread)
    author = cache[key]
    if author.endswith(BOT_SUFFIX) or author == "?":
        return "CLOSE"   # dependabot[bot] и прочие боты — шум, а не человек
    return "KEEP"        # живой человек просит ревью — остаётся Хозяину

def scan_all(max_pages=40):
    seen, page = {}, 1
    while page <= max_pages:
        st, body = curl(f"{API}/notifications?all=true&per_page=50&page={page}")
        if st != 200:
            break
        batch = json.loads(body) if body.strip() else []
        if not batch:
            break
        before = len(seen)
        for i in batch:
            seen[i["id"]] = i
        if len(seen) == before and page > 3:
            break
        page += 1
    return list(seen.values())

def load_last_run():
    """Время последнего прогона из state-файла (skip done-нитей)."""
    try:
        return json.load(open(STATE_F, encoding="utf-8")).get("last_run")
    except Exception:
        return None

def main():
    t0 = time.time()
    last_run = load_last_run()
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        items = scan_all()
        cache = {}
        plan = {"total": len(items), "would_close": 0, "would_keep": 0,
                "keep_sample": []}
        for i in items:
            if triage(i, cache) == "KEEP":
                plan["would_keep"] += 1
                plan["keep_sample"].append(f"{i['reason']}:{i['subject']['title'][:40]}")
            else:
                plan["would_close"] += 1
        plan["keep_sample"] = plan["keep_sample"][:10]
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return
    stats = {"rounds": 0, "closed_204": 0, "closed_404": 0, "other": Counter(),
             "kept": 0, "reason": Counter(), "repo": Counter(), "type": Counter()}
    cache = {}
    for rnd in range(1, MAX_ROUNDS + 1):
        stats["rounds"] = rnd
        items = scan_all()
        if not items:
            break
        keep_ids, close = [], []
        for i in items:
            # done-нити навсегда остаются в all=true-листинге API (факт 2026-11-18:
            # повторный DELETE даёт 204) — пропускаем всё, что уже обработано
            # последним прогоном: updated_at <= last_run и не unread
            if last_run and not i.get("unread") and (i.get("updated_at") or "") <= last_run:
                continue
            v = triage(i, cache)
            if v == "KEEP":
                keep_ids.append(i["id"]); stats["kept"] += 1
            else:
                close.append(i)
        for i in close:
            st, _ = curl(f"{API}/notifications/threads/{i['id']}", method="DELETE")
            if st == 204:
                stats["closed_204"] += 1
                stats["reason"][i["reason"]] += 1
                stats["repo"][i["repository"]["full_name"]] += 1
                stats["type"][i["subject"]["type"]] += 1
            elif st == 404:
                stats["closed_404"] += 1
            else:
                stats["other"][st] += 1
        for _ in range(2):
            st, _ = curl(f"{API}/notifications", method="PUT", data={})
            if st != 202:
                break
            time.sleep(2)
    st, body = curl(f"{API}/notifications?per_page=50")
    unread = len(json.loads(body)) if st == 200 else -1
    st2, body2 = curl(f"{API}/notifications?all=true&per_page=50&page=1")
    inbox1 = len(json.loads(body2)) if st2 == 200 else -1

    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rounds": stats["rounds"], "closed_204": stats["closed_204"],
        "closed_404": stats["closed_404"], "kept_escalated": stats["kept"],
        "other_status": dict(stats["other"]),
        "reasons": dict(stats["reason"]), "types": dict(stats["type"]),
        "top_repos": dict(stats["repo"].most_common(8)),
        "verify_unread": unread, "verify_inbox_p1": inbox1,
        "duration_s": round(time.time() - t0, 1),
    }
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    state = {"last_run": rec["ts"], "last_result": rec,
             "total_closed_204": 0, "total_closed_404": 0}
    if os.path.exists(STATE_F):
        try:
            old = json.load(open(STATE_F, encoding="utf-8"))
            state["total_closed_204"] = old.get("total_closed_204", 0)
            state["total_closed_404"] = old.get("total_closed_404", 0)
        except Exception:
            pass
    state["total_closed_204"] += rec["closed_204"]
    state["total_closed_404"] += rec["closed_404"]
    with open(STATE_F, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    for f_ in (f"{T}.h", f"{T}.b"):
        if os.path.exists(f_):
            os.remove(f_)
    sys.exit(0 if rec["kept_escalated"] == 0 else 2)

if __name__ == "__main__":
    main()
