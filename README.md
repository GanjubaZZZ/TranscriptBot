# TranscriptBot

Автоматизований бот для оцінки якості телефонних дзвінків менеджерів автосервісу.

**Принцип роботи:** аудіо дзвінків з **Google Drive** → транскрипція через **AssemblyAI** → аналіз через локальну LLM (**Ollama**) → заповнення **Google Sheets** (транскрипція, оцінки 0/1, коментарі з червоним виділенням проблемних місць).

## Як це працює

1. Бот зчитує всі `.mp3` файли з вказаної папки на Google Drive.
2. Кожен файл транскрибується через AssemblyAI (з розпізнаванням спікерів).
3. Файл транскрипції (`.txt`) зберігається поруч з аудіо на Drive.
4. Текст транскрипції аналізується локальною LLM (Ollama, модель `gemma3:4b`).
5. Результат записується у Google таблицю:
   - **Колонка A** — повний текст транскрипції дзвінка.
   - **Колонки скорингу** (початок розмови, кузов, рік, пробіг тощо) — оцінка 1 або 0.
   - **Колонка "Оцінка"** — 1 якщо результат дзвінка "запис", 0 — будь-який інший.
   - **Колонка "Коментар"** — розгорнутий коментар, проблемні місця виділені червоним.
6. Вже заповнені рядки не перезаписуються — нові дані додаються лише у порожні рядки.

## Вимоги

- **Python 3.10+**
- **Google Cloud Project** з увімкненими API:
  - Google Drive API
  - Google Sheets API
  - OAuth 2.0 Desktop credentials (`client_secret_*.json`)
- **[AssemblyAI API key](https://www.assemblyai.com/dashboard/api-keys)** — для транскрипції
- **[Ollama](https://ollama.com/)** — запущений локально з моделлю `gemma3:4b`

Детальніше про безпеку: [SECURITY.md](SECURITY.md).

## Встановлення та налаштування

### 1. Клонування та встановлення залежностей

```powershell
git clone https://github.com/GanjubaZZZ/TranscriptBot.git
cd TranscriptBot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Налаштування Google Cloud

1. Створіть проєкт у [Google Cloud Console](https://console.cloud.google.com/).
2. Увімкніть **Google Drive API** та **Google Sheets API**.
3. Створіть OAuth 2.0 Client ID (тип: Desktop App).
4. Скачайте JSON-файл credentials і покладіть у корінь проєкту як `client_secret_*.json`.

### 3. Налаштування Ollama

```powershell
# Встановіть Ollama з https://ollama.com/
# Завантажте модель:
ollama pull gemma3:4b
# Ollama повинна працювати на http://localhost:11434
```

### 4. Створення .env файлу

```powershell
copy .env.example .env
```

Відредагуйте `.env` та вкажіть:
- `ASSEMBLYAI_API_KEY` — ваш ключ AssemblyAI
- `SOURCE_AUDIO_FOLDER_ID` — ID папки з аудіо на Google Drive
- `WORK_SPREADSHEET_ID` — ID вашої Google таблиці
- `SHEET_NAME` — назва аркуша (наприклад `Аркуш1`)

**Не комітьте `.env` у git** — він вже у `.gitignore`.

## Запуск

```powershell
.venv\Scripts\activate
python main.py
```

При першому запуску відкриється браузер для авторизації Google-акаунту. Після цього збережеться `token.json` (локально, не потрапляє в git).

### Перетранскрибувати всі файли заново:

```powershell
python main.py --force
```

Без `--force` бот використовує вже існуючі `.txt` файли транскрипцій (не витрачає кредити AssemblyAI повторно).

## Конфігурація

| Параметр | Опис |
|----------|------|
| `SOURCE_AUDIO_FOLDER_ID` | ID папки Google Drive з аудіофайлами |
| `WORK_SPREADSHEET_ID` | ID Google таблиці для заповнення |
| `SHEET_NAME` | Назва аркуша в таблиці |
| `ASSEMBLYAI_API_KEY` | Ключ API AssemblyAI |
| `OLLAMA_MODEL` | Модель Ollama для аналізу (за замовчуванням `gemma3:4b`) |
| `OLLAMA_URL` | URL Ollama API (за замовчуванням `http://localhost:11434/v1/chat/completions`) |
| `SCORE_COLUMNS` | Критерії оцінки через `\|` як роздільник |

## Структура проєкту

```
TranscriptBot/
├── main.py                      # Точка входу
├── config.py                    # Конфігурація з .env
├── requirements.txt             # Залежності Python
├── .env.example                 # Шаблон змінних середовища
├── SECURITY.md                  # Правила безпеки
├── src/
│   ├── pipeline.py              # Головний пайплайн обробки
│   ├── assemblyai_transcriber.py # Транскрипція через AssemblyAI
│   ├── analyzer.py              # Аналіз дзвінків через Ollama
│   ├── analyzer_models.py       # Моделі даних аналізу
│   ├── drive_client.py          # Робота з Google Drive API
│   ├── sheets_client.py         # Робота з Google Sheets API
│   └── google_auth.py           # OAuth 2.0 авторизація
├── client_secret_*.json         # OAuth credentials (не в git)
├── token.json                   # Токен авторизації (не в git)
└── .env                         # Змінні середовища (не в git)
```

## Усунення проблем

- **FileNotFoundError credentials** — покладіть `client_secret_*.json` у корінь проєкту.
- **403 / access denied** — надайте доступ Editor на папку Drive і таблицю тому ж Google-акаунту, що використовується при OAuth авторизації.
- **Ollama не відповідає** — переконайтесь що Ollama запущена (`ollama serve`) і модель завантажена (`ollama list`).
- **Порожній результат аналізу** — перевірте що модель `gemma3:4b` працює: `ollama run gemma3:4b "test"`.
