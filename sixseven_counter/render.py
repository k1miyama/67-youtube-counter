from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import SixSevenError
from .models import ClipSegment

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess]
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class RenderResult:
    output_path: Path | None
    commands: list[list[str]]


def get_imageio_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise SixSevenError(
            "imageio-ffmpeg is not installed. Install the package with `python -m pip install -e .`."
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_supercut(
    *,
    url: str,
    segments: list[ClipSegment],
    run_dir: Path,
    quality: int,
    cookies: Path | None = None,
    keep_clips: bool = False,
    dry_run: bool = False,
    ffmpeg_path: str | None = None,
    runner: CommandRunner | None = None,
    progress: ProgressCallback | None = None,
) -> RenderResult:
    if not segments:
        return RenderResult(output_path=None, commands=[])

    ffmpeg = ffmpeg_path or get_imageio_ffmpeg_exe()
    command_runner = runner or _run_command
    clips_dir = run_dir / "clips"
    normalized_dir = run_dir / "normalized"
    clips_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    output_path = run_dir / "67_supercut.mp4"
    concat_file = run_dir / "concat.txt"
    commands: list[list[str]] = []
    normalized_clips: list[Path] = []

    for segment in segments:
        stem = f"clip_{segment.index:03d}"
        raw_template = clips_dir / f"{stem}.%(ext)s"
        _progress(
            progress,
            f"Downloading segment {segment.index}/{len(segments)} "
            f"({_format_seconds(segment.start)}-{_format_seconds(segment.end)})...",
        )
        ytdlp_command = build_ytdlp_command(
            url=url,
            segment=segment,
            output_template=raw_template,
            quality=quality,
            ffmpeg_path=ffmpeg,
            cookies=cookies,
        )
        commands.append(ytdlp_command)
        if not dry_run:
            if runner:
                command_runner(ytdlp_command)
            else:
                download_segment_with_ytdlp(
                    url=url,
                    segment=segment,
                    output_template=raw_template,
                    quality=quality,
                    ffmpeg_path=ffmpeg,
                    cookies=cookies,
                )

        raw_clip = clips_dir / f"{stem}.mp4" if dry_run else _find_downloaded_clip(clips_dir, stem)
        normalized_clip = normalized_dir / f"{stem}.mp4"
        _progress(progress, f"Normalizing segment {segment.index}/{len(segments)}...")
        normalize_command = build_normalize_command(raw_clip, normalized_clip, ffmpeg)
        commands.append(normalize_command)
        normalized_clips.append(normalized_clip)
        if not dry_run:
            command_runner(normalize_command)

    concat_file.write_text(_concat_file_text(normalized_clips), encoding="utf-8")
    concat_command = build_concat_command(concat_file, output_path, ffmpeg)
    commands.append(concat_command)
    _progress(progress, "Combining clips into 67_supercut.mp4...")
    if dry_run:
        (run_dir / "render_commands.txt").write_text(
            "\n".join(shlex.join(command) for command in commands) + "\n",
            encoding="utf-8",
        )
    else:
        command_runner(concat_command)
        if not keep_clips:
            shutil.rmtree(clips_dir, ignore_errors=True)
            shutil.rmtree(normalized_dir, ignore_errors=True)
            concat_file.unlink(missing_ok=True)

    _progress(progress, f"Render output: {output_path}")
    return RenderResult(output_path=output_path, commands=commands)


def build_ytdlp_command(
    *,
    url: str,
    segment: ClipSegment,
    output_template: Path,
    quality: int,
    ffmpeg_path: str,
    cookies: Path | None = None,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "yt_dlp",
        *build_ytdlp_args(
            url=url,
            segment=segment,
            output_template=output_template,
            quality=quality,
            ffmpeg_path=ffmpeg_path,
            cookies=cookies,
        ),
    ]


def build_ytdlp_args(
    *,
    url: str,
    segment: ClipSegment,
    output_template: Path,
    quality: int,
    ffmpeg_path: str,
    cookies: Path | None = None,
) -> list[str]:
    args = [
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--ffmpeg-location",
        ffmpeg_path,
        "--format",
        f"bv*[height<={quality}]+ba/b[height<={quality}]/best",
        "--merge-output-format",
        "mp4",
        "--recode-video",
        "mp4",
        "--force-keyframes-at-cuts",
        "--download-sections",
        f"*{_format_seconds(segment.start)}-{_format_seconds(segment.end)}",
        "--output",
        str(output_template),
    ]
    if cookies:
        args.extend(["--cookies", str(cookies)])
    args.append(url)
    return args


def download_segment_with_ytdlp(
    *,
    url: str,
    segment: ClipSegment,
    output_template: Path,
    quality: int,
    ffmpeg_path: str,
    cookies: Path | None = None,
) -> None:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
        from yt_dlp.utils import download_range_func
    except ImportError as exc:
        raise SixSevenError(
            "yt-dlp is not installed. Install dependencies or use the standalone release build."
        ) from exc

    ydl_opts = build_ytdlp_options(
        segment=segment,
        output_template=output_template,
        quality=quality,
        ffmpeg_path=ffmpeg_path,
        cookies=cookies,
        download_range_func=download_range_func,
    )
    ffmpeg_token = set_ytdlp_ffmpeg_location(ffmpeg_path, FFmpegPostProcessor)
    try:
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])
    except Exception as exc:
        raise SixSevenError(f"yt-dlp failed while downloading a clip: {exc}") from exc
    finally:
        reset_ytdlp_ffmpeg_location(ffmpeg_token, FFmpegPostProcessor)

    if result:
        raise SixSevenError(f"yt-dlp failed while downloading a clip: exit code {result}")


