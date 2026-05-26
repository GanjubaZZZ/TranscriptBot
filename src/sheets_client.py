"""Google Sheets: read rows, write transcription and analysis with rich text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from googleapiclient.discovery import Resource


@dataclass
class SheetRow:
    row_index: int  # 1-based in spreadsheet
    values: dict[str, str]


@dataclass
class ColumnMap:
    headers: dict[str, int]  # header name -> 0-based column index

    def index(self, name: str) -> int | None:
        return self.headers.get(name)


class SheetsClient:
    def __init__(self, service: Resource, spreadsheet_id: str, sheet_name: str):
        self._service = service
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._sheet_id: int | None = None

    def _range(self, cell_range: str) -> str:
        return f"'{self._sheet_name}'!{cell_range}"

    def _col_letter(self, index: int) -> str:
        result = ""
        n = index + 1
        while n:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    def get_sheet_id(self) -> int:
        if self._sheet_id is not None:
            return self._sheet_id
        meta = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        for sheet in meta.get("sheets", []):
            props = sheet["properties"]
            if props["title"] == self._sheet_name:
                self._sheet_id = props["sheetId"]
                return self._sheet_id
        raise ValueError(f"Sheet '{self._sheet_name}' not found")

    def read_header_and_rows(self, header_row: int = 1) -> tuple[ColumnMap, list[SheetRow]]:
        result = (
            self._service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=self._range(f"A{header_row}:ZZ"),
            )
            .execute()
        )
        rows_data = result.get("values", [])
        if not rows_data:
            return ColumnMap({}), []

        headers = {h.strip(): i for i, h in enumerate(rows_data[0]) if h and str(h).strip()}
        col_map = ColumnMap(headers)

        data_rows: list[SheetRow] = []
        for offset, row_cells in enumerate(rows_data[1:], start=1):
            row_index = header_row + offset
            values: dict[str, str] = {}
            for header, col_idx in headers.items():
                if col_idx < len(row_cells):
                    values[header] = str(row_cells[col_idx]).strip()
                else:
                    values[header] = ""
            data_rows.append(SheetRow(row_index=row_index, values=values))
        return col_map, data_rows

    def update_cell(self, row: int, col_index: int, value: str | int | float) -> None:
        cell = f"{self._col_letter(col_index)}{row}"
        body = {"values": [[value]]}
        (
            self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=self._range(cell),
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )

    def update_row_fields(self, row: int, col_map: ColumnMap, fields: dict[str, Any]) -> None:
        for header, value in fields.items():
            idx = col_map.index(header)
            if idx is not None and value is not None and value != "":
                self.update_cell(row, idx, value)

    def set_comment_with_red_highlights(
        self,
        row: int,
        col_index: int,
        full_text: str,
        red_segments: list[str],
    ) -> None:
        """Write comment cell with red formatting for problematic phrases."""
        sheet_id = self.get_sheet_id()
        cell_a1 = f"{self._col_letter(col_index)}{row}"

        if not red_segments or not any(s in full_text for s in red_segments if s):
            self.update_cell(row, col_index, full_text)
            return

        runs = self._build_text_format_runs(full_text, red_segments)
        requests = [
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1,
                    },
                    "rows": [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {"stringValue": full_text},
                                    "textFormatRuns": runs,
                                }
                            ]
                        }
                    ],
                    "fields": "userEnteredValue,textFormatRuns",
                }
            }
        ]
        (
            self._service.spreadsheets()
            .batchUpdate(spreadsheetId=self._spreadsheet_id, body={"requests": requests})
            .execute()
        )
        _ = cell_a1  # kept for clarity in logs

    @staticmethod
    def _build_text_format_runs(full_text: str, red_segments: list[str]) -> list[dict]:
        """Mark segments in red; default format for the rest."""
        highlights: list[tuple[int, int]] = []
        for segment in red_segments:
            if not segment:
                continue
            start = 0
            while True:
                pos = full_text.find(segment, start)
                if pos == -1:
                    break
                highlights.append((pos, pos + len(segment)))
                start = pos + 1

        if not highlights:
            return [{"startIndex": 0, "format": {}}]

        highlights.sort()
        merged: list[tuple[int, int]] = []
        for start, end in highlights:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        runs: list[dict] = []
        cursor = 0
        for start, end in merged:
            if cursor < start:
                runs.append({"startIndex": cursor, "format": {}})
            runs.append(
                {
                    "startIndex": start,
                    "format": {"foregroundColor": {"red": 1.0, "green": 0.0, "blue": 0.0}},
                }
            )
            cursor = end
        if cursor < len(full_text):
            runs.append({"startIndex": cursor, "format": {}})
        if not runs:
            runs.append({"startIndex": 0, "format": {}})
        return runs

    def compute_total_score(self, row_values: dict[str, int], score_headers: list[str]) -> int:
        total = 0
        for h in score_headers:
            val = row_values.get(h, 0)
            try:
                total += int(val)
            except (TypeError, ValueError):
                pass
        return total
