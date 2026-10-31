# RESTORE.md — самовоскрешение репозитория

## Что это за репо
Ранбук настройки GitHub «человеком для человека» — стандарт настройки
всех репо аккаунта. Приватный репо: github.com/rtynbirf/github-runbook.

Ирония восстановления: ранбук может восстановить сам себя —
все команды в главах 01–05 проверены live и работают на голом месте.

## Восстановление из bundle
```bash
git clone github-runbook.bundle github-runbook
cd github-runbook
git remote add origin https://github.com/rtynbirf/github-runbook.git
git push -u origin main && git push --tags
```

## Где взять свежий bundle
1. Артефакт Actions: workflow `bundle-backup` (пн 03:00 UTC, 90 дней)
2. Локальные бандлы владельца: `github-runbook-fresh-*.bundle`

## Ключевые точки
- Тегов пока нет; первый тег — при следующей крупной главе
- Проверка после восстановления: CI (см. .github/workflows/ci.yml)
