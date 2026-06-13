from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import SixSevenError
from .manifest import load_matches, write_manifests
from .matcher import find_sixseven_matches
from .models import Match
from .render import render_supercut
from .selection import load_selection, review_run, select_matches
from .timing import assign_clip_bounds, merge_clip_segments
from .youtube import fetch_english_transcript, fetch_video_metadata, parse_youtube_video_id

COMMANDS = {"scan", "review", "render"}
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ScanResult:
    video_id: str
    run_dir: Path
    metadata: dict
    confirmed: list[Match]
    possible: list[Match]


def main(argv: list[str] | None = None) -> int:
    args = parse_cli_args(argv)

    try:
        dispatch(args)
    except SixSevenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sixseven",
        description="Find English 67 moments in a YouTube transcript and render a supercut.",
        epilog=(
            "Legacy one-shot usage still works: "
            "sixseven <youtube-url> --out runs --padding 2 --lang en --quality 720"
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan transcript and write matches.json/csv.")
    scan_parser.add_argument("url", help="YouTube video or finished stream archive URL.")
    add_scan_options(scan_parser)
    scan_parser.set_defaults(command="scan")

    review_parser = subparsers.add_parser("review", help="Interactively choose matches to render.")
    review_parser.add_argument("run_dir", type=Path, help="Run directory, such as runs/<video_id>.")
    review_parser.set_defaults(command="review")

    render_parser = subparsers.add_parser("render", help="Render selected matches from selection.json.")
    render_parser.add_argument("run_dir", type=Path, help="Run directory, such as runs/<video_id>.")
    render_parser.add_argument("--quality", default=720, type=int, help="Maximum downloaded video height.")
    render_parser.add_argument("--cookies", type=Path, help="yt-dlp cookies.txt path for download.")
    render_parser.add_argument(
        "--keep-clips", action="store_true", help="Keep intermediate downloaded and normalized clips."
    )
    render_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write render_commands.txt without downloading or rendering.",
    )
    render_parser.set_defaults(command="render")

    return parser


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sixseven",
        description="Find English 67 moments in a YouTube transcript and render a supercut.",
    )
    parser.add_argument("url", help="YouTube video or finished stream archive URL.")
    add_scan_options(parser)
    parser.add_argument(
        "--include-possible",
        action="store_true",
        help="Include lone six/seven matches in the rendered MP4.",
    )
    parser.add_argument(
        "--keep-clips",
        action="store_true",
        help="Keep intermediate downloaded and normalized clips.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write manifests and render_commands.txt without downloading or rendering.",
    )
    parser.set_defaults(command="legacy")
    return parser


def add_scan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default="runs", type=Path, help="Output root directory.")
    parser.add_argument("--padding", default=2.0, type=float, help="Seconds before/after each match.")
    parser.add_argument("--lang", default="en", help="Transcript language code. v1 expects English.")
    parser.add_argument("--quality", default=720, type=int, help="Maximum downloaded video height.")
    parser.add_argument("--cookies", type=Path, help="yt-dlp cookies.txt path for metadata.")


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args or raw_args[0] in {"-h", "--help"} or raw_args[0] in COMMANDS:
        return build_parser().parse_args(raw_args)
    return build_legacy_parser().parse_args(raw_args)


def dispatch(args: argparse.Namespace) -> None:
    if args.command == "scan":
        scan_video(args)
        return
    if args.command == "review":
        review_run(args.run_dir)
        return
    if args.command == "render":
        render_reviewed_run(args)
        return
    if args.command == "legacy":
        run_legacy(args)
        return
    raise SixSevenError(f"Unknown command: {args.command}")


def validate_scan_options(args: argparse.Namespace) -> None:
    if args.padding < 0:
        raise SixSevenError("--padding must be zero or greater.")
    if args.quality <= 0:
        raise SixSevenError("--quality must be a positive video height.")
    if args.lang != "en":
        raise SixSevenError("v1 is English-only. Use --lang en.")
    if args.cookies and not args.cookies.exists():
        raise SixSevenError(f"Cookies file does not exist: {args.cookies}")


