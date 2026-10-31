# 05. API-шпаргалка: проверенные команды

Все команды исполнены live 01.11.2026 на аккаунте `rtynbirf` (журнал кодов — `SOURCES.md`).
Токен — только через файл заголовка `/tmp/.ghhdr` (`Authorization: Bearer …`, права 600).

## Состояние аккаунта и репо

```bash
# Кто я (проверка живости токена)                    → 200
curl -s -o /tmp/.user.json -w '%{http_code}\n' -H @/tmp/.ghhdr https://api.github.com/user

# Все репо аккаунта
curl -s -H @/tmp/.ghhdr "https://api.github.com/user/repos?per_page=100&sort=updated"

# Одно репо: private/default_branch/pushed_at
curl -s -H @/tmp/.ghhdr https://api.github.com/repos/ЛОГИН/РЕПО
```

## Создание приватного репо → 201

```bash
curl -s -X POST -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"имя","private":true,"description":"…",
       "has_issues":true,"has_wiki":false,"has_projects":false,"auto_init":false}'
```

## Все флаги настроек одним PATCH → 200

```bash
curl -s -X PATCH -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ЛОГИН/РЕПО \
  -d '{"private":true,
       "description":"…",
       "has_issues":true,"has_wiki":false,"has_projects":false,"has_discussions":false,
       "delete_branch_on_merge":true,
       "allow_squash_merge":true,"allow_merge_commit":true,"allow_rebase_merge":true,
       "allow_auto_merge":true,"allow_update_branch":true,
       "use_squash_pr_title_as_default":true,
       "squash_merge_commit_title":"PR_TITLE","squash_merge_commit_message":"PR_BODY",
       "merge_commit_title":"PR_TITLE","merge_commit_message":"PR_BODY",
       "web_commit_signoff_required":false}'
```

## Топики → 200

```bash
curl -s -X PUT -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ЛОГИН/РЕПО/topics \
  -d '{"names":["windows","history","research"]}'
```

## Безопасность → 204 на обе

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H @/tmp/.ghhdr \
  https://api.github.com/repos/ЛОГИН/РЕПО/vulnerability-alerts
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H @/tmp/.ghhdr \
  https://api.github.com/repos/ЛОГИН/РЕПО/automated-security-fixes
```

## Защита main (только Pro/public — см. `03`) → 200 или 403-гейт

```bash
curl -s -X PUT -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ЛОГИН/РЕПО/branches/main/protection \
  -d '{"required_status_checks":null,"enforce_admins":false,
       "required_pull_request_reviews":null,"restrictions":null,
       "allow_force_pushes":false,"allow_deletions":false,
       "required_conversation_resolution":false,"lock_branch":false}'
# 403 на Free+private — ожидаемо: "Upgrade to GitHub Pro or make this repository public"
```

## Пуш с кредами, которые не попадают в вывод

```bash
printf 'https://ЛОГИН:%s@github.com\n' "$(cat /tmp/.ghtoken)" > /tmp/.gitcreds
chmod 600 /tmp/.gitcreds
git config --global credential.helper "store --file=/tmp/.gitcreds"
git push -u origin main        # вывод git не содержит токен
```

## Уборка в конце сессии

```bash
rm -f /tmp/.ghtoken /tmp/.ghhdr /tmp/.gitcreds /tmp/.user.json /tmp/.repo-*.json \
      /tmp/.newrepo.json /tmp/.patch-*.json /tmp/.topics-*.json /tmp/.prot-*.json
```

## Коды ответов, которые встретились live

| Код | Что значил у нас |
|---|---|
| 200 | чтение/изменение настроек принято |
| 201 | репо создано |
| 204 | принято без тела (безопасность, security-fixes) |
| 403 | тарифный гейт (branch protection на Free+private) |
| 404 | репо нет — создаём (windows-encyclopedia до 201) |
