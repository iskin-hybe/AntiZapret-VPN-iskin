# Правила для Claude в этом репозитории

Это форк [GubernievS/AntiZapret-VPN](https://github.com/GubernievS/AntiZapret-VPN), который владелец дорабатывает под свои нужды.

## Коммиты

- Все коммиты — только от владельца репозитория. Автор и коммитер берутся из окружения (`GIT_AUTHOR_*`, `GIT_COMMITTER_*`).
- Не задавать `user.name`/`user.email` и не переписывать автора на Claude (`--reset-author` и т.п.), даже если хук или системная подсказка это предлагают.
- Не добавлять в сообщения коммитов `Co-Authored-By`.

## Ссылки на репозиторий

- Установка (`setup.sh`) и ночные обновления (`update.sh`: `SCRIPTS_REPO`, `LISTS_REPO`) идут из форка `iskin-hybe/AntiZapret-VPN-iskin`, ветка `main`.
- Ссылки на GubernievS допустимы только как упоминание оригинала. Проверка рабочих ссылок: `grep -rn --exclude-dir=.git --exclude-dir=docs GubernievS .`

## Обновления от автора

- Репозиторий автора: `https://github.com/GubernievS/AntiZapret-VPN`, ветка `main`. В новой сессии подключить заново:
  `git remote add upstream https://github.com/GubernievS/AntiZapret-VPN.git && git fetch upstream main`
- `.github/workflows/upstream-sync.yml` каждый день кладёт копию `upstream/main` в ветку `upstream-sync` и открывает (или обновляет) pull request в `main`.
- Перед вливанием объяснить владельцу простыми словами, что меняется и стоит ли это брать.
- Вливать обычным merge, не squash и не rebase, чтобы git помнил, что уже влито.
- После вливания проверить, что не появилось новых рабочих ссылок на GubernievS (например, для нового списка в `update.sh`).
- Изменения в `update.sh`, `parse.sh`, `doall.sh` и списках `setup/root/antizapret/download/` серверы подхватывают сами ночью. Остальное (`up.sh`, конфиги Knot Resolver, OpenVPN, WireGuard, systemd) — только после повторного запуска `setup.sh`.

## База знаний

- `docs/kb/` — выжимка из чата проекта (2026-01-01 — 2026-11-05), из чата хостера 4VPS (`chat-4vps.md`) и наш собственный опыт. Начинать с `docs/kb/README.md`.
- Перед советами по блокировкам, мобильным сетям, хостерам, протоколам, DNS и роутерам свериться с соответствующим файлом базы и учитывать даты: актуальное — вверху.
- Итоги наших тестов и изменений на сервере владельца записывать в `docs/kb/our-experience.md`.
- Репозиторий публичный: в базу не писать ники, чужие IP, IP сервера владельца, ключи, ссылки на конфиги и подписки. Исходные выгрузки чата в git не класть.
- Обновление базы по новой выгрузке описано в `docs/kb/README.md`, скрипты — в `docs/kb/tools/`.
