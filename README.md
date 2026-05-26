# TranscriptBot

Пайплайн для технічного завдання: аудіо дзвінків на **Google Drive** → транскрипція **AssemblyAI** → аналіз через **AssemblyAI LLM Gateway** → заповнення **Google Sheets** (оцінки 0/1, коментарі з червоним виділенням).

## Можливості

1. Читає `.mp3` з папки Google Drive.
2. Транскрибує через AssemblyAI (`universal-3-pro` / `universal-2`), зберігає `.txt` поруч на Drive.
3. Аналізує розмову (відповідність, тип робіт, оцінка менеджера, бали).
4. Заповнює [вашу таблицю](https://docs.google.com/spreadsheets/d/1rN7DVN6OZks_-bI_aBC4zCpKCVNCK61Cg4P-2p7mJKI/edit) — проблемні фрази в коментарі **червоним**.

## Вимоги

- Python 3.10+
- Google Cloud: **Drive API** + **Sheets API**, OAuth Desktop (`credentials.json` або `client_secret_*.json`)
- [AssemblyAI API key](https://www.assemblyai.com/dashboard/api-keys)

Детальніше про секрети: [SECURITY.md](SECURITY.md).

## Встановлення

```powershell
cd d:\coding\TranscriptBot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

У `.env` вкажіть **`ASSEMBLYAI_API_KEY`** (не комітьте файл).

## Перший запуск

```powershell
python main.py
```

1. Відкриється браузер — увійдіть Google-акаунтом з доступом до папки Drive і таблиці.
2. З’явиться `token.json` (локально, не в git).
3. Обробляться всі mp3 у папці; рядки таблиці з заповненою колонкою **Дата** отримають транскрипцію та оцінки.

Перетранскрибувати все:

```powershell
python main.py --force
```

## Конфігурація за замовчуванням

| Параметр | Значення |
|----------|----------|
| Папка Drive | `1iGdAYAcMd8WOSglo6Pt-h4CZEMpI3ElK` |
| Таблиця | `1rN7DVN6OZks_-bI_aBC4zCpKCVNCK61Cg4P-2p7mJKI` |

Назви колонок — як у вашій таблиці (`COL_*`, `SCORE_COLUMNS` через `|`). Повна транскрипція — у `.txt` на Drive; у таблицю йде аналіз і бали 0/1 по чеклісту.

## Структура

```
TranscriptBot/
├── main.py
├── config.py
├── src/
│   ├── assemblyai_transcriber.py
│   ├── analyzer.py              # LLM Gateway
│   ├── drive_client.py
│   ├── sheets_client.py
│   ├── google_auth.py
│   └── pipeline.py
├── credentials.json             # або client_secret_*.json
└── .env
```

## Усунення проблем

- **FileNotFoundError credentials** — покладіть OAuth JSON у корінь проєкту.
- **403 / access denied** — надайте Editor на папку Drive і таблицю тому ж акаунту, що в OAuth.
- **Порожні рядки в таблиці** — у рядках має бути дата в колонці `Дата`, або дата в імені файлу (`2024-05-20_call.mp3`).
