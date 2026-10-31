# 04. Безопасность: Dependabot, secret scanning, гигиена токенов

## Dependabot alerts и автоматические исправления

**Что это.** GitHub сканирует манифесты зависимостей (package.json и т.п.) и сообщает
об известных уязвимостях; автоматические исправления присылают PR с обновлением.

**Проверено live (01.11.2026, приватные репо, Free):** обе команды приняли — `204`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H @/tmp/.ghhdr \
  https://api.github.com/repos/ЛОГИН/РЕПО/vulnerability-alerts        # 204
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H @/tmp/.ghhdr \
  https://api.github.com/repos/ЛОГИН/РЕПО/automated-security-fixes    # 204
```

## Secret scanning и push protection

**Что это.** GitHub распознаёт в коде API-ключи/токены известных провайдеров;
push protection блокирует пуш, содержащий живой секрет, до того, как он попадёт в историю.

**Верифицированное состояние (по changelog GitHub 2026 и докам):**

- **Публичные репо**: secret scanning и push protection — бесплатно и автоматически.
- **Приватные репо**: полный набор — часть платных планов (Advanced Security);
  защита от случайного пуша секретов частично работает и на личных приватных репо
  (паттерны партнёров), но рассчитывать на неё не стоит.

**Поэтому правило аккаунта: секреты не должны существовать в коде вообще.**

- Токен живёт в `/tmp`, права 600, **в командной строке его нет** — только ссылка на файл:

```bash
# WRONG: curl -H "Authorization: Bearer github_pat_ПРИМЕР" ...   ← токен в истории shell
# RIGHT:
curl -H @/tmp/.ghhdr https://api.github.com/user
```

## Гигиена токенов (fine-grained PAT)

1. **Fine-grained, не classic**: ограничен выбранными репо и конкретными правами.
   Лимит аккаунта — 50 таких токенов (доки GitHub).
2. **Минимум прав**: для работы «код+настройки» достаточно
   `Contents: RW` + `Administration: RW` + `Metadata: R` на нужных репо.
3. **Срок жизни**: ставь минимально разумный; умерший токен безопаснее вечного.
4. **Хранение в сессии**: файл 600 в `/tmp`, два вида:
   `/tmp/.ghtoken` (сам токен) и `/tmp/.ghhdr` (готовый заголовок). В выводе — никогда.
5. **Утилизация в конце сессии**:

```bash
rm -f /tmp/.ghtoken /tmp/.ghhdr /tmp/.gitcreds
```

6. **Если токен попал в вывод/историю** — не «подумать», а сразу:
   Settings → Developer settings → Fine-grained tokens → **Revoke**, выпустить новый.
   Пушить секрет в код нельзя даже в приватное репо: секрет в истории — это вечный секрет.

## Что настроено на аккаунте (итог live-сессии 01.11.2026)

| Мера | cell65-host | windows-full-report | windows-encyclopedia |
|---|---|---|---|
| private = true | ✅ (был публичным) | ✅ | ✅ (создан приватным) |
| Dependabot alerts (204) | ✅ | ✅ | ✅ |
| Automated security fixes (204) | ✅ | ✅ | ✅ |
| Branch protection | гейт Free-плана (403, см. `03`) | — « — | — « — |