def validate_render_options(args: argparse.Namespace) -> None:
    if args.quality <= 0:
        raise SixSevenError("--quality must be a positive video height.")
    if args.cookies and not args.cookies.exists():
        raise SixSevenError(f"Cookies file does not exist: {args.cookies}")


def scan_video(
    args: argparse.Namespace,
    *,
    include_possible_for_segments: bool = False,
    progress: ProgressCallback | None = None,
) -> ScanResult:
    validate_scan_options(args)
    output = progress or print
    video_id = parse_youtube_video_id(args.url)
    run_dir = args.out / video_id

    output(f"Reading metadata for {video_id}...")
    metadata = fetch_video_metadata(args.url, cookies=args.cookies)
    duration = _duration_as_float(metadata.get("duration"))

    output("Fetching English transcript...")
    snippets = fetch_english_transcript(video_id, lang=args.lang)

    output("Finding 67 moments...")
    match_result = find_sixseven_matches(snippets)
    confirmed = assign_clip_bounds(match_result.confirmed, args.padding, duration)
    possible = assign_clip_bounds(match_result.possible, args.padding, duration)
    render_matches = confirmed + (possible if include_possible_for_segments else [])
    segments = merge_clip_segments(render_matches)

    write_manifests(
        run_dir,
        video_id=video_id,
        source_url=args.url,
        metadata=metadata,
        confirmed=confirmed,
        possible=possible,
        segments=segments,
        options={
            "padding": args.padding,
            "lang": args.lang,
            "quality": args.quality,
            "include_possible": include_possible_for_segments,
        },
    )

    output(
        f"Found {len(confirmed)} confirmed match(es), "
        f"{len(possible)} possible match(es), {len(segments)} render segment(s)."
    )

    return ScanResult(
        video_id=video_id,
        run_dir=run_dir,
        metadata=metadata,
        confirmed=confirmed,
        possible=possible,
    )


def run_legacy(args: argparse.Namespace) -> None:
    result = scan_video(args, include_possible_for_segments=args.include_possible)
    render_matches = result.confirmed + (result.possible if args.include_possible else [])
    segments = merge_clip_segments(render_matches)

    if not segments:
        print(f"No MP4 rendered. Manifests are in {result.run_dir}.")
        return

    render_result = render_supercut(
        url=args.url,
        segments=segments,
        run_dir=result.run_dir,
        quality=args.quality,
        cookies=args.cookies,
        keep_clips=args.keep_clips,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"Dry run complete. Commands are in {result.run_dir / 'render_commands.txt'}.")
    else:
        print(f"Wrote {render_result.output_path}.")


def render_reviewed_run(
    args: argparse.Namespace,
    *,
    ffmpeg_path: str | None = None,
    progress: ProgressCallback | None = None,
) -> None:
    validate_render_options(args)
    output = progress or print
    payload, confirmed, possible = load_matches(args.run_dir)
    choices = load_selection(args.run_dir)
    matches = [*confirmed, *possible]
    selected = select_matches(matches, choices)
    segments = merge_clip_segments(selected)

    if not selected:
        output(f"No matches selected. No MP4 rendered. Selection is in {args.run_dir / 'selection.json'}.")
        return

    source_url = str(payload.get("source_url") or payload.get("metadata", {}).get("webpage_url") or "")
    if not source_url:
        raise SixSevenError("matches.json does not contain a source URL.")

    output(f"Rendering {len(selected)} selected match(es) as {len(segments)} segment(s)...")
    result = render_supercut(
        url=source_url,
        segments=segments,
        run_dir=args.run_dir,
        quality=args.quality,
        cookies=args.cookies,
        keep_clips=args.keep_clips,
        dry_run=args.dry_run,
        ffmpeg_path=ffmpeg_path,
        progress=progress,
    )

    if args.dry_run:
        output(f"Dry run complete. Commands are in {args.run_dir / 'render_commands.txt'}.")
    else:
        output(f"Wrote {result.output_path}.")


def _duration_as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
