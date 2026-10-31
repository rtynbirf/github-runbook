# SOURCES.md — журнал верификации

Правило аккаунта: факт попадает в документ только после проверки. Ниже — все проверки,
на которых стоит этот мануал. Дата исполнения: **01.11.2026 (UTC+8)**.

## A. Живые API-тесты (первичный источник — сами ответы GitHub API)

| # | Действие | Endpoint | Ответ | Что доказывает |
|---|---|---|---|---|
| A-01 | Проверка токена | `GET /user` | **200** | токен жив, логин `rtynbirf` |
| A-02 | Инвентаризация | `GET /user/repos?per_page=100` | 200, 18 репо | картина аккаунта |
| A-03 | Статус cell65-host | `GET /repos/rtynbirf/cell65-host` | 200 | `private=False` до настройки |
| A-04 | Статус windows-full-report | `GET /repos/rtynbirf/windows-full-report` | 200 | уже private |
| A-05 | Статус windows-encyclopedia | `GET /repos/rtynbirf/windows-encyclopedia` | **404** | репо не существовало |
| A-06 | Создание приватного репо | `POST /user/repos` (windows-encyclopedia) | **201** | fine-grained PAT имеет Administration: write |
| A-07 | Пуш windows-encyclopedia | `git push -u origin main` | OK, new branch main | содержимое выложено |
| A-08 | Сверка cell65-host | `git fetch` + `rev-list --left-right --count` | 0/3 → ff-merge → **0/0** | чужие 3 коммита поглощены без force-push |
| A-09 | Теги на удалёнке | `git ls-remote --tags origin` | v1.0.0, v1.0.0-mv3, v1.1.0 | все теги целы |
| A-10 | Все флаги × 3 репо | `PATCH /repos/{repo}` | **200 × 3** | private=true, фичи, merge-флаги |
| A-11 | Топики × 3 | `PUT /repos/{repo}/topics` | **200 × 3** | топики записаны |
| A-12 | Dependabot alerts × 3 | `PUT /repos/{repo}/vulnerability-alerts` | **204 × 3** | активны на приватных репо Free |
| A-13 | Security fixes × 3 | `PUT /repos/{repo}/automated-security-fixes` | **204 × 3** | активны |
| A-14 | Branch protection × 3 | `PUT /repos/{repo}/branches/main/protection` | **403 × 3** | гейт тарифа, цитата тела ответа ниже |
| A-15 | Контрольный GET cell65-host | `GET /repos/rtynbirf/cell65-host` | 200 | private=True, 11 топиков, флаги подтверждены |
| A-16 | Пуш пакета автономности × 4 | `git fetch` + `rev-list --left-right --count` → rebase/ff → `git push` | cell65-host: расхождение 1/5 → rebase (впитаны 5 чужих коммитов) → push `72dfcf4`; остальные — ff-push `2a0b9f8`, `0e1c18a`, `d0e3a02`; после пуша 0/0 × 4 | пакет на main всех репо; чужая история не тронута, force-push не применялся |
| A-17 | Ручной тест бэкапа | `POST /repos/{repo}/actions/workflows/bundle-backup.yml/dispatches` | **403 × 4** «Resource not accessible by personal access token» | у текущего PAT нет права Actions:write — dispatch только с ним. Плановый cron запускает сам GitHub (первая живая проверка — пн 03:00 UTC во вкладке Actions) |
| A-18 | Workflows на удалёнке | `GET /repos/{repo}/contents/.github/workflows?ref=main` | **200 × 4** | `ci.yml` + `bundle-backup.yml` + `release.yml` на main во всех репо (+ чужие `selftest.yml`, `guardian-tripwire.yml` целы) |
| A-19 | Локальная репетиция CI | `scripts/local-ci-rehearsal.sh` (шаги один-в-один из ci.yml) | зелёный × 4 | PAC «ВСЕ PAC-ТЕСТЫ ЗЕЛЁНЫЕ»; CSV 42/40/27/41 строк, 0 брака; каркас 6 эпох; ранбук: главы+карта+журнал; живых токенов в md нет |
| A-20 | Реестр workflows | `GET /repos/{repo}/actions/workflows` | **200 × 4** (токен с правом Actions) | во всех репо state=active: `ci`, `bundle-backup`, `release` (+ чужие `selftest`, `guardian-tripwire` целы); в каждом поднялся авто-workflow «Dependabot Updates» — dependabot.yml принят платформой |
| A-21 | Ручной запуск бэкапа (PAT с Actions:write) | `POST /repos/{repo}/actions/workflows/bundle-backup.yml/dispatches` | **204 × 4** | cron-канал жив: GitHub принял dispatch на ref=main |
| A-22 | Итоги запусков Actions | `GET /repos/{repo}/actions/runs` | success — все запуски | в каждом репо: `ci` (push и PR) success, `bundle-backup` #1 success (2026-10-31 20:55–20:56 UTC); также success: `selftest` (cell65-host), чужой `guardian-tripwire` (windows-full-report), авто-Dependabot × 4 |
| A-23 | Bundle-артефакты | `GET /repos/{repo}/actions/artifacts` | **200 × 4, total_count=1** | `git-bundle-<репо>-…`: 26–447 КБ, истекают 2027-01-29 (= 90 дней — retention подтверждён live) |

