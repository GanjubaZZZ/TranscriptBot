# Безпека TranscriptBot

## Секрети (ніколи не комітити)

| Файл | Зміст |
|------|--------|
| `.env` | `ASSEMBLYAI_API_KEY` |
| `credentials.json` / `client_secret_*.json` | OAuth client secret Google |
| `token.json` | Токен доступу Google після авторизації |

Усі ці шляхи в `.gitignore`.

## Рекомендації

1. **Ротуйте ключі**, якщо вони потрапили в чат, скріншот або публічний репозиторій.
2. **OAuth**: тип клієнта **Desktop app**; не використовуйте service account без зміни коду.
3. **AssemblyAI**: ключ лише в `.env`; у LLM Gateway заголовок `Authorization` — **без** префікса `Bearer`.
4. **Доступ до таблиці та папки Drive**: Google-акаунт, яким ви авторизуєтесь у браузері, має мати права Editor.
5. Перед `git push` перевірте: `git status` не показує `.env`, `token.json`, `client_secret_*.json`.

## Перейменування OAuth-файлу (опційно)

Можна залишити `client_secret_....json` — код знайде його автоматично. Для порядку:

```text
client_secret_....json  →  credentials.json
```
