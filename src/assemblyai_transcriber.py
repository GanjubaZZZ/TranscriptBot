"""Pre-recorded transcription via AssemblyAI SDK."""

from __future__ import annotations

from pathlib import Path

import assemblyai as aai
from assemblyai import TranscriptStatus


class AssemblyAITranscriber:
    def __init__(
        self,
        api_key: str,
        speech_models: list[str],
        language_code: str = "uk",
        speaker_labels: bool = True,
    ):
        aai.settings.api_key = api_key
        self._config = aai.TranscriptionConfig(
            speech_models=speech_models,
            speaker_labels=speaker_labels,
            language_code=language_code,
        )
        self._transcriber = aai.Transcriber(config=self._config)

    def transcribe_file(self, audio_path: Path) -> str:
        transcript = self._transcriber.transcribe(str(audio_path))
        if transcript.status == TranscriptStatus.error:
            raise RuntimeError(transcript.error or "AssemblyAI transcription failed")
        return self._format_transcript(transcript)

    @staticmethod
    def _format_transcript(transcript: aai.Transcript) -> str:
        if transcript.utterances:
            lines = []
            for utt in transcript.utterances:
                speaker = utt.speaker or "?"
                text = (utt.text or "").strip()
                if text:
                    lines.append(f"Speaker {speaker}: {text}")
            if lines:
                return "\n".join(lines)
        return (transcript.text or "").strip()
