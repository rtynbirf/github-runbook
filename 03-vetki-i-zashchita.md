# 03. Ветки и защита main: Free vs Pro — честно

## Дефолтная ветка

- Имя `main` (не `master`): локально `git init -b main`, на GitHub
  Settings → General → Default branch.
- Смена дефолта, если история пришла как `master`:
  `git branch -m main` → push → сменить на GitHub → удалить старую.

## Branch protection: что доступно на каком тарифе

**Проверено live 01.11.2026** — попытка включить защиту ветки `main` на приватном репо
тарифа Free через API вернула:

```json
{
  "message": "Upgrade to GitHub Pro or make this repository public to enable this feature.",
  "status": "403"
}
```

Это не проблема токена (тем же токеном репо создаются — 201, флаги ставятся — 200),
а тарифный гейт. Официальная документация подтверждает: защищённые ветки доступны
в приватных репозиториях на **GitHub Pro / Team / Enterprise**, на Free — только
в публичных.

### Значит, на Free для приватного репо:

1. **Не тратить время** на UI: галочки защиты просто не применятся.
2. Заменители защиты — дисциплина:
   - **Теги на каждом осмысленном состоянии** (`v1.0.0-mv3`, `v1.1.0`) — точка возврата;
   - **bundle-бэкапы** после крупных слияний (см. `06`);
   - **никаких force-push в main**: `git push --force` — запрещённое слово;
   - чужой агент пушит в main — это нормально: перед пушем `git fetch` +
     `--ff-only`-слияние, история только растёт.
3. Когда появится Pro — одна команда включает мягкую защиту:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT \
  -H @/tmp/.ghhdr -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ЛОГИН/РЕПО/branches/main/protection \
  -d '{"required_status_checks":null,"enforce_admins":false,
       "required_pull_request_reviews":null,"restrictions":null,
       "allow_force_pushes":false,"allow_deletions":false,
       "required_conversation_resolution":false,"lock_branch":false}'
# 200 = защищено: force-push и удаление запрещены, прямые пуши разрешены
```

Это «мягкая» защита: она НЕ мешает агентам пушить прямо в main (комфорт),
но НЕ даёт потерять историю force-push'ем или удалением ветки.

Нюанс с тарифов (по обсуждениям сообщества и докам): полная органайзерская сила
(«Restrict who can push», обязательные ревью по код-аунерам) на приватных репо
личного аккаунта ограничена — «restrict pushes» существует только у организаций
Team/Enterprise. Для одного человека это неважно.

## Правила слияния для многорукой работы (агенты)

1. Перед своим пушем: `git fetch origin` и `git rev-list --left-right --count main...origin/main`.
2. Если ты только позади (лево 0) — `git merge --ff-only origin/main` и работай дальше.
3. Если разошлись — merge, не rebase общих коммитов: чужой агент уже мог на них опереться.
4. Никогда не решай конфликт удалением ветки или force-push'ем.

**Проверено live (01.11.2026):** именно так поглотили 3 чужих коммита в `cell65-host` —
fast-forward без единого конфликта, история цела.
