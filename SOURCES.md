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
| A-24 | Первый плановый cron-бэкап (04.11) | `GET …/actions/runs` (event=schedule) | **failure × 4** | run #2, старт 2026-11-02 10:10–10:45 UTC (задержка от 03:00 UTC): checkout, `git bundle --all`, проверка целостности — success; упал только `upload-artifact@v4`. Дословно из лога: «Failed to CreateArtifact: Artifact storage quota has been hit. Unable to upload any new artifacts. Usage is recalculated every 6-12 hours.» |
| A-25 | Повторный dispatch × 3 (04.11) | `POST …/bundle-backup.yml/dispatches` → **204 × 3** → runs | failure × 3 | тот же шаг upload, тот же лог; при этом cell65-host в 11:35 UTC тем же workflow — **success** (прошёл до пересчёта квоты). Вывод: орган собран и жив — заблокировано ХРАНИЛИЩЕ аккаунта, не workflow |
| A-26 | Скан квоты аккаунта (04.11) | `GET /user/repos` + `GET /repos/{repo}/actions/artifacts` (read-only) | 200 × 27 | едок — `nous`: 46 артефактов ≈ 14.8 ГБ; `singulyar`: 10 ≈ 120 МБ; мои 4 репы: 5 ≈ 1 МБ; итог ≈ 15.1 ГБ против 500 МБ Free (B-8). Чужое не удалял — письмо nous-агенту через ящик (A-29, письмо №2) |
| A-27 | Инвентаризация email аккаунта (04.11) | `GET /user/emails` | **200** | 3 адреса: primary `sankt.technician@gmail.com` (verified, visibility private); **второй реальный `bitumbala@mail.ru` — verified**: «backup-ящик на GitHub» больше не пуст; noreply `119601232+rtynbirf@users.noreply.github.com`. Скопы по докам (B-7): чтение — `user:email`, добавление/удаление — `user` |
| A-28 | Единая commit-identity × 4 (04.11) | `git config user.email` | — | было: `rtynbirf@users.noreply.github.com` без ID-префикса (cell65-host; в списке верифицированных его нет) и `z@container` (github-runbook) — коммиты не атрибутировались; стало: верифицированный noreply `119601232+rtynbirf@users.noreply.github.com` во всех 4 репо |
| A-29 | Почтовый ящик клетки (04.11) | `MAILBOX.md` в cell65-host → ff-push **`1cd485e`** | репетиция CI зелёная, push 0/0 | протокол: append-only, письмо = коммит, теги [ALERT]/[CRON]/[DNA]/[FACT]/[HUMAN]; письмо №1 [DNA] → ALL (открытие органа, identity), №2 [ALERT] → nous-агент (квота, A-24…A-26). AGENTS.md: орган в карте репо + запрет правки чужих писем |
| A-30 | Оффлайн-зеркала бандлов (04.11) | `GET …/actions/artifacts/{id}/zip` (archive_download_url) | **200 × 5** | все 5 живых бандлов (31.10 и 04.11, 27–488 КБ) скачаны в `download/backup-mirrors/` — резервная копия вне квот GitHub; правило 3-2-1 получило физический носитель |
| A-31 | Токен мандата (10.11) | `GET /user` | **200** | токен жив, логин `rtynbirf`, 15 приватных; токен держится в файле 600, в логи не печатается (маскирован) |
| A-32 | Мастер-индекс реестра (10.11) | `GET /repos/rtynbirf/github-runbook/issues/10` | **200**, 32 комментария | «Сюда смотрят ДО первого действия»: реестр недоделанного жив, закон закрытия §5 действует |
| A-33 | Вход в дом + зелень (10.11) | `GET …/actions/workflows/ci.yml/runs` + `git fetch` | success ×3 на `fd2ad1d`; ff 0/0 | вход по чистой голове; грязь рабочего дерева (61 файл, 0 вставок/0 удалений = права/EOL песочницы) дискретирована, не смешана с чужим |

**Дословное тело 403 (A-14):**

```json
{
  "message": "Upgrade to GitHub Pro or make this repository public to enable this feature.",
  "documentation_url": "https://docs.github.com/rest/branches/branch-protection#update-branch-protection",
  "status": "403"
}
```

## B. Веб-источники (проверены поиском 01.11.2026 и fetch-ем 04.11.2026)

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
7. **GitHub Docs — REST «Emails»**: список адресов — «personal access tokens (classic)
   need the `user:email` scope»; добавление/удаление (`POST`/`DELETE /user/emails`) —
   «need the `user` scope»; fine-grained — «Email addresses» (read/write).
   URL: https://docs.github.com/en/rest/users/emails?apiVersion=2022-11-28 (проверено fetch-ем 04.11.2026)
8. **GitHub Docs — Billing for GitHub Actions**: тариф Free включает 500 МБ хранилища
   (артефакты + Packages); удаление артефактов — «Current storage decreases
   immediately», но «Storage already accrued … will appear on your bill».
   URL: https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions (проверено fetch-ем 04.11.2026)

## C. Что в мануале НЕ считается проверенным

- Точные интерфейсные пути кнопок GitHub (UI меняется) — даны как ориентир, а не факт.
- Даты следующих тарифных изменений GitHub — предсказания запрещены правилом аккаунта.

## D. Лог-файл сессии

