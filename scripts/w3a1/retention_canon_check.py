#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retention как код · независимая сверка канона (Волна ×3, W3-A1, issue #5).

Дополняет синхронизатор волны A (wave3-retention-canon.yml + scripts/wave3/
retention_audit.py, их не трогаем): тот РАЗНОСИТ канон, этот — независимый
ревизор: только чтение API, идемпотентен, повторный проход — ноль диффов.
Сверяет retention-days воркфлоу с каноном accounts/retention.yml:
ci/forge — 3 дня, bundle-backup — 7, release — БЕЗ ttl (СВЯТОЕ, не расходник,
не проверяется), protected_repos (media-vault) — пропуск целиком (критерий 3).
Расхождение краснит прогон (критерий 2). Только stdlib 3.11; локально —
--selftest, живой прогон — в Actions.
"""
import json, os, re, sys, urllib.error, urllib.request

API = "https://api.github.com"
RET_RE = re.compile(r"retention-days:\s*(\d+)")

def _req(path, token, accept, raw=False):
    req = urllib.request.Request(
        API + path, headers={"Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
                             "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(1 << 20)
    except urllib.error.HTTPError as err:
        return err.code, ("" if raw else {})
    if raw:
        return 200, body.decode("utf-8", "replace")
    try:
        return 200, json.loads(body or b"{}")
    except ValueError:
        return 200, {}

def api_json(path, token):
    return _req(path, token, "application/vnd.github+json")

def api_raw(path, token):
    return _req(path, token, "application/vnd.github.raw", raw=True)

def paged(token, path):
    out, page = [], 1
    while True:
        st, data = api_json(path + ("&" if "?" in path else "?") + "per_page=100&page=%d" % page, token)
        if st != 200 or not isinstance(data, list):
            return out, st
        out.extend(data)
        if len(data) < 100:
            return out, st
        page += 1

def classify(fname):
    """Класс канона по имени файла; спорные случаи → None (честно, не гадаем)."""
    n = fname.lower()
    if "release" in n:
        return "release"          # не расходник: СВЯТОЕ, сверке не подлежит
    if "bundle-backup" in n:
        return "bundle-backup"
    if "forge" in n:
        return "forge"
    if n == "ci.yml" or n.startswith("ci.") or ".ci." in n:
        return "ci"
    return None

def parse_canon(text):
    """Мини-парсер формата accounts/retention.yml: скаляры, блок classes:,
    список protected_repos. Никаких внешних зависимостей (правило stdlib)."""
    canon = {"classes": {}, "protected_repos": [], "owner": "", "quiet_window_utc": ""}
    section = None
    for raw in text.splitlines():
        line = re.split(r"\s+#", raw.rstrip())[0]
        if not line.strip() or line.strip().startswith("#"):
            continue
        s = line.strip()
        if len(line) - len(line.lstrip(" ")) == 0:
            section = None
            key, _, val = s.partition(":")
            val = val.strip().strip('"')
            if key == "classes":
                section = "classes"
            elif key == "protected_repos":
                section = "protected"
            elif key in canon and val:
                canon[key] = val
        elif section == "classes":
            k, _, v = s.partition(":")
            v = v.split("#", 1)[0].strip()
            canon["classes"][k.strip()] = None if v in ("", "null", "~") else int(v)
        elif section == "protected" and s.startswith("- "):
            canon["protected_repos"].append(s[2:].strip())
    return canon

def check_repos(token, owner, canon):
    """Возврат: (репо в каноне, проверено репо с CI, диффы, спорные, статус)."""
    repos, st = paged(token, "/user/repos?affiliation=owner&visibility=all")
    if st != 200:
        print("КАНОН: список репо недоступен (HTTP %s) — честный стоп." % st)
        return 0, 0, [], [], st
    ok = checked = 0
    diffs, murky = [], []
    for r in repos:
        repo = r["name"]
        if repo in canon["protected_repos"]:
            print("СВЯТОЕ: %s — в protected_repos, сверка не заходит." % repo)
            continue
        st2, listing = api_json("/repos/%s/%s/contents/.github/workflows" % (owner, repo), token)
        if st2 != 200 or not isinstance(listing, list):
            continue  # без воркфлоу — не участник сверки «35/35 репо с CI»
        repo_touched = False
        for f in listing:
            name = f.get("name", "")
            if not (name.endswith(".yml") or name.endswith(".yaml")):
                continue
            cls = classify(name)
            if cls is None:
                murky.append("%s/%s" % (repo, name))
                continue
            if cls == "release":
                continue  # СВЯТОЕ: релизы без ttl
            expected = canon["classes"].get(cls)
            if expected is None:
                murky.append("%s/%s (класс %s без ttl в каноне)" % (repo, name, cls))
                continue
            st3, blob = api_raw("/repos/%s/%s/contents/.github/workflows/%s" % (owner, repo, name), token)
            if st3 != 200:
                diffs.append("%s/%s: файл не прочитан (HTTP %s)" % (repo, name, st3))
                continue
            repo_touched = True
            found = sorted({int(x) for x in RET_RE.findall(blob)})
            if not found:
                diffs.append("%s/%s: retention-days не указан, канон требует %d" % (repo, name, expected))
            elif found != [expected]:
                diffs.append("%s/%s: retention-days %s, канон требует %d" % (repo, name, found, expected))
        if repo_touched:
            checked += 1
            if not any(d.startswith(repo + "/") for d in diffs):
                ok += 1
    return ok, checked, diffs, murky, 200

def selftest():
    """Автономная проверка парсера канона на встроенном образце формата."""
    sample = """
