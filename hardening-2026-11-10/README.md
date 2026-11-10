# hardening-2026-11-10 — пакет для исполнения агентами

Аудит аккаунта rtynbirf (46 репо: 31 публичных, 15 приватных) → что уже сделано → что осталось и в каком порядке.

| Файл | Для чего |
|---|---|
| `ТЗ.md` | что и зачем делаем, критерии «готово» |
| `ДОРОЖНАЯ-КАРТА.md` | волны W1–W4, порядок, откат |
| `AGENTS-HARDENING.md` | инструкция исполнителю: вход, правила, отчёт |
| `АУДИТ-2026-11-10.md` | снимок состояния с живого API |
| `ТРЕНДЫ.md` | что из мировых практик берём и почему |
| `tasks.json` | 76 задач в машинном виде (id, запрос, проверка, откат) |
| `scripts/hardening.py` | исполнитель: probe / plan / apply / verify, dry-run по умолчанию |
| `templates/` | SECURITY.md, dependabot.yml, CODEOWNERS, CITATION.cff |

Быстрый старт: `export GH_TOKEN=…` (только в env) → `python3 scripts/hardening.py probe` → `plan` → `apply T-xxxx --yes`.