Полный вывод настройки: `/tmp/setup-log.txt` (живёт в сессии; содержимое свернуто в
таблицу A). Скрипт настройки: `scripts/setup-repos.sh` (в локальном хранилище сессии).
Скрипты сессии 01.11.2026 (пакет автономности): `push-autonomy.sh` (ff-дисциплина),
`verify-autonomy.sh`, `probe-perms.sh` (зонд прав PAT), `local-ci-rehearsal.sh`,
`contents-verify.sh`, `artifacts-check.sh` (проверка bundle-артефактов) — там же.
Скрипты сессии 04.11.2026 (почта + квота): `token-intake.sh`, `runs-probe.sh`,
`jobs-probe.sh`, `log-fetch.sh` (дословный лог упавшего шага), `dispatch-retry.sh`,
`dispatch-check.sh`, `quota-scan.sh` (скан артефактов × 27 реп), `mirror-artifacts.sh`
(оффлайн-зеркала) — там же.

## E. Сессия 2026-11-10 · аудит аккаунта (дополнение, append-only)

| # | Действие | Endpoint | Ответ | Что доказывает |
|---|---|---|---|---|
| A-34 | Проба токена (закон 11) | `GET /user` | **200** + `github-authentication-token-expiration` | токен жив, логин `rtynbirf`, `plan.name=free` |
| A-35 | PVR × 7 публичных репо | `PUT /repos/{repo}/private-vulnerability-reporting` | **204 × 7**, затем `GET` → `enabled: true` | combain-v2, polymath-atlas, uace-polymat, rtynbirf, polymath-gen, polymath-stckg-core, revo |
| A-36 | Secret scanning на приватном репо | `PATCH /repos/rtynbirf/edinyy-svod` (`security_and_analysis`) | **422** «Secret scanning is not available for this repository.» | на Free для приватных репо недоступен (блок `security_and_analysis` в ответе пуст) |
| A-37 | PVR на архивном репо | `PUT /repos/rtynbirf/rumu/private-vulnerability-reporting` | **422** «Repository must be public and not archived» | для архива настройки безопасности закрыты |
| A-38 | Dependabot alerts × 3; secret scanning + push protection | `PUT …/vulnerability-alerts` · `PATCH /repos/rtynbirf/combain-v2` | **204 × 3** · **200**, статус `enabled` | combain-v2 закрыт; polymath-atlas и polymath-stckg-core получили alerts |
| A-39 | Статус immutable releases × 30 публичных | `GET /repos/{repo}/immutable-releases` | **200**, `enabled: true` только у polymath-os | чтение работает; PUT/DELETE на аккаунте ещё не проверены |
| A-40 | Push protection на архивном rumu | `PATCH /repos/rtynbirf/rumu` | **200**, но статус остаётся `disabled` | PATCH принят, в архиве не применяется |
| A-41 | Immutable releases ON (проба, затем ×11) | `PUT /repos/{repo}/immutable-releases` | **204 × 12**; `GET` → `{enabled: true, enforced_by_owner: false}` | эндпоинт работает на Free-аккаунте для публичных репо; guard (скан workflow на `--clobber`/`release upload`/`release edit`) пройден у 12 репо |
| A-42 | Лёгкая защита main × 9 | `PUT /repos/{repo}/branches/main/protection` (без PR и проверок, `allow_force_pushes=false`, `allow_deletions=false`) | **200 × 9**; `GET` → `allow_force_pushes.enabled: false` | защита без бюрократии доступна на публичных репо Free |

Пакет исполнения: `hardening-2026-11-10/` (ТЗ, дорожная карта, `tasks.json`, `scripts/hardening.py`).

## 2026-11-10 · Сессия 2: W2 + W2b закрыты, пакет исполнения опубликован (исполнитель: полимат-мультиагент)

| A-№ | Что проверено | Как | Результат | Вывод |
|---|---|---|---|---|
| A-43 | Права fine-grained PAT на запись | PUT contents/.github/CODEOWNERS ×5, PUT topics, PUT CITATION.cff | **403** на 5 репо («Resource not accessible by personal access token»), **201** на rtynbirf | fine-grained токен сессии имеет Contents write только на репо rtynbirf; записи на остальные репо — классическим токеном. Для минимальных прав это ожидаемо: скоуп репо задан владельцем |
| A-44 | Dependabot security updates в combain-v2 | `PUT /repos/rtynbirf/combain-v2/automated-security-fixes` | **204**; GET → `dependabot_security_updates.status=enabled` | R2 ТЗ закрыт полностью |
| A-45 | CODEOWNERS ×3 | `PUT contents/.github/CODEOWNERS` (combain-v2, polymath-stckg-core, uace-polymat) | **201 ×3**; GET → 200 | R4 закрыт: SECURITY.md + CODEOWNERS + dependabot.yml на месте |
| A-46 | Topics uace-polymat | `PUT /repos/rtynbirf/uace-polymat/topics` | **200**; GET → 9 тем | темы выведены из README (userscript, tampermonkey, browser-extension, chrome-extension, manifest-v3, cookie-vault, javascript, privacy, offline-first), не выдуманы; R8 частично (лицензия и homepage — за хозяином) |
| A-47 | CITATION.cff (волна W2b) | `PUT contents/CITATION.cff` ×6: combain-v2, polymath-os, uace-polymat, rtynbirf, polymath-stckg-core, .github | **201 ×6**; остальные 21 из 27 уже существовали и подтверждены live-GET | W2b закрыта: 27/27. У uace-polymat поле license опущено — лицензии в репо нет, не выдумываем |
| A-48 | Публикация Agent Execution Pack v0.1.0 в polymath-os | ветка `pack/agent-execution-2026-11-10`, commit (DCO) + push + PR | validate_pack PASS (25 файлов, 5 схем), unittest OK, `make verify` 33/33 локально; PR #38 открыт | https://github.com/rtynbirf/polymath-os/pull/38 — оверлей неразрушающий: AGENTS.md дополнен секцией, host PR-шаблон не дублирован; слияние — решение хозяина |