def set_ytdlp_ffmpeg_location(ffmpeg_path: str, ffmpeg_postprocessor_cls: object) -> object:
    return ffmpeg_postprocessor_cls._ffmpeg_location.set(ffmpeg_path)


def reset_ytdlp_ffmpeg_location(token: object, ffmpeg_postprocessor_cls: object) -> None:
    ffmpeg_postprocessor_cls._ffmpeg_location.reset(token)


def build_ytdlp_options(
    *,
    segment: ClipSegment,
    output_template: Path,
    quality: int,
    ffmpeg_path: str,
    cookies: Path | None = None,
    download_range_func: Callable | None = None,
) -> dict:
    if download_range_func is None:
        from yt_dlp.utils import download_range_func as yt_dlp_download_range_func

        download_range_func = yt_dlp_download_range_func

    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_path,
        "format": f"bv*[height<={quality}]+ba/b[height<={quality}]/best",
        "merge_output_format": "mp4",
        "final_ext": "mp4",
        "outtmpl": {"default": str(output_template)},
        "download_ranges": download_range_func(
            [],
            [[float(segment.start), float(segment.end)]],
        ),
        "force_keyframes_at_cuts": True,
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "FFmpegConcat", "only_multi_video": True, "when": "playlist"},
        ],
    }
    if cookies:
        opts["cookiefile"] = str(cookies)
    return opts


def build_normalize_command(input_path: Path, output_path: Path, ffmpeg_path: str) -> list[str]:
    return [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def build_concat_command(concat_file: Path, output_path: Path, ffmpeg_path: str) -> list[str]:
    return [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _run_command(command: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise SixSevenError(f"Command was not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise SixSevenError(f"Command failed with exit code {exc.returncode}: {shlex.join(command)}") from exc


def _find_downloaded_clip(directory: Path, stem: str) -> Path:
    candidates = sorted(
        path
        for path in directory.glob(f"{stem}.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    )
    if not candidates:
        raise SixSevenError(f"yt-dlp did not produce a clip named {stem}.*")

    mp4_candidates = [path for path in candidates if path.suffix.lower() == ".mp4"]
    return mp4_candidates[-1] if mp4_candidates else candidates[-1]


def _concat_file_text(paths: list[Path]) -> str:
    lines = []
    for path in paths:
        safe_path = path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{safe_path}'")
    return "\n".join(lines) + "\n"


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.3f}"


def _progress(progress: ProgressCallback | None, message: str) -> None:
    if progress:
        progress(message)
