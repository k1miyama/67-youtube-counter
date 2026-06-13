from __future__ import annotations

from dataclasses import replace

from .models import ClipSegment, Match


def assign_clip_bounds(
    matches: list[Match],
    padding: float,
    video_duration: float | None = None,
) -> list[Match]:
    bounded: list[Match] = []
    for match in matches:
        clip_start = max(0.0, match.start - padding)
        clip_end = match.end + padding
        if video_duration is not None:
            clip_end = min(video_duration, clip_end)
        if clip_end <= clip_start:
            clip_end = clip_start + 0.001
        bounded.append(replace(match, clip_start=clip_start, clip_end=clip_end))
    return bounded


def merge_clip_segments(matches: list[Match]) -> list[ClipSegment]:
    render_matches = sorted(
        (match for match in matches if match.clip_start is not None and match.clip_end is not None),
        key=lambda match: (match.clip_start, match.clip_end, match.id),
    )
    if not render_matches:
        return []

    merged: list[ClipSegment] = []
    current_start = float(render_matches[0].clip_start)
    current_end = float(render_matches[0].clip_end)
    current_ids = [render_matches[0].id]

    for match in render_matches[1:]:
        start = float(match.clip_start)
        end = float(match.clip_end)
        if start <= current_end:
            current_end = max(current_end, end)
            current_ids.append(match.id)
            continue

        merged.append(
            ClipSegment(
                index=len(merged) + 1,
                start=current_start,
                end=current_end,
                match_ids=current_ids,
            )
        )
        current_start = start
        current_end = end
        current_ids = [match.id]

    merged.append(
        ClipSegment(
            index=len(merged) + 1,
            start=current_start,
            end=current_end,
            match_ids=current_ids,
        )
    )
    return merged

