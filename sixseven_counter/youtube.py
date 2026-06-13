from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .errors import SixSevenError
from .models import TranscriptSnippet

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def parse_youtube_video_id(value: str) -> str:
    candidate = value.strip()
    if VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    if host == "youtu.be":
        return _validate_video_id(parsed.path.strip("/").split("/")[0])

    if host in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return _validate_video_id(query_id)

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
            return _validate_video_id(parts[1])

    raise SixSevenError(f"Could not parse a YouTube video ID from: {value}")


def fetch_video_metadata(url: str, cookies: Path | None = None) -> dict:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SixSevenError(
            "yt-dlp is not installed. Install the package with `python -m pip install -e .`."
        ) from exc

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp exposes several extractor-specific errors.
        raise SixSevenError(f"Could not read YouTube metadata: {exc}") from exc

    if info.get("_type") in {"playlist", "multi_video"}:
        raise SixSevenError("Playlists are not supported in v1. Pass a single video URL.")

    live_status = info.get("live_status")
    if info.get("is_live") or live_status in {"is_live", "is_upcoming", "post_live"}:
        raise SixSevenError("Active or not-yet-processed live streams are not supported.")

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
        "uploader": info.get("uploader"),
        "live_status": live_status,
        "was_live": info.get("was_live"),
    }


def fetch_english_transcript(video_id: str, lang: str = "en") -> list[TranscriptSnippet]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise SixSevenError(
            "youtube-transcript-api is not installed. Install the package with `python -m pip install -e .`."
        ) from exc

    try:
        api = YouTubeTranscriptApi()
        transcript_list = (
            api.list(video_id)
            if hasattr(api, "list")
            else YouTubeTranscriptApi.list_transcripts(video_id)
        )
        transcript = _find_preferred_transcript(transcript_list, lang)
        fetched = transcript.fetch()
        raw_items = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else fetched
    except Exception as exc:
        raise SixSevenError(
            f"Could not fetch an English transcript for {video_id}: {exc}"
        ) from exc

    snippets = [_snippet_from_item(item) for item in raw_items]
    if not snippets:
        raise SixSevenError(f"Transcript for {video_id} was empty.")
    return snippets


def _find_preferred_transcript(transcript_list: object, lang: str) -> object:
    try:
        return transcript_list.find_generated_transcript([lang])
    except Exception:
        pass

    try:
        return transcript_list.find_transcript([lang])
    except Exception as exc:
        raise SixSevenError(f"No transcript found for language `{lang}`.") from exc


def _snippet_from_item(item: object) -> TranscriptSnippet:
    if isinstance(item, dict):
        return TranscriptSnippet(
            text=str(item["text"]),
            start=float(item["start"]),
            duration=float(item["duration"]),
        )

    return TranscriptSnippet(
        text=str(getattr(item, "text")),
        start=float(getattr(item, "start")),
        duration=float(getattr(item, "duration")),
    )


def _validate_video_id(video_id: str) -> str:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise SixSevenError(f"Invalid YouTube video ID: {video_id}")
    return video_id

