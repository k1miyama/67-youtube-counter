from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .manifest import load_matches
from .models import Match
from .selection import choices_for_review, load_selection, save_selection, select_matches


@dataclass(frozen=True)
class MatchRow:
    match: Match
    include: bool

    @property
    def match_id(self) -> str:
        return self.match.id

    @property
    def kind(self) -> str:
        return self.match.kind

    @property
    def time_label(self) -> str:
        return f"{format_time(self.match.start)}-{format_time(self.match.end)}"

    @property
    def text(self) -> str:
        return squash(self.match.text, 60)

    @property
    def context(self) -> str:
        return squash(self.match.transcript_text, 140)

    @property
    def include_label(self) -> str:
        return "[x]" if self.include else "[ ]"


def build_match_rows(
    confirmed: list[Match],
    possible: list[Match],
    existing_choices: dict[str, bool] | None = None,
) -> list[MatchRow]:
    matches = [*confirmed, *possible]
    choices = choices_for_review(matches, existing_choices)
    return [MatchRow(match=match, include=choices[match.id]) for match in matches]


def load_match_rows(run_dir: Path) -> tuple[dict, list[MatchRow]]:
    payload, confirmed, possible = load_matches(run_dir)
    existing = try_load_selection(run_dir)
    return payload, build_match_rows(confirmed, possible, existing)


def try_load_selection(run_dir: Path) -> dict[str, bool] | None:
    try:
        return load_selection(run_dir)
    except Exception:
        return None


def toggle_row(rows: list[MatchRow], match_id: str) -> list[MatchRow]:
    return [
        replace(row, include=not row.include) if row.match_id == match_id else row
        for row in rows
    ]


def choices_from_rows(rows: list[MatchRow]) -> dict[str, bool]:
    return {row.match_id: row.include for row in rows}


def selected_matches_from_rows(rows: list[MatchRow]) -> list[Match]:
    return select_matches([row.match for row in rows], choices_from_rows(rows))


def can_render(rows: list[MatchRow]) -> bool:
    return any(row.include for row in rows)


def save_rows_selection(run_dir: Path, rows: list[MatchRow], *, completed: bool = True) -> Path:
    return save_selection(
        run_dir,
        [row.match for row in rows],
        choices_from_rows(rows),
        completed=completed,
    )


def format_time(seconds: float) -> str:
    total = int(seconds)
    millis = int(round((seconds - total) * 1000))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def squash(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
