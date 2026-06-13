from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ClipSegment, Match
from .errors import SixSevenError


def write_manifests(
    run_dir: Path,
    *,
    video_id: str,
    source_url: str,
    metadata: dict[str, Any],
    confirmed: list[Match],
    possible: list[Match],
    segments: list[ClipSegment],
    options: dict[str, Any],
) -> tuple[Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "matches.json"
    csv_path = run_dir / "matches.csv"

    payload = {
        "video_id": video_id,
        "source_url": source_url,
        "metadata": metadata,
        "options": options,
        "counts": {
            "confirmed": len(confirmed),
            "possible": len(possible),
            "segments": len(segments),
        },
        "confirmed_matches": [_match_dict(match) for match in confirmed],
        "possible_matches": [_match_dict(match) for match in possible],
        "segments": [_segment_dict(segment) for segment in segments],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fieldnames = [
        "id",
        "kind",
        "pattern",
        "text",
        "transcript_text",
        "start",
        "end",
        "clip_start",
        "clip_end",
        "snippet_start_index",
        "snippet_end_index",
        "token_start_index",
        "token_end_index",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for match in [*confirmed, *possible]:
            writer.writerow({field: _match_dict(match).get(field) for field in fieldnames})

    return json_path, csv_path


def load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "matches.json"
    if not path.exists():
        raise SixSevenError(f"Could not find {path}. Run `sixseven scan` first.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SixSevenError(f"Could not parse {path}: {exc}") from exc


def load_matches(run_dir: Path) -> tuple[dict[str, Any], list[Match], list[Match]]:
    payload = load_manifest(run_dir)
    confirmed = [_match_from_dict(item) for item in payload.get("confirmed_matches", [])]
    possible = [_match_from_dict(item) for item in payload.get("possible_matches", [])]
    return payload, confirmed, possible


def _match_dict(match: Match) -> dict[str, Any]:
    return asdict(match)


def _segment_dict(segment: ClipSegment) -> dict[str, Any]:
    return asdict(segment)


def _match_from_dict(item: dict[str, Any]) -> Match:
    return Match(
        id=str(item["id"]),
        kind=str(item["kind"]),
        pattern=str(item["pattern"]),
        text=str(item["text"]),
        transcript_text=str(item["transcript_text"]),
        start=float(item["start"]),
        end=float(item["end"]),
        token_start_index=int(item["token_start_index"]),
        token_end_index=int(item["token_end_index"]),
        snippet_start_index=int(item["snippet_start_index"]),
        snippet_end_index=int(item["snippet_end_index"]),
        clip_start=_optional_float(item.get("clip_start")),
        clip_end=_optional_float(item.get("clip_end")),
    )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
