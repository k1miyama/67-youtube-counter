from __future__ import annotations

import argparse
import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import render_reviewed_run, scan_video
from .errors import SixSevenError
from .ui_state import (
    MatchRow,
    can_render,
    load_match_rows,
    save_rows_selection,
    toggle_row,
)


class SixSevenApp:
    def __init__(self, root: tk.Tk, *, start_polling: bool = True) -> None:
        self.root = root
        self.root.title("67 Counter")
        self.root.geometry("1060x720")
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.rows: list[MatchRow] = []
        self.current_run_dir: Path | None = None
        self.job_running = False

        self.url_var = tk.StringVar()
        self.out_var = tk.StringVar(value="runs")
        self.padding_var = tk.StringVar(value="2")
        self.lang_var = tk.StringVar(value="en")
        self.quality_var = tk.StringVar(value="720")
        self.cookies_var = tk.StringVar()
        self.keep_clips_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        self._build_widgets()
        if start_polling:
            self.root.after(100, self._poll_queue)

    def _build_widgets(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="YouTube URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.url_var).grid(row=0, column=1, columnspan=5, sticky="ew", padx=(8, 0))

        ttk.Label(top, text="Output").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.out_var).grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=(8, 0))
        ttk.Button(top, text="Browse", command=self._choose_output).grid(row=1, column=2, sticky="w", pady=(8, 0))

        ttk.Label(top, text="Cookies").grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(8, 0))
        ttk.Entry(top, textvariable=self.cookies_var).grid(row=1, column=4, sticky="ew", padx=(8, 4), pady=(8, 0))
        ttk.Button(top, text="Browse", command=self._choose_cookies).grid(row=1, column=5, sticky="w", pady=(8, 0))

        settings = ttk.Frame(top)
        settings.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        ttk.Label(settings, text="Padding").pack(side="left")
        ttk.Spinbox(settings, from_=0, to=30, increment=0.5, width=6, textvariable=self.padding_var).pack(
            side="left", padx=(6, 16)
        )
        ttk.Label(settings, text="Language").pack(side="left")
        ttk.Entry(settings, width=6, textvariable=self.lang_var).pack(side="left", padx=(6, 16))
        ttk.Label(settings, text="Quality").pack(side="left")
        ttk.Spinbox(settings, from_=144, to=2160, increment=144, width=7, textvariable=self.quality_var).pack(
            side="left", padx=(6, 16)
        )
        ttk.Checkbutton(settings, text="Keep clips", variable=self.keep_clips_var).pack(side="left", padx=(0, 16))

        self.scan_button = ttk.Button(settings, text="Scan", command=self.start_scan)
        self.scan_button.pack(side="left")
        self.render_button = ttk.Button(settings, text="Render", command=self.start_render, state="disabled")
        self.render_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(settings, text="Open Folder", command=self.open_output_folder, state="disabled")
        self.open_button.pack(side="left", padx=(8, 0))

        main = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(main)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("include", "id", "kind", "time", "text", "context")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for key, label, width in [
            ("include", "Use", 54),
            ("id", "ID", 120),
            ("kind", "Kind", 90),
            ("time", "Time", 135),
            ("text", "Text", 120),
            ("context", "Transcript Context", 460),
        ]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="w", stretch=key == "context")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<ButtonRelease-1>", self._on_table_click)
        self.table.bind("<space>", self._toggle_selected_row)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)

        side = ttk.Frame(main)
        side.grid(row=0, column=1, sticky="nsew")
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        ttk.Label(side, textvariable=self.status_var).grid(row=0, column=0, sticky="ew")
        self.log = tk.Text(side, height=16, wrap="word", state="disabled")
        self.log.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def start_scan(self) -> None:
        if self.job_running:
            return
        try:
            args = self._scan_args()
        except SixSevenError as exc:
            self._show_error(str(exc))
            return
        self._set_running(True)
        self.rows = []
        self._populate_table()
        self._log("Starting scan...")
        self._run_worker(self._scan_worker, args)

    def start_render(self) -> None:
        if self.job_running or not self.current_run_dir:
            return
        if not can_render(self.rows):
            self._log("No matches selected. Nothing to render.")
            return
        try:
            save_rows_selection(self.current_run_dir, self.rows)
            args = self._render_args()
        except SixSevenError as exc:
            self._show_error(str(exc))
            return
        self._set_running(True)
        self._log("Starting render...")
        self._run_worker(self._render_worker, args)

    def open_output_folder(self) -> None:
        if not self.current_run_dir:
            return
        path = self.current_run_dir.resolve()
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _scan_worker(self, args: argparse.Namespace) -> None:
        result = scan_video(args, progress=self._worker_log)
        self.queue.put(("scan_done", result.run_dir))

    def _render_worker(self, args: argparse.Namespace) -> None:
        render_reviewed_run(args, progress=self._worker_log)
        self.queue.put(("render_done", args.run_dir))

    def _run_worker(self, target, args: argparse.Namespace) -> None:
        def wrapped() -> None:
            try:
                target(args)
            except Exception as exc:
                self.queue.put(("error", exc))

        threading.Thread(target=wrapped, daemon=True).start()

    def _poll_queue(self) -> None:
        while True:
            try:
                event, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if event == "log":
                self._log(str(payload))
            elif event == "scan_done":
                self.current_run_dir = Path(payload)
                self._load_rows(self.current_run_dir)
                self._set_running(False)
                self._log(f"Scan complete: {self.current_run_dir}")
            elif event == "render_done":
                self.current_run_dir = Path(payload)
                self._set_running(False)
                self._log("Render complete.")
            elif event == "error":
                self._set_running(False)
                self._show_error(str(payload))
        self.root.after(100, self._poll_queue)

    def _load_rows(self, run_dir: Path) -> None:
        _, self.rows = load_match_rows(run_dir)
        self._populate_table()

    def _populate_table(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        for row in self.rows:
            self.table.insert(
                "",
                "end",
                iid=row.match_id,
                values=(row.include_label, row.match_id, row.kind, row.time_label, row.text, row.context),
            )
        self._sync_buttons()

    def _on_table_click(self, event: tk.Event) -> None:
        if self.table.identify_column(event.x) == "#1":
            item = self.table.identify_row(event.y)
            if item:
                self._toggle_row(item)

    def _toggle_selected_row(self, _event: tk.Event) -> str:
        selected = self.table.selection()
        if selected:
            self._toggle_row(selected[0])
        return "break"

    def _toggle_row(self, match_id: str) -> None:
        self.rows = toggle_row(self.rows, match_id)
        self._populate_table()

    def _scan_args(self) -> argparse.Namespace:
        url = self.url_var.get().strip()
        if not url:
            raise SixSevenError("Paste a YouTube URL first.")
        return argparse.Namespace(
            command="scan",
            url=url,
            out=Path(self.out_var.get().strip() or "runs"),
            padding=self._float_value(self.padding_var.get(), "Padding"),
            lang=self.lang_var.get().strip() or "en",
            quality=self._int_value(self.quality_var.get(), "Quality"),
            cookies=self._optional_path(self.cookies_var.get()),
        )

    def _render_args(self) -> argparse.Namespace:
        if not self.current_run_dir:
            raise SixSevenError("Scan a video first.")
        return argparse.Namespace(
            command="render",
            run_dir=self.current_run_dir,
            quality=self._int_value(self.quality_var.get(), "Quality"),
            cookies=self._optional_path(self.cookies_var.get()),
            keep_clips=self.keep_clips_var.get(),
            dry_run=False,
        )

    def _optional_path(self, value: str) -> Path | None:
        stripped = value.strip()
        return Path(stripped) if stripped else None

    def _float_value(self, value: str, label: str) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise SixSevenError(f"{label} must be a number.") from exc

    def _int_value(self, value: str, label: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise SixSevenError(f"{label} must be a whole number.") from exc

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.out_var.get() or ".")
        if selected:
            self.out_var.set(selected)

    def _choose_cookies(self) -> None:
        selected = filedialog.askopenfilename(title="Select cookies.txt")
        if selected:
            self.cookies_var.set(selected)

    def _set_running(self, running: bool) -> None:
        self.job_running = running
        state = "disabled" if running else "normal"
        self.scan_button.configure(state=state)
        self.open_button.configure(state="disabled" if running or not self.current_run_dir else "normal")
        self._sync_buttons()
        self.status_var.set("Working..." if running else "Ready")

    def _sync_buttons(self) -> None:
        render_state = "normal" if self.current_run_dir and can_render(self.rows) and not self.job_running else "disabled"
        self.render_button.configure(state=render_state)
        open_state = "normal" if self.current_run_dir and not self.job_running else "disabled"
        self.open_button.configure(state=open_state)

    def _worker_log(self, message: str) -> None:
        self.queue.put(("log", message))

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _show_error(self, message: str) -> None:
        self._log("Error: " + message)
        messagebox.showerror("67 Counter", message)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m sixseven_counter.ui",
        description="Launch the standalone 67 Counter desktop UI.",
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    root = tk.Tk()
    SixSevenApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
