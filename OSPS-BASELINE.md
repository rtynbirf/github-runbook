# 🏛 HIVE-OSPS · Level 1 самооценка флота · OSPS Baseline v2026.08.28

> Ревизия: 2026-11-10T15:14:04Z UTC · 24 требования L1 · вердикты: VERIFIED (API) / ATTEST (самодекларация) / NA-PRIV (честное отклонение приватности) / FAIL (лечить)

| Показатель | Значение |
|---|---|
| Репозиториев в самооценке | 50 |
| Средний L1-покрытие флота | **99.1%** |
| VERIFIED всего | 789 |
| ATTEST всего | 400 |
| FAIL всего | 11 |
| NA / NA-PRIV (честные отклонения) | 0 |

| Репо | L1 | SPDX | Провалы |
|---|---|---|---|
| yazyk-skvoz-epohi | 87.5% | NOASSERTION | OSPS-LE-02.01, OSPS-LE-02.02, OSPS-VM-02.01 |
| neutral-browser | 91.7% | NOASSERTION | OSPS-LE-02.01, OSPS-LE-02.02 |
| polymath-atlas | 91.7% | NOASSERTION | OSPS-LE-02.01, OSPS-LE-02.02 |
| domovenok | 95.8% | MIT | OSPS-VM-02.01 |
| polymat-hive | 95.8% | MIT | OSPS-VM-02.01 |
| POLYMATH-ATLAS-GESTALT-CANON | 95.8% | MIT | OSPS-VM-02.01 |
| polymath-multiagent | 95.8% | MIT | OSPS-VM-02.01 |
| .github | 100.0% | MIT | — |
| agryp | 100.0% | MIT | — |
| cell-rs | 100.0% | Apache-2.0 | — |
| cell-swarm | 100.0% | Apache-2.0 | — |
| cell65-host | 100.0% | MIT | — |
| combain-v2 | 100.0% | MIT | — |
| commons | 100.0% | Apache-2.0 | — |
| domovoy-tweaker | 100.0% | MIT | — |
| edinyy-svod | 100.0% | CC-BY-4.0 | — |
| github-runbook | 100.0% | CC-BY-4.0 | — |
| global-video-platforms-registry | 100.0% | CC-BY-4.0 | — |
| H-PE11-PHOENIX | 100.0% | MIT | — |
| karaoke-dream | 100.0% | MIT | — |
| language-through-the-ages | 100.0% | CC-BY-4.0 | — |
| markitdown | 100.0% | MIT | — |
| nous | 100.0% | MIT | — |
| os-forge | 100.0% | MIT | — |
| polimat-hub | 100.0% | Apache-2.0 | — |
| polimat-task174 | 100.0% | CC-BY-4.0 | — |
| polymath-atlas-v107 | 100.0% | MIT | — |
| polymath-gen | 100.0% | MIT | — |
| polymath-os | 100.0% | MIT | — |
| polymath-stckg-core | 100.0% | MIT | — |
| polymath-tools-atlas | 100.0% | MIT | — |
| red-thread-debt-audit | 100.0% | CC-BY-4.0 | — |
| release-vault | 100.0% | MIT | — |
| rent-mechanism-q43 | 100.0% | CC-BY-4.0 | — |
| repo-doctrine | 100.0% | CC-BY-4.0 | — |
| revo | 100.0% | MIT | — |
| rtynbirf | 100.0% | MIT | — |
| rtynbirf.github.io | 100.0% | MIT | — |
| runtime-protocol | 100.0% | Apache-2.0 | — |
| ruvson-lyrics | 100.0% | MIT | — |
| ruvson-rse2 | 100.0% | MIT | — |
| singulyar | 100.0% | MIT | — |
| singulyar-llm | 100.0% | Apache-2.0 | — |
| task-graph-propagator | 100.0% | Apache-2.0 | — |
| uace-pml | 100.0% | MIT | — |
| uace-polymat | 100.0% | MIT | — |
| universal-agent | 100.0% | MIT | — |
| voice-atlas-llm | 100.0% | MIT | — |
| web-evolution-1991-2026 | 100.0% | CC-BY-4.0 | — |
| windows-chronicle | 100.0% | CC-BY-4.0 | — |

## Метод

- VERIFIED: rulesets/protection (AC-03), README/CONTRIBUTING/SECURITY/LICENSE-файл (DO/GV/LE/VM), has_issues (GV-02), манифесты зависимостей (QA-02), публичность (QA-01);
- BR-01.03 опирается на живую ревизию ×14: pull_request_target = 0 по всему флоту;
- ATTEST: MFA (AC-01.01), санитизация метаданных (BR-01.01), шифрование каналов (BR-03), отсутствие секретов в VCS (BR-07.01) — вне API, декларируем каноном улья (токены только env/secrets, §×14);
- QA-04.01: реестр кодовых баз дома = РЕЕСТР + мастер-индекс issue #10;
- FAIL — корм автопилота следующей волны (SECURITY/LICENSE/манифесты докладывает доктор).
