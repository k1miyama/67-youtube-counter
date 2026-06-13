from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Any

from .errors import SixSevenError
from .manifest import load_matches
from .models import Match

SELECTION_FILENAME = "selection.json"


def default_choices(matches: list[Match]) -> dict[str, bool]:
    return {match.id: match.kind == "confirmed" for match in matches}


def load_selection(run_dir: Path) -> dict[str, bool]:
    path = run_dir / SELECTION_FILENAME
    if not path.exists():
        raise SixSevenError(f"Could not find {path}. Run `sixseven review {run_dir}` first.")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SixSevenError(f"Could not parse {path}: {exc}") from exc

    choices = payload.get("choices")
    if isinstance(choices, dict):
        return {str(match_id): bool(include) for match_id, include in choices.items()}

    selected_ids = payload.get("selected_ids")
    if isinstance(selected_ids, list):
        return {str(match_id): True for match_id in selected_ids}

    raise SixSevenError(f"{path} does not contain review choices.")


def save_selection(
    run_dir: Path,
    matches: list[Match],
    choices: dict[str, bool],
    *,
    completed: bool,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    normalized_choices = {match.id: bool(choices.get(match.id, False)) for match in matches}
    selected_ids = [match.id for match in matches if normalized_choices[match.id]]
    payload: dict[str, Any] = {
        "version": 1,
        "completed": completed,
        "selected_ids": selected_ids,
        "choices": normalized_choices,
        "counts": {
            "available": len(matches),
            "selected": len(selected_ids),
            "confirmed_selected": sum(
                1 for match in matches if match.kind == "confirmed" and normalized_choices[match.id]
            ),
            "possible_selected": sum(
                1 for match in matches if match.kind == "possible" and normalized_choices[match.id]
            ),
        },
    }
    path = run_dir / SELECTION_FILENAME
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def choices_for_review(matches: list[Match], existing: dict[str, bool] | None = None) -> dict[str, bool]:
    choices = default_choices(matches)
    if existing:
        for match_id, include in existing.items():
            if match_id in choices:
                choices[match_id] = include
    return choices


def select_matches(matches: list[Match], choices: dict[str, bool]) -> list[Match]:
    return [match for match in matches if choices.get(match.id, False)]


def review_run(
    run_dir: Path,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> Path:
    _, confirmed, possible = load_matches(run_dir)
    matches = [*confirmed, *possible]
    if not matches:
        return save_selection(run_dir, matches, {}, completed=True)

    existing = _load_optional_selection(run_dir)
    choices = choices_for_review(matches, existing)

    output_func(f"Reviewing {len(matches)} match(es). Enter keeps default, y includes, n excludes, q saves and exits.")
    completed = True
    for match in matches:
        default = choices[match.id]
        prompt = _prompt_for_match(match, default)
        while True:
            answer = input_func(prompt).strip().lower()
            if answer == "":
                break
            if answer in {"y", "yes"}:
                choices[match.id] = True
                break
            if answer in {"n", "no"}:
                choices[match.id] = False
                break
            if answer in {"q", "quit"}:
                completed = False
                path = save_selection(run_dir, matches, choices, completed=completed)
                output_func(f"Saved partial selection to {path}.")
                return path
            output_func("Use Enter, y, n, or q.")

    path = save_selection(run_dir, matches, choices, completed=completed)
    selected_count = len(select_matches(matches, choices))
    output_func(f"Saved {selected_count} selected match(es) to {path}.")
    return path


def _load_optional_selection(run_dir: Path) -> dict[str, bool] | None:
    path = run_dir / SELECTION_FILENAME
    if not path.exists():
        return None
    return load_selection(run_dir)


def _prompt_for_match(match: Match, default: bool) -> str:
    default_label = "Y" if default else "n"
    timestamp = f"{_format_time(match.start)}-{_format_time(match.end)}"
    context = _squash(match.transcript_text)
    text = _squash(match.text)
    return f"{match.id} {match.kind} [{default_label}] {timestamp} \"{text}\" | {context} > "


def _format_time(seconds: float) -> str:
    total = int(seconds)
    millis = int(round((seconds - total) * 1000))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def _squash(value: str, limit: int = 120) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
