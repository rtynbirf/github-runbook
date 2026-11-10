#!/usr/bin/env python3
# Волна ×18 «БЛЕСК ДОМА» · 2026-11-10 — П-34 (polimat-hub#52).
# Канон имён становится законом: "канон, который не линтится, — это пожелание;
# канон, который линтится, — это закон".
#
# Линтер имён репо дома:
#   1) kebab-case: ^[a-z0-9][a-z0-9-]*$ (только строчные, цифры, дефисы)
#   2) FORBIDDEN-имена канона: windows-encyclopedia, windows-full-report, polimat-vault
#   3) бренд-префиксы "не-канон" по SWARM: microsoft-, apple-, google-, amazon-
#      (windows-канон дома — исключение: windows-chronicle легален как историческая линия)
#
# Режимы:
#   python3 repo_inventory.py            → живая опись флота + линт имён (rc=0/1)
#   python3 repo_inventory.py --self-test → ловушка: проверочные нарушители ДОЛЖНЫ быть
#                                           пойманы (rc=0, если тест пройден)
import json
import re
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com"
TOKEN_FILE = Path("/tmp/hive/classic")
FORBIDDEN_NAMES = {"windows-encyclopedia", "windows-full-report", "polimat-vault"}
BRAND_PREFIXES = ("microsoft-", "apple-", "google-", "amazon-")
KEBAB = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# Документированные исключения канона (закон с реестром исключений — всё равно закон):
#   .github, <owner>.github.io — платформенные контракты GitHub (имя менять нельзя);
#   H-PE11-PHOENIX — канон-наследие дома (линия PHOENIX, живёт до решения Хозяина).
PLATFORM_CONTRACTS = {".github", "rtynbirf.github.io"}
HOUSE_LEGACY = {"H-PE11-PHOENIX"}
ARCHIVED_ALLOWED = {"rumu"}  # архивный канон (снапшот ×3)


def token() -> str:
    return TOKEN_FILE.read_text().strip()


def api(url: str):
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token()}",
                      "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def lint_name(name: str):
    """None = чисто; строка-исключение = легально; строка-нарушение = красный."""
    if name in PLATFORM_CONTRACTS:
        return None  # платформенный контракт GitHub (документированное исключение)
    if name in HOUSE_LEGACY:
        return None  # канон-наследие дома (документированное исключение)
    if name in FORBIDDEN_NAMES:
        return f"FORBIDDEN-имя канона: {name} (запрещён реестром дома)"
    for bp in BRAND_PREFIXES:
        if name.startswith(bp):
            return f"бренд-префикс «{bp}» не-канон по SWARM: {name}"
    if not KEBAB.match(name):
        return ("не kebab-case (^[a-z0-9][a-z0-9-]*$): "
                f"{name} — только строчные/цифры/дефисы")
    if "--" in name or name.endswith("-"):
        return f"гигиена дефисов: {name}"
    return None


def fleet() -> list[dict]:
    repos, page = [], 1
    while True:
        batch = api(f"{API}/user/repos?per_page=100&sort=full_name&page={page}")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def run_inventory() -> int:
    repos = fleet()
    rows, violations = [], 0
    for r in repos:
        name = r["name"]
        v = lint_name(name)
        rows.append((name, "ок" if v else "ок" if False else ("НАРУШЕНИЕ" if v else "ok"),
                     v or ""))
        if v:
            violations += 1
    for name in sorted(rows):
        mark = "🔴" if name[2] else "🟢"
        if name[2]:
            print(f"{mark} {name[0]:40s} {name[2]}")
    print(f"\nопись: {len(rows)} репо · нарушений имён: {violations}")
    print("правило: kebab-case ^[a-z0-9][a-z0-9-]*$ · FORBIDDEN: "
          + ", ".join(sorted(FORBIDDEN_NAMES))
          + " · бренд-префиксы: " + ", ".join(BRAND_PREFIXES))
    return 1 if violations else 0


def self_test() -> int:
    cases = {
        "Bad_Underscore": "не kebab-case",
        "Upper-Case": "не kebab-case",
        "microsoft-fake": "бренд-префикс",
        "apple-fake": "бренд-префикс",
        "windows-encyclopedia": "FORBIDDEN",
        "windows-full-report": "FORBIDDEN",
        "polimat-vault": "FORBIDDEN",
        "dvoynoy--defis": "гигиена дефисов",
        "hvost-": "гигиена дефисов",
        "-nachalo": "не kebab-case",
        "legit-name-1": None,
        "ok123": None,
        "windows-chronicle": None,  # канон-исключение дома
    }
    caught, missed, clean_ok = 0, [], 0
    for name, expect in cases.items():
        v = lint_name(name)
        if expect is None:
            if v is None:
                clean_ok += 1
            else:
                missed.append(f"{name} — чистое имя помечено: {v}")
        else:
            if v is not None:
                caught += 1
            else:
                missed.append(f"{name} — нарушитель ПРОПУЩЕН (ожидали: {expect})")
    print(f"самотест: поймано нарушителей {caught}/10 · чистых подтверждено "
          f"{clean_ok}/{len(cases) - 10}")
    for m in missed:
        print("ПРОВАЛ:", m)
    return 0 if not missed else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run_inventory())
