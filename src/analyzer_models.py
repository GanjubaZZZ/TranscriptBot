"""Shared models for call analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CallAnalysis:
    appeal_type: str = ""
    phone: str = ""
    branch: str = ""
    manager: str = ""
    top100_work: str = ""
    top100_compliance: str = ""
    top100_missed: str = ""
    result: str = ""
    score: str = ""
    parts: str = ""
    comment: str = ""
    red_segments: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)

    @property
    def total_score(self) -> int:
        return sum(self.scores.values())
