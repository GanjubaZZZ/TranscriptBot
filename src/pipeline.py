"""Main processing pipeline: Google Drive + AssemblyAI + Sheets."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from config import Settings
from src.analyzer import CallAnalyzer
from src.assemblyai_transcriber import AssemblyAITranscriber
from src.drive_client import DriveClient
from src.google_auth import build_drive_service, build_sheets_service
from src.sheets_client import ColumnMap, SheetsClient

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    formats = (
        "%d.%m.%Y",
        "%d.%m.%y",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _date_from_filename(name: str) -> datetime | None:
    match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", name)
    if match:
        y, m, d = match.groups()
        try:
            return datetime(int(y), int(m), int(d))
        except ValueError:
            pass
    match = re.search(r"(\d{2})[._](\d{2})[._](\d{4})", name)
    if match:
        d, m, y = match.groups()
        try:
            return datetime(int(y), int(m), int(d))
        except ValueError:
            pass
    return None


def _match_audio_to_row(
    audio: dict, rows_with_date: list, col_date: str
) -> int | None:
    audio_date = _date_from_filename(audio["name"])
    if audio_date:
        for sheet_row in rows_with_date:
            row_date = _parse_date(sheet_row.values.get(col_date, ""))
            if row_date and row_date.date() == audio_date.date():
                return sheet_row.row_index
    return None


class Pipeline:
    def __init__(self, settings: Settings, *, force_retranscribe: bool = False):
        self._settings = settings
        self._force = force_retranscribe
        settings.temp_dir.mkdir(parents=True, exist_ok=True)

        creds_path = settings.resolved_credentials_path()
        drive_svc = build_drive_service(creds_path, settings.token_path)
        sheets_svc = build_sheets_service(creds_path, settings.token_path)

        self._drive = DriveClient(drive_svc)
        spreadsheet_id = settings.work_spreadsheet_id or settings.source_spreadsheet_id
        self._sheets = SheetsClient(sheets_svc, spreadsheet_id, settings.sheet_name)

        if not settings.assemblyai_api_key:
            raise ValueError("Set ASSEMBLYAI_API_KEY in .env")

        self._transcriber = AssemblyAITranscriber(
            api_key=settings.assemblyai_api_key,
            speech_models=settings.speech_model_list(),
            language_code=settings.assemblyai_language_code,
            speaker_labels=settings.assemblyai_speaker_labels,
        )
        self._analyzer = CallAnalyzer(
            api_key=settings.assemblyai_api_key,
            model=settings.assemblyai_llm_model,
            score_columns=settings.score_column_list(),
            gateway_url=settings.assemblyai_llm_gateway_url,
        )

    def ensure_work_spreadsheet(self) -> str:
        if self._settings.work_spreadsheet_id:
            return self._settings.work_spreadsheet_id

        if not self._settings.source_spreadsheet_id:
            raise ValueError("Set WORK_SPREADSHEET_ID or SOURCE_SPREADSHEET_ID in .env")

        new_id = self._drive.copy_spreadsheet(
            self._settings.source_spreadsheet_id,
            self._settings.work_audio_folder_id,
            "TranscriptBot — копія таблиці",
        )
        logger.info("Copied spreadsheet → %s (add to .env as WORK_SPREADSHEET_ID)", new_id)
        self._settings.work_spreadsheet_id = new_id
        creds_path = self._settings.resolved_credentials_path()
        self._sheets = SheetsClient(
            build_sheets_service(creds_path, self._settings.token_path),
            new_id,
            self._settings.sheet_name,
        )
        return new_id

    def run(self) -> None:
        s = self._settings
        if not s.work_audio_folder_id:
            raise ValueError("Set WORK_AUDIO_FOLDER_ID in .env")

        self.ensure_work_spreadsheet()

        audio_files = self._drive.sync_audio_from_source(
            s.source_audio_folder_id, s.work_audio_folder_id
        )
        logger.info("Audio files in work folder: %d", len(audio_files))

        col_map, all_rows = self._sheets.read_header_and_rows()
        rows_with_date = [
            r for r in all_rows if _parse_date(r.values.get(s.col_date, ""))
        ]
        logger.info("Rows with date to process: %d", len(rows_with_date))

        for audio in audio_files:
            self._process_audio(audio, col_map, rows_with_date)

        logger.info("Pipeline finished.")

    def _process_audio(
        self, audio: dict, col_map: ColumnMap, rows_with_date: list
    ) -> None:
        s = self._settings
        folder_id = s.work_audio_folder_id
        name = audio["name"]
        logger.info("Processing: %s", name)

        transcript = self._get_or_create_transcript(audio, folder_id)
        if not transcript:
            logger.warning("Empty transcript for %s, skipping sheet update", name)
            return

        row_index = _match_audio_to_row(audio, rows_with_date, s.col_date)
        if row_index is None and rows_with_date:
            for sheet_row in rows_with_date:
                if not sheet_row.values.get(s.col_comment, "").strip():
                    row_index = sheet_row.row_index
                    break
        if row_index is None:
            logger.warning("No matching row for %s", name)
            return

        self._update_sheet_row(row_index, col_map, transcript, name)

    def _get_or_create_transcript(self, audio: dict, folder_id: str) -> str:
        if not self._force:
            existing = self._drive.find_transcript(folder_id, audio["name"])
            if existing:
                logger.info("Using existing transcript: %s", existing["name"])
                return self._drive.read_text_file(existing["id"])

        local_audio = self._settings.temp_dir / audio["name"]
        self._drive.download_file(audio["id"], local_audio)
        logger.info("Transcribing %s via AssemblyAI ...", audio["name"])
        try:
            transcript = self._transcriber.transcribe_file(local_audio)
        finally:
            local_audio.unlink(missing_ok=True)

        txt_name = self._drive.get_transcript_filename(audio["name"])
        existing_id = None
        if self._force:
            existing = self._drive.find_transcript(folder_id, audio["name"])
            if existing:
                existing_id = existing["id"]
        self._drive.upload_text_file(
            folder_id, txt_name, transcript, existing_id=existing_id
        )
        return transcript

    def _update_sheet_row(
        self, row_index: int, col_map: ColumnMap, transcript: str, audio_name: str
    ) -> None:
        s = self._settings
        analysis = self._analyzer.analyze(transcript, audio_name)
        fields: dict = {
            s.col_appeal_type: analysis.appeal_type,
            s.col_phone: analysis.phone,
            s.col_branch: analysis.branch,
            s.col_manager: analysis.manager,
            s.col_top100_work: analysis.top100_work,
            s.col_top100_compliance: analysis.top100_compliance,
            s.col_top100_missed: analysis.top100_missed,
            s.col_result: analysis.result,
            s.col_score: analysis.score,
            s.col_parts: analysis.parts,
        }
        for score_col, score_val in analysis.scores.items():
            fields[score_col] = score_val

        self._sheets.update_row_fields(row_index, col_map, fields)

        comment_idx = col_map.index(s.col_comment)
        if comment_idx is not None:
            self._sheets.set_comment_with_red_highlights(
                row_index,
                comment_idx,
                analysis.comment,
                analysis.red_segments,
            )

        logger.info("Updated row %s for %s", row_index, audio_name)