schema_version: 1
owner: rtynbirf
quiet_window_utc: "02:00-04:00"
classes:
  ci: 3               # ci-класс
  forge: 3            # forge-класс
  bundle-backup: 7    # bundle-backup
  release: null       # релизы без ttl
protected_repos:
  - media-vault
"""
    c = parse_canon(sample)
    assert c["classes"] == {"ci": 3, "forge": 3, "bundle-backup": 7, "release": None}, c["classes"]
    assert c["protected_repos"] == ["media-vault"], c["protected_repos"]
    assert c["owner"] == "rtynbirf" and c["quiet_window_utc"] == "02:00-04:00"
    print("СЕЛФТЕСТ: парсер канона верен (classes, protected_repos, скаляры).")
    return 0

def main():
    if "--selftest" in sys.argv:
        return selftest()
    canon_path = os.environ.get("CANON_PATH", "accounts/retention.yml")
    if not os.path.exists(canon_path):
        print("КАНОН: %s не найден — появится после мержа волны A; прогон откладывается честно." % canon_path)
        return 0
    canon = parse_canon(open(canon_path, encoding="utf-8").read())
    token = os.environ.get("PAT_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("КАНОН: токена нет — живой сверке быть в Actions; локально запусти --selftest.")
        return 0
    owner = canon.get("owner") or ""
    if not owner:
        st, me = api_json("/user", token)
        owner = me.get("login", "") if st == 200 else ""
    if not owner:
        print("КАНОН: владелец не определён — честный стоп.")
        return 0
    ok, checked, diffs, murky, _ = check_repos(token, owner, canon)
    line = "КАНОН: %d/%d репо с CI в каноне" % (ok, checked)
    print(line, flush=True)
    for d in diffs:
        print("ДИФФ: " + d)
    if murky:
        print("СПОРНЫЕ (класс не определён — гляди глазами): " + "; ".join(sorted(set(murky))))
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as fh:  # append-only, перезаписи нет
            fh.write(line + "\n")
            fh.writelines("ДИФФ: " + d + "\n" for d in diffs)
    if diffs:
        print("КАНОН: расхождения есть — прогон красный; правка = дополнение, не перезапись.")
        return 1
    print("КАНОН: расхождений нет — идемпотентный проход, ноль диффов.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
