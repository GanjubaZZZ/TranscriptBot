"""OAuth2 authentication for Google Drive and Sheets APIs."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Place OAuth client secrets at {credentials_path}. "
                "Download from Google Cloud Console → APIs → Credentials."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_drive_service(credentials_path: Path, token_path: Path):
    creds = get_credentials(credentials_path, token_path)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_sheets_service(credentials_path: Path, token_path: Path):
    creds = get_credentials(credentials_path, token_path)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