**Дословное тело 403 (A-14):**

```json
{
  "message": "Upgrade to GitHub Pro or make this repository public to enable this feature.",
  "documentation_url": "https://docs.github.com/rest/branches/branch-protection#update-branch-protection",
  "status": "403"
}
```

## B. Веб-источники (проверены поиском 01.11.2026)

1. **GitHub Docs — About protected branches**: «Protected branches are also available
   in public and private repositories with GitHub Pro, GitHub Team, GitHub Enterprise
   Cloud, and GitHub Enterprise Server». → подтверждает 403: на Free защита веток —
   только в публичных репо.
   URL: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
2. **GitHub Docs — Permissions required for fine-grained PATs**: перечень прав
   (Administration — для создания/настроек репо, Contents — для пуша).
   URL: https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
3. **GitHub Docs — Managing your personal access tokens**: лимит 50 fine-grained токенов
   на аккаунт.
   URL: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
4. **GitHub Changelog — Secret scanning (2026-03-31)**: новые типы секретов; push
   protection по умолчанию — «for all repositories with secret scanning enabled,
   including for free public repositories» → в приватных бесплатных репо полный
   secret scanning — часть платных планов.
   URL: https://github.blog/changelog/2026-03-31-github-secret-scanning-nine-new-types-and-more
5. **GitHub Community discussion #209198 (2026-09/10)**: разбор «личный аккаунт +
   приватное репо»: classic protection и rulesets на Pro enforce'ятся; «Restrict who
   can push» — только для организаций Team/Enterprise.
   URL: https://github.com/orgs/community/discussions/209198
6. **GitHub CLI — `gh release create`**: флаг `--generate-notes` — дословно:
   «Automatically generate title and notes for the release via GitHub Release Notes
   API» (используется в release.yml всех репо).
   URL: https://cli.github.com/manual/gh_release_create (проверено fetch-ем 01.11.2026)

## C. Что в мануале НЕ считается проверенным

- Точные интерфейсные пути кнопок GitHub (UI меняется) — даны как ориентир, а не факт.
- Даты следующих тарифных изменений GitHub — предсказания запрещены правилом аккаунта.

## D. Лог-файл сессии

Полный вывод настройки: `/tmp/setup-log.txt` (живёт в сессии; содержимое свернуто в
таблицу A). Скрипт настройки: `scripts/setup-repos.sh` (в локальном хранилище сессии).
Скрипты сессии 01.11.2026 (пакет автономности): `push-autonomy.sh` (ff-дисциплина),
`verify-autonomy.sh`, `probe-perms.sh` (зонд прав PAT), `local-ci-rehearsal.sh`,
`contents-verify.sh`, `artifacts-check.sh` (проверка bundle-артефактов) — там же.
