# 🧬 HIVE-AUDIT · РЕВИЗОР-2026 · живой аудит флота

> Последняя ревизия: 2026-11-10T13:48:49Z UTC · тренды: GitHub Actions Security Roadmap 2026 · OpenSSF

| Показатель | Значение |
|---|---|
| Репозиториев в аудите | 50 |
| Средний счёт флота | **92.6/100** |
| Mutable `uses:` (не SHA-40) | 21 |
| Workflow без `permissions:` | 2 |
| Опасный `pull_request_target` | 0 |
| Default-ветка без защиты (и без rulesets) | 15 |

| Репо | Счёт | Грейд | Находки |
|---|---|---|---|
| POLYMATH-ATLAS-GESTALT-CANON | 30 | D | mutable uses ×7 |
| polymath-atlas | 35 | D | mutable uses ×6; без permissions ×1 |
| polymat-hive | 40 | D | mutable uses ×6 |
| polymath-multiagent | 75 | B | mutable uses ×2; без permissions ×1 |
| edinyy-svod | 90 | A | default-ветка без защиты |
| github-runbook | 90 | A | default-ветка без защиты |
| H-PE11-PHOENIX | 90 | A | default-ветка без защиты |
| language-through-the-ages | 90 | A | default-ветка без защиты |
| nous | 90 | A | default-ветка без защиты |
| polimat-hub | 90 | A | default-ветка без защиты |
| polimat-task174 | 90 | A | default-ветка без защиты |
| red-thread-debt-audit | 90 | A | default-ветка без защиты |
| rent-mechanism-q43 | 90 | A | default-ветка без защиты |
| repo-doctrine | 90 | A | default-ветка без защиты |
| ruvson-lyrics | 90 | A | default-ветка без защиты |
| task-graph-propagator | 90 | A | default-ветка без защиты |
| uace-pml | 90 | A | default-ветка без защиты |
| web-evolution-1991-2026 | 90 | A | default-ветка без защиты |
| windows-chronicle | 90 | A | default-ветка без защиты |
| .github | 100 | A+ | — |
| agryp | 100 | A+ | — |
| cell-rs | 100 | A+ | — |
| cell-swarm | 100 | A+ | — |
| cell65-host | 100 | A+ | — |
| combain-v2 | 100 | A+ | — |
| commons | 100 | A+ | — |
| domovenok | 100 | A+ | — |
| domovoy-tweaker | 100 | A+ | — |
| global-video-platforms-registry | 100 | A+ | — |
| karaoke-dream | 100 | A+ | — |
| markitdown | 100 | A+ | — |
| neutral-browser | 100 | A+ | — |
| os-forge | 100 | A+ | — |
| polymath-atlas-v107 | 100 | A+ | — |
| polymath-gen | 100 | A+ | — |
| polymath-os | 100 | A+ | — |
| polymath-stckg-core | 100 | A+ | — |
| polymath-tools-atlas | 100 | A+ | — |
| release-vault | 100 | A+ | — |
| revo | 100 | A+ | — |
| rtynbirf | 100 | A+ | — |
| rtynbirf.github.io | 100 | A+ | — |
| runtime-protocol | 100 | A+ | — |
| ruvson-rse2 | 100 | A+ | — |
| singulyar | 100 | A+ | — |
| singulyar-llm | 100 | A+ | — |
| uace-polymat | 100 | A+ | — |
| universal-agent | 100 | A+ | — |
| voice-atlas-llm | 100 | A+ | — |
| yazyk-skvoz-epohi | 100 | A+ | — |

## Закон ревизора

- находка ≠ приговор: ревизор ТОЛЬКО репортит, лечение — волна руками/доктором;
- ledger append-only: hive_auditor_ledger.jsonl;
- аларм в issue #10 — только при смене отпечатка находок (дедуп).
