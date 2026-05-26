"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DRIVE_FOLDER = "1iGdAYAcMd8WOSglo6Pt-h4CZEMpI3ElK"
DEFAULT_SPREADSHEET_ID = "1rN7DVN6OZks_-bI_aBC4zCpKCVNCK61Cg4P-2p7mJKI"

DEFAULT_SCORE_COLUMNS = (
    "Початок розмови, представлення|"
    "Чи дізнвся менеджер кузов атвомобіля|"
    "Чи дізнався менеджер рік автомобіля|"
    "Чи дізнався менеджр пробіг|"
    "Пропозиція про комплексну діагностику|"
    "Дізнався які роботи робилися раніше|"
    "Запис на сервіс, Дата|"
    "Завершення розмови прощання"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    source_audio_folder_id: str = DEFAULT_DRIVE_FOLDER
    work_audio_folder_id: str = DEFAULT_DRIVE_FOLDER
    source_spreadsheet_id: str = ""
    work_spreadsheet_id: str = DEFAULT_SPREADSHEET_ID

    sheet_name: str = "Sheet1"

    col_date: str = "Дата"
    col_appeal_type: str = "Тип звернення"
    col_phone: str = "Номер телефону"
    col_branch: str = "Філія"
    col_manager: str = "Менеджер"

    score_columns: str = Field(default=DEFAULT_SCORE_COLUMNS)

    col_top100_work: str = "Яка робота з топ 100"
    col_top100_compliance: str = (
        "Чи дотримувався всіх інструкцій з топ 100 робіт Да/Ні"
    )
    col_top100_missed: str = (
        "Яких рекоменадцій менеджер не дотримувався з топ 100 робіт"
    )
    col_result: str = "Результат"
    col_score: str = "Оцінка"
    col_parts: str = "Запчастини"
    col_comment: str = "Коментар"

    assemblyai_api_key: str = ""
    assemblyai_speech_models: str = "universal-3-pro,universal-2"
    assemblyai_language_code: str = "uk"
    assemblyai_speaker_labels: bool = True

    ollama_model: str = "gemma3:4b"
    ollama_url: str = "http://localhost:11434/v1/chat/completions"

    temp_dir: Path = Path("./data/temp")
    credentials_path: Path = Path("credentials.json")
    token_path: Path = Path("token.json")

    def score_column_list(self) -> list[str]:
        raw = self.score_columns.strip()
        if not raw:
            return []
        if "|" in raw:
            return [c.strip() for c in raw.split("|") if c.strip()]
        return [c.strip() for c in raw.split(",") if c.strip()]

    def speech_model_list(self) -> list[str]:
        return [m.strip() for m in self.assemblyai_speech_models.split(",") if m.strip()]

    def resolved_credentials_path(self) -> Path:
        if self.credentials_path.is_file():
            return self.credentials_path
        matches = sorted(Path(".").glob("client_secret_*.json"))
        if matches:
            return matches[0]
        return self.credentials_path


def get_settings() -> Settings:
    return Settings()
