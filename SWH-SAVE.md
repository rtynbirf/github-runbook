# 📚 SWH-SAVE · Software Heritage Save Code Now · публичный флот

> Прогон: 2026-11-10T14:33:34Z UTC · П-28 (polimat-hub#46) · POST /origin/save/github/rtynbirf/<repo>/

**SWH coverage: запрошено 0/50 · статусы задач {}**

> ⛔ **Anubis anti-bot**: archive.softwareheritage.org отдаёт PoW-вызов (HTML «Oh noes!», /.within.website) вместо JSON на все API-запросы с серверных IP — независимо от User-Agent (curl×3 UA + urllib POST + GET = 5 независимых проб). Это факт платформы, не ошибка скрипта: 50/50 позиций заблокированы/пропущены.
> Разблокировка (решение Хозяина): SWH-токен (https://archive.softwareheritage.org/api/1/token/) или ручной POST через браузер; скрипт готов — при живом канале перезапуск покроет весь флот.

| Репо | HTTP | save_request | save_task | verify |
|---|---|---|---|---|
| .github | 200 | ANUBIS-BLOCK | — | — |
| H-PE11-PHOENIX | 200 | ANUBIS-BLOCK | — | — |
| POLYMATH-ATLAS-GESTALT-CANON | 200 | ANUBIS-BLOCK | — | — |
| agryp | 0 | SKIPPED | — | — |
| cell-rs | 0 | SKIPPED | — | — |
| cell-swarm | 0 | SKIPPED | — | — |
| cell65-host | 0 | SKIPPED | — | — |
| combain-v2 | 0 | SKIPPED | — | — |
| commons | 0 | SKIPPED | — | — |
| domovenok | 0 | SKIPPED | — | — |
| domovoy-tweaker | 0 | SKIPPED | — | — |
| edinyy-svod | 0 | SKIPPED | — | — |
| github-runbook | 0 | SKIPPED | — | — |
| global-video-platforms-registry | 0 | SKIPPED | — | — |
| karaoke-dream | 0 | SKIPPED | — | — |
| language-through-the-ages | 0 | SKIPPED | — | — |
| markitdown | 0 | SKIPPED | — | — |
| neutral-browser | 0 | SKIPPED | — | — |
| nous | 0 | SKIPPED | — | — |
| os-forge | 0 | SKIPPED | — | — |
| polimat-hub | 0 | SKIPPED | — | — |
| polimat-task174 | 0 | SKIPPED | — | — |
| polymat-hive | 0 | SKIPPED | — | — |
| polymath-atlas | 0 | SKIPPED | — | — |
| polymath-atlas-v107 | 0 | SKIPPED | — | — |
| polymath-gen | 0 | SKIPPED | — | — |
| polymath-multiagent | 0 | SKIPPED | — | — |
| polymath-os | 0 | SKIPPED | — | — |
| polymath-stckg-core | 0 | SKIPPED | — | — |
| polymath-tools-atlas | 0 | SKIPPED | — | — |
| red-thread-debt-audit | 0 | SKIPPED | — | — |
| release-vault | 0 | SKIPPED | — | — |
| rent-mechanism-q43 | 0 | SKIPPED | — | — |
| repo-doctrine | 0 | SKIPPED | — | — |
| revo | 0 | SKIPPED | — | — |
| rtynbirf | 0 | SKIPPED | — | — |
| rtynbirf.github.io | 0 | SKIPPED | — | — |
| runtime-protocol | 0 | SKIPPED | — | — |
| ruvson-lyrics | 0 | SKIPPED | — | — |
| ruvson-rse2 | 0 | SKIPPED | — | — |
| singulyar | 0 | SKIPPED | — | — |
| singulyar-llm | 0 | SKIPPED | — | — |
| task-graph-propagator | 0 | SKIPPED | — | — |
| uace-pml | 0 | SKIPPED | — | — |
| uace-polymat | 0 | SKIPPED | — | — |
| universal-agent | 0 | SKIPPED | — | — |
| voice-atlas-llm | 0 | SKIPPED | — | — |
| web-evolution-1991-2026 | 0 | SKIPPED | — | — |
| windows-chronicle | 0 | SKIPPED | — | — |
| yazyk-skvoz-epohi | 0 | SKIPPED | — | — |

## Метод

- POST /origin/save/github/... — официальный механизм сохранения (softwareheritage.org);
- уважение к чужому лимиту: X-RateLimit-Remaining/Reset читаются каждый запрос, на 429 — backoff до reset (≤15 мин), иначе честная остановка (прецедент fossology#1836);
- Anubis-детектор: HTML «Oh noes!» вместо JSON = вердикт ANUBIS-BLOCK, 3 подряд = честная остановка полного прогона;
- журнал: hive_swh_ledger.jsonl (append-only, сырые коды и статусы — факт = байты).
