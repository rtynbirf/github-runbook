# 01. Создание репозитория

## Через сайт (путь по кнопкам)

1. Правый верхний угол: **+** → **New repository**.
2. **Repository name**: латиница, дефисы, без пробелов. Имя — это контракт: по нему
   ты и агенты найдёте дело через год. `windows-full-report` — хорошо; `repo1` — нет.
3. **Description** сразу заполни — одно человеческое предложение. Оно попадает в поиск,
   в список репо и в голову тому, кто откроет аккаунт через полгода.
4. **Visibility**: личное дело — **Private**. Публичным репо можно сделать позже
   одной командой; обратно (публичное → приватное) — тоже, но форки уже разошлись.
5. **Add a README file** — если начинаешь с нуля; если пушишь готовый локальный репо —
   НЕ ставь (иначе придётся решать конфликт несвязанных историй).
6. **Create repository**.

## Через API (проверено live: HTTP 201)

Токен в заголовке из файла, в командной строке его нет:

```bash
code=$(curl -s -o ответ.json -w '%{http_code}' -X POST \
  -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"windows-encyclopedia","private":true,
       "description":"одно человеческое предложение",
       "has_issues":true,"has_wiki":false,"has_projects":false,"auto_init":false}')
echo "HTTP $code"   # 201 = создан, private=true подтверждён
```

Флаги в теле соответствуют решениям из `02`: issues включены, wiki/projects выключены,
`auto_init` выключен для пуша готовой истории.

## Подключение локального репо и первый пуш

```bash
cd мой-репо
git init -b main                          # если ещё не репо
git remote add origin https://github.com/ВАШ_ЛОГИН/мой-репо.git
git push -u origin main                   # первый пуш, -u запоминает ветку
```

Креды: файл-хранилище с правами 600 в `/tmp`, живёт только в рамках сессии
(см. `04-bezopasnost.md`).

## Проверка после создания

```bash
curl -s -H @/tmp/.ghhdr https://api.github.com/repos/ЛОГИН/мой-репо | \
  python3 -c "import json,sys;d=json.load(sys.stdin);print(d['private'],d['default_branch'])"
# True main  — то, что нужно
```

**Проверено live (01.11.2026):** создание `windows-encyclopedia` — 201;
контрольный GET — `private=True, default=main`.
