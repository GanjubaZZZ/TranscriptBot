"""Call analysis via local Ollama LLM — automotive service checklist."""

from __future__ import annotations

import json
import re

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.analyzer_models import CallAnalysis

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"


class CallAnalyzer:
    _DATE_COLUMN = "Запис на сервіс, Дата"

    def __init__(
        self,
        model: str,
        score_columns: list[str],
        base_url: str = OLLAMA_URL,
    ):
        self._model = model
        self._base_url = base_url
        self._score_columns = score_columns

    @retry(wait=wait_exponential(min=3, max=30), stop=stop_after_attempt(3))
    def analyze(self, transcript: str, audio_filename: str) -> CallAnalysis:
        prompt = self._build_prompt(transcript, audio_filename)
        response = requests.post(
            self._base_url,
            headers={"Content-Type": "application/json"},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"] or "{}"
        data = self._parse_json_response(raw)
        return self._parse_analysis(data)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Ти експерт з контролю якості телефонних розмов менеджерів автосервісу. "
            "Твоя задача — проаналізувати транскрипцію дзвінка та повернути структурований результат.\n\n"
            "ВАЖЛИВІ ПРАВИЛА:\n"
            "1. Відповідай ТІЛЬКИ одним валідним JSON-об'єктом.\n"
            "2. НЕ додавай текст до або після JSON.\n"
            "3. НЕ огортай відповідь у ```json``` або інші маркери.\n"
            "4. Всі строкові значення пиши українською мовою.\n"
            "5. Для числових полів scores використовуй ТІЛЬКИ цілі числа 0 або 1.\n"
            "6. Якщо інформація відсутня у розмові — пиши порожній рядок \"\".\n"
            "7. Поле red_segments має містити ТОЧНІ цитати з поля comment."
        )

    def _build_prompt(self, transcript: str, audio_filename: str) -> str:
        numeric_cols = [c for c in self._score_columns if c != self._DATE_COLUMN]
        criteria_lines = []
        for c in numeric_cols:
            criteria_lines.append(f"  - \"{c}\": 1 (виконано) або 0 (не виконано)")
        criteria_block = "\n".join(criteria_lines)

        score_keys = ", ".join(f'"{c}": 0' for c in numeric_cols)

        date_field = ""
        date_rules = ""
        if self._DATE_COLUMN in self._score_columns:
            date_field = f',\n    "{self._DATE_COLUMN}": "Запис відсутній"'
            date_rules = (
                f'\n\nПОЛЕ "{self._DATE_COLUMN}":\n'
                f"- Якщо клієнт записався на сервіс — вкажи дату у форматі ДД.ММ.РРРР\n"
                f"- Якщо дата не названа але запис є — напиши \"Так\"\n"
                f"- Якщо запису НЕ було — напиши \"Запис відсутній\"\n"
                f"- НЕ пиши числа 0 або 1 для цього поля"
            )

        return f"""Проаналізуй транскрипцію телефонного дзвінка в автосервіс.

Файл: {audio_filename}

ТРАНСКРИПЦІЯ:
---
{transcript[:8000]}
---

Поверни ОДИН JSON-об'єкт з такою структурою (заповни кожне поле на основі розмови):

{{
  "appeal_type": "запис на сервіс",
  "phone": "",
  "branch": "",
  "manager": "",
  "scores": {{
    {score_keys}{date_field}
  }},
  "top100_work": "",
  "top100_compliance": "Так",
  "top100_missed": "немає",
  "result": "запис",
  "parts": "",
  "comment": "Коментар про якість розмови",
  "red_segments": []
}}

ІНСТРУКЦІЇ ДЛЯ КОЖНОГО ПОЛЯ:

appeal_type: Один з варіантів — "запис на сервіс", "консультація", "скарга", "інше"

phone: Номер телефону клієнта якщо згадується у розмові, інакше ""

branch: Назва філії якщо згадується, інакше ""

manager: Ім'я менеджера якщо представився, інакше ""

scores: Оцінка менеджера по критеріях (ТІЛЬКИ 0 або 1):
{criteria_block}
{date_rules}

top100_compliance: "Так" або "Ні" — чи дотримувався менеджер стандартів обслуговування

top100_missed: Що саме менеджер не виконав зі стандартів. Якщо все ОК — "немає"

result: Результат дзвінка — одне слово/фраза: "запис", "відмова", "передзвон", "консультація", "інше"

parts: Запчастини які обговорювались, або ""

comment: Розгорнутий коментар українською (2-4 речення) про якість обслуговування. Обов'язково зазнач проблемні моменти якщо вони є.

red_segments: Масив рядків — ТОЧНІ цитати з поля comment де описані проблеми (менеджер погано відповідає, некоректна поведінка, порушення стандартів). Якщо проблем немає — порожній масив []."""

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        brace_start = text.find("{")
        if brace_start > 0:
            text = text[brace_start:]
        brace_end = text.rfind("}")
        if brace_end != -1:
            text = text[: brace_end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(r",\s*([}\]])", r"\1", text)
            return json.loads(text)

    def _parse_analysis(self, data: dict) -> CallAnalysis:
        scores: dict[str, str] = {}
        raw_scores = data.get("scores") or {}
        for col in self._score_columns:
            val = raw_scores.get(col, "0")
            if col == self._DATE_COLUMN:
                scores[col] = str(val) if val else "Запис відсутній"
            else:
                try:
                    scores[col] = "1" if int(val) == 1 else "0"
                except (TypeError, ValueError):
                    scores[col] = "0"

        red = data.get("red_segments") or []
        if isinstance(red, str):
            red = [red]

        return CallAnalysis(
            appeal_type=str(data.get("appeal_type") or ""),
            phone=str(data.get("phone") or ""),
            branch=str(data.get("branch") or ""),
            manager=str(data.get("manager") or ""),
            top100_work=str(data.get("top100_work") or ""),
            top100_compliance=str(data.get("top100_compliance") or ""),
            top100_missed=str(data.get("top100_missed") or ""),
            result=str(data.get("result") or ""),
            score=str(data.get("score") or ""),
            parts=str(data.get("parts") or ""),
            comment=str(data.get("comment") or ""),
            red_segments=[str(s) for s in red if s],
            scores=scores,
        )
