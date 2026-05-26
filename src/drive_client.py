"""Google Drive: copy audio files and upload transcriptions."""

from __future__ import annotations

import io
from pathlib import Path

from googleapiclient.discovery import Resource
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}


class DriveClient:
    def __init__(self, service: Resource):
        self._service = service

    def list_files_in_folder(self, folder_id: str) -> list[dict]:
        query = f"'{folder_id}' in parents and trashed = false"
        files: list[dict] = []
        page_token = None
        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                    pageToken=page_token,
                    pageSize=200,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return files

    def list_audio_files(self, folder_id: str) -> list[dict]:
        return [
            f
            for f in self.list_files_in_folder(folder_id)
            if Path(f["name"]).suffix.lower() in AUDIO_EXTENSIONS
        ]

    def copy_file_to_folder(self, file_id: str, name: str, dest_folder_id: str) -> str:
        body = {"name": name, "parents": [dest_folder_id]}
        copied = (
            self._service.files()
            .copy(fileId=file_id, body=body, fields="id, name")
            .execute()
        )
        return copied["id"]

    def file_exists_in_folder(self, folder_id: str, name: str) -> str | None:
        for f in self.list_files_in_folder(folder_id):
            if f["name"] == name:
                return f["id"]
        return None

    def sync_audio_from_source(
        self, source_folder_id: str, work_folder_id: str
    ) -> list[dict]:
        """Copy new audio from source folder to work folder. Returns work-folder audio list."""
        if source_folder_id == work_folder_id:
            return self.list_audio_files(work_folder_id)

        source_files = self.list_audio_files(source_folder_id)
        for src in source_files:
            existing_id = self.file_exists_in_folder(work_folder_id, src["name"])
            if not existing_id:
                self.copy_file_to_folder(src["id"], src["name"], work_folder_id)
        return self.list_audio_files(work_folder_id)

    def download_file(self, file_id: str, dest_path: Path) -> Path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(fileId=file_id)
        with io.FileIO(str(dest_path), "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest_path

    def upload_text_file(
        self, folder_id: str, filename: str, content: str, existing_id: str | None = None
    ) -> str:
        tmp = Path("_upload_tmp.txt")
        tmp.write_text(content, encoding="utf-8")
        try:
            media = MediaFileUpload(str(tmp), mimetype="text/plain", resumable=True)
            if existing_id:
                updated = (
                    self._service.files()
                    .update(fileId=existing_id, media_body=media, fields="id")
                    .execute()
                )
                return updated["id"]

            body = {"name": filename, "parents": [folder_id], "mimeType": "text/plain"}
            created = (
                self._service.files()
                .create(body=body, media_body=media, fields="id")
                .execute()
            )
            return created["id"]
        finally:
            tmp.unlink(missing_ok=True)

    def get_transcript_filename(self, audio_name: str) -> str:
        return Path(audio_name).stem + ".txt"

    def find_transcript(self, folder_id: str, audio_name: str) -> dict | None:
        transcript_name = self.get_transcript_filename(audio_name)
        for f in self.list_files_in_folder(folder_id):
            if f["name"] == transcript_name:
                return f
        return None

    def read_text_file(self, file_id: str) -> str:
        path = Path("_tmp_read.txt")
        try:
            self.download_file(file_id, path)
            return path.read_text(encoding="utf-8")
        finally:
            if path.exists():
                path.unlink()

    def copy_spreadsheet(self, source_id: str, dest_folder_id: str, new_name: str) -> str:
        body = {
            "name": new_name,
            "parents": [dest_folder_id],
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        copied = (
            self._service.files()
            .copy(fileId=source_id, body=body, fields="id")
            .execute()
        )
        return copied["id"]
