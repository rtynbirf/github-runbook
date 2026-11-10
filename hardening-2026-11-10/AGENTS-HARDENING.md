# AGENTS-HARDENING — инструкция исполнителю пакета

Читать до первого действия: `AGENTS.md` репо, `ТЗ.md`, `ДОРОЖНАЯ-КАРТА.md`. Правила аккаунта сильнее этого файла.

## 1. Вход
1. Токен — только из env `GH_TOKEN`. Не печатать, не писать в файл, не коммитить.
2. `python3 scripts/hardening.py probe` — должен быть 200, логин rtynbirf, срок. Иначе честный ноль и стоп.

## 2. Правила
- Только репо rtynbirf. Чужих агентов и аккаунт-настройки не трогать.
- Задачи с `owner_decision: true` — только после явного решения хозяина (`--owner-ok`).
- Сначала dry-run (`apply T-xxxx`), потом `--yes`. После — `verify`.
- Force-push запрещён. Перед пушем `pull --rebase`.
- Мембранные файлы (README.md, AGENTS.md, llms.txt) без пломбы в polimat-hub не править.
- Новый факт GitHub — сначала live-тест, потом запись в SOURCES.md (только дописывать).
- Красный CI от твоего коммита — твой долг: довести до зелёного в ту же сессию.

## 3. Как отчитаться
Строка на задачу: `T-id · репо · код ответа · verify OK/НЕТ`. Если ответ не 2xx — дословное `message` из тела, без пересказа. Невыполненное не прятать: честный хвост в github-runbook#10.

## 4. Чего не делать
- Не включать immutable releases там, где `guard` вернул блок (сейчас: uace-polymat, domovoy-tweaker, commons).
- Не выдумывать темы, описания, лицензии, SHA экшенов.
- Не менять приватные репо через security_and_analysis: на Free вернёт 422.
- Не трогать rumu: архив.

## 5. dependabot.yml
Заменить `{{ECOSYSTEM}}` по файлам в корне репо: `requirements.txt` или `pyproject.toml` → pip; `package.json` → npm; `Cargo.toml` → cargo. Если экосистем нет (чистый HTML/Markdown) — удалить второй блок, оставить github-actions.
