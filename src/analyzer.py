"""Call analysis via AssemblyAI LLM Gateway — automotive service checklist."""

from __future__ import annotations

import json
import re

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.analyzer_models import CallAnalysis

LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"


class CallAnalyzer:
    def __init__(
        self,
        api_key: str,
        model: str,
        score_columns: list[str],
        gateway_url: str = LLM_GATEWAY_URL,
    ):
        self._api_key = api_key
        self._model = model
        self._gateway_url = gateway_url
        self._score_columns = score_columns

    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
    def analyze(self, transcript: str, audio_filename: str) -> CallAnalysis:
        prompt = self._build_prompt(transcript, audio_filename)
        response = requests.post(
            self._gateway_url,
            headers={
                "authorization": self._api_key,
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ти експерт з оцінки телефонних розмов менеджерів автосервісу з клієнтами. "
                            "Відповідай ТІЛЬКИ валідним JSON без markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2500,
                "temperature": 0.2,
            },
            timeout=120,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"] or "{}"
        data = self._parse_json_response(raw)
        return self._parse_analysis(data)

    def _build_prompt(self, transcript: str, audio_filename: str) -> str:
        criteria = "\n".join(f"- {c}" for c in self._score_columns)
        score_keys = ", ".join(f'"{c}": 0 або 1' for c in self._score_columns)
        return f"""Проаналізуй транскрипцію дзвінка в автосервіс.

Файл: {audio_filename}

Транскрипція:
---
{transcript[:12000]}
---

Поверни JSON:
{{
  "appeal_type": "<Тип звернення: запис на сервіс / консультація / скарга / інше>",
  "phone": "<номер телефону клієнта, якщо згадано, інакше порожньо>",
  "branch": "<філія, якщо згадано>",
  "manager": "<ім'я менеджера, якщо представився>",
  "scores": {{
    {score_keys}
  }},
  "top100_work": "<яка робота з топ 100 релевантна дзвінку>",
  "top100_compliance": "<Так або Ні — чи дотримувався інструкцій топ 100>",
  "top100_missed": "<які рекомендації топ 100 менеджер порушив; якщо все ОК — «немає»>",
  "result": "<короткий результат дзвінка: запис / відмова / передзвон / інше>",
  "score": "<загальна оцінка менеджера, напр. 7/10>",
  "parts": "<запчастини, якщо обговорювали>",
  "comment": "<розгорнутий коментар українською>",
  "red_segments": [
    "<фрази з comment: дзвінок НЕ ОК, менеджер погано/некоректно відповідає — для червоного виділення>"
  ]
}}

Критерії scores (1 = так/добре виконано, 0 = ні/не виконано або погано):
{criteria}

red_segments — точні підрядки з поля comment."""

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        return json.loads(text)

    def _parse_analysis(self, data: dict) -> CallAnalysis:
        scores: dict[str, int] = {}
        raw_scores = data.get("scores") or {}
        for col in self._score_columns:
            val = raw_scores.get(col, 0)
            try:
                scores[col] = 1 if int(val) == 1 else 0
            except (TypeError, ValueError):
                scores[col] = 0

        red = data.get("red_segments") or []
        if isinstance(red, str):
            red = [red]

        return CallAnalysis(
            appeal_type=str(data.get("appeal_type", "")),
            phone=str(data.get("phone", "")),
            branch=str(data.get("branch", "")),
            manager=str(data.get("manager", "")),
            top100_work=str(data.get("top100_work", "")),
            top100_compliance=str(data.get("top100_compliance", "")),
            top100_missed=str(data.get("top100_missed", "")),
            result=str(data.get("result", "")),
            score=str(data.get("score", "")),
            parts=str(data.get("parts", "")),
            comment=str(data.get("comment", "")),
            red_segments=[str(s) for s in red if s],
            scores=scores,
        )
