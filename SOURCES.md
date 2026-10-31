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

## C. Что в мануале НЕ считается проверенным

- Точные интерфейсные пути кнопок GitHub (UI меняется) — даны как ориентир, а не факт.
- Даты следующих тарифных изменений GitHub — предсказания запрещены правилом аккаунта.

## D. Лог-файл сессии

Полный вывод настройки: `/tmp/setup-log.txt` (живёт в сессии; содержимое свернуто в
таблицу A). Скрипт настройки: `scripts/setup-repos.sh` (в локальном хранилище сессии).
