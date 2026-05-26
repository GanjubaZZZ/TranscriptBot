"""
TranscriptBot — Google Drive + AssemblyAI + Google Sheets.

Запуск: python main.py
        python main.py --force
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import get_settings
from src.pipeline import Pipeline


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _check_credentials(settings) -> None:
    creds = settings.resolved_credentials_path()
    if not creds.is_file():
        print(
            "Помилка: не знайдено OAuth credentials.\n"
            "  - перейменуйте client_secret_*.json → credentials.json, або\n"
            "  - покладіть credentials.json у корінь проєкту."
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="TranscriptBot pipeline")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перетранскрибувати навіть якщо .txt вже є на Drive",
    )
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()
    _check_credentials(settings)

    missing = []
    if not settings.assemblyai_api_key:
        missing.append("ASSEMBLYAI_API_KEY")
    if not settings.work_audio_folder_id:
        missing.append("WORK_AUDIO_FOLDER_ID")
    if not settings.work_spreadsheet_id and not settings.source_spreadsheet_id:
        missing.append("WORK_SPREADSHEET_ID or SOURCE_SPREADSHEET_ID")

    if missing:
        print("Помилка: заповніть у файлі .env:", ", ".join(missing))
        print("Приклад: скопіюйте .env.example в .env")
        sys.exit(1)

    pipeline = Pipeline(settings, force_retranscribe=args.force)
    pipeline.run()


if __name__ == "__main__":
    main()
