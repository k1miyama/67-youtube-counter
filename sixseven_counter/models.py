from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TranscriptSnippet:
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class Token:
    value: str
    raw: str
    start: float
    end: float
    snippet_index: int
    token_index: int


@dataclass(frozen=True)
class Match:
    id: str
    kind: str
    pattern: str
    text: str
    transcript_text: str
    start: float
    end: float
    token_start_index: int
    token_end_index: int
    snippet_start_index: int
    snippet_end_index: int
    clip_start: Optional[float] = None
    clip_end: Optional[float] = None


@dataclass(frozen=True)
class MatchResult:
    confirmed: list[Match]
    possible: list[Match]


@dataclass(frozen=True)
class ClipSegment:
    index: int
    start: float
    end: float
    match_ids: list[str]

