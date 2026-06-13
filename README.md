# 67 Counter

Create a YouTube "67" supercut from captions using a small desktop app.

## Install

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e .
```

The package installs:

- `youtube-transcript-api` for timestamped transcript snippets.
- `yt-dlp` for downloading source video sections.
- `imageio-ffmpeg` for a bundled FFmpeg executable.

## Use The App

Download `67-counter-v1.0.0-windows-x64.exe` from the GitHub release, then
double-click it.

For development, launch the app from source:

```powershell
.\.venv\Scripts\python.exe -m sixseven_counter.ui
```

The app lets you paste a YouTube URL, scan captions, check or uncheck matches,
render the selected clips, and open the output folder.

Output is written to `runs/<video_id>/`:

- `67_supercut.mp4`
- `matches.json`
- `matches.csv`
- `selection.json` after review

If there are no selected matches, the app writes manifests and skips MP4
rendering.

## Matching Rules

Confirmed matches:

- `67`
- `6 7`
- `six seven`
- `six-seven`
- `sixty seven`

Possible matches:

- standalone `six`
- standalone `6`
- standalone `seven`
- standalone `7`

Transcript timings are approximate because YouTube captions are snippet-level,
not exact word-level timings.
