#!/usr/bin/env python3
"""
gui.py
======

A small desktop window for research_downloader.py, styled as a Claude-brand
palette mixed with a pixel-art / retro-terminal look. No command line needed:
enter a company name, pick how many years of each report to fetch, and click
Download.

The actual downloading runs in a SEPARATE PROCESS (this script re-invokes
itself with a hidden --cli-worker flag, which delegates straight to
research_downloader.main()), not a background thread in this process.
That's deliberate, not legacy: running the network code in a thread inside
a process that has a live Tk root reliably hangs (confirmed - a live tk.Tk()
in-process is enough to make a background thread's requests calls never
return, even though the exact same call is instant in a plain thread or a
separate process). Re-invoking "myself" as a worker also means this stays
fully compatible with a frozen single-file PyInstaller .exe, which can't
usefully be pointed at a second, separate .py file as a subprocess target.

Two Google Fonts (Press Start 2P, VT323 - both OFL licensed, bundled under
assets/fonts/) are loaded privately for this process only, so nothing is
installed system-wide.
"""

from __future__ import annotations

import os
import sys

# Worker dispatch happens before any GUI imports, so a --cli-worker
# subprocess starts fast and never touches Tkinter at all.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--cli-worker":
    import traceback

    import research_downloader as rd
    try:
        _worker_code = rd.main(sys.argv[2:])
    except SystemExit:
        raise
    except Exception:
        # Never let an exception escape: in a windowed exe it would pop up
        # a modal "Unhandled exception" dialog and leave the worker (and the
        # GUI waiting on it) stuck. Print it to the log instead.
        print("Something unexpected went wrong:\n" + traceback.format_exc(),
              flush=True)
        _worker_code = 1
    raise SystemExit(_worker_code)

import ctypes
import queue
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import filedialog, messagebox
from urllib.parse import quote

# --------------------------------------------------------------------------- #
# Paths. A frozen PyInstaller exe extracts bundled data (fonts, icon) to a
# temp folder at sys._MEIPASS - use that ONLY for read-only resources. The
# app's own persistent home (for the default output folder) is the folder
# the .exe actually sits in, via sys.executable, never the temp extraction
# path (which is deleted when the app closes).
# --------------------------------------------------------------------------- #
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR

DEFAULT_OUTPUT = os.path.join(APP_DIR, "output")
FONTS_DIR = os.path.join(RESOURCE_DIR, "assets", "fonts")
ICON_PATH = os.path.join(RESOURCE_DIR, "assets", "icon.ico")

# How to re-invoke this program as a --cli-worker: a frozen exe IS the
# interpreter (no separate script path to pass); a dev/source run needs its
# own file path passed explicitly so python.exe knows what to execute.
if getattr(sys, "frozen", False):
    _WORKER_BASE_CMD = [sys.executable]
else:
    _WORKER_BASE_CMD = [sys.executable, os.path.abspath(__file__)]

# --------------------------------------------------------------------------- #
# Palette - warm cream + terracotta, in the spirit of Claude's brand colors,
# rendered with hard pixel edges instead of soft/rounded UI chrome.
# --------------------------------------------------------------------------- #
BG = "#F4F1EA"
CARD = "#EDE8DA"
FIELD = "#FFFFFF"
INK = "#2E2B26"
MUTED = "#8A8578"
ACCENT = "#D97757"
ACCENT_DARK = "#B85C3F"
ACCENT_LIGHT = "#E7A186"
LOG_BG = "#262420"
LOG_FG = "#D9D4C5"
SUCCESS = "#4C9A5B"
DANGER = "#C1443C"

DISPLAY_FONT_FILE = "PressStart2P-Regular.ttf"
DISPLAY_FONT_NAME = "Press Start 2P"
MONO_FONT_FILE = "VT323-Regular.ttf"
MONO_FONT_NAME = "VT323"

DOC_TYPES = [
    ("AR", "Annual Reports", 10, True),
    ("DRHP", "DRHP (IPO prospectus)", None, False),
    ("CC", "Concall Transcripts", 4, True),
    ("IP", "Investor Presentations", 4, True),
    ("CR", "Credit Ratings", 2, True),
]


# --------------------------------------------------------------------------- #
# Private, no-install font loading (Windows GDI trick: AddFontResourceEx with
# FR_PRIVATE registers the font for this process only; it is auto-released
# when the process exits).
# --------------------------------------------------------------------------- #
def _load_private_fonts() -> None:
    if os.name != "nt":
        return
    FR_PRIVATE = 0x10
    for filename in (DISPLAY_FONT_FILE, MONO_FONT_FILE):
        path = os.path.join(FONTS_DIR, filename)
        if os.path.isfile(path):
            try:
                ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
            except Exception:  # noqa: BLE001 - fonts are a nice-to-have, never fatal
                pass


def _resolve_fonts(root: tk.Tk) -> tuple[str, str]:
    """Return (display_family, mono_family), falling back to system fonts
    if the bundled pixel fonts didn't register for some reason."""
    available = set(tkfont.families(root))
    display = DISPLAY_FONT_NAME if DISPLAY_FONT_NAME in available else "Consolas"
    mono = MONO_FONT_NAME if MONO_FONT_NAME in available else "Consolas"
    return display, mono


# --------------------------------------------------------------------------- #
# Small pixel-styled widgets built on plain tk (not ttk, so colors/borders are
# never overridden by the OS visual theme).
# --------------------------------------------------------------------------- #
class PixelButton(tk.Frame):
    def __init__(self, parent, text, command=None, font=None,
                 bg=ACCENT, hover=ACCENT_DARK, fg="#FFFDF8",
                 padx=10, pady=5, shadow=3, state="normal"):
        super().__init__(parent, bg=BG)
        self._shadow = tk.Frame(self, bg=INK)
        self._shadow.pack()
        self.btn = tk.Button(
            self._shadow, text=text, command=command, font=font,
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
            disabledforeground=MUTED, state=state,
        )
        self.btn.pack(padx=(0, shadow), pady=(0, shadow))
        self._bg, self._hover = bg, hover
        self.btn.bind("<Enter>", lambda e: self._set(hover))
        self.btn.bind("<Leave>", lambda e: self._set(bg))

    def _set(self, color: str) -> None:
        if str(self.btn["state"]) == "normal":
            self.btn.configure(bg=color)

    def configure_state(self, state: str) -> None:
        self.btn.configure(state=state, bg=self._bg if state == "normal" else CARD)


class PixelCheck(tk.Frame):
    def __init__(self, parent, variable: tk.BooleanVar, font):
        super().__init__(parent, bg=BG)
        self.var = variable
        self.box = tk.Label(self, text="", width=1, font=font, bg=FIELD, fg=INK,
                            relief="flat", highlightthickness=1,
                            highlightbackground=INK, cursor="hand2")
        self.box.pack()
        self.box.bind("<Button-1>", self.toggle)
        self._refresh()

    def toggle(self, _evt=None) -> None:
        self.var.set(not self.var.get())
        self._refresh()

    def _refresh(self) -> None:
        on = self.var.get()
        self.box.configure(text="X" if on else "", bg=ACCENT if on else FIELD,
                           fg="#FFFDF8" if on else INK)


class YearStepper(tk.Frame):
    def __init__(self, parent, initial: int, mono_font, minv=1, maxv=25):
        super().__init__(parent, bg=BG)
        self.var = tk.IntVar(value=initial)
        self.minv, self.maxv = minv, maxv

        minus = tk.Button(self, text="-", font=mono_font, width=1,
                          bg=CARD, fg=INK, activebackground=ACCENT_LIGHT,
                          relief="flat", bd=0, highlightthickness=1,
                          highlightbackground=INK, cursor="hand2",
                          command=self.dec)
        self.value_lbl = tk.Label(self, textvariable=self.var, width=2,
                                  font=mono_font, bg=FIELD, fg=INK,
                                  highlightthickness=1, highlightbackground=INK)
        plus = tk.Button(self, text="+", font=mono_font, width=1,
                         bg=CARD, fg=INK, activebackground=ACCENT_LIGHT,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=INK, cursor="hand2",
                         command=self.inc)
        minus.pack(side="left")
        self.value_lbl.pack(side="left", padx=2)
        plus.pack(side="left")

    def dec(self) -> None:
        self.var.set(max(self.minv, self.var.get() - 1))

    def inc(self) -> None:
        self.var.set(min(self.maxv, self.var.get() + 1))

    def get(self) -> int:
        return self.var.get()


def pixel_rule(parent, height=4, block=5):
    """A horizontal strip of alternating hard-edged squares as a section divider."""
    canvas = tk.Canvas(parent, height=height, bg=BG, highlightthickness=0)

    def redraw(event=None) -> None:
        canvas.delete("all")
        width = canvas.winfo_width()
        colors = (ACCENT, INK)
        x = 0
        i = 0
        while x < width:
            canvas.create_rectangle(x, 0, x + block, height,
                                    fill=colors[i % 2], outline="")
            x += block
            i += 1

    canvas.bind("<Configure>", redraw)
    return canvas


# --------------------------------------------------------------------------- #
# Main application
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        _load_private_fonts()

        self.title("Corporate Filings Downloader")
        self.configure(bg=BG)
        if os.path.isfile(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except tk.TclError:
                pass
        self.minsize(400, 600)
        self.geometry("420x640")

        self.display_family, self.mono_family = _resolve_fonts(self)
        self.f_title = (self.display_family, 10)
        self.f_section = (self.display_family, 7)
        self.f_button = (self.display_family, 8)
        self.f_button_sm = (self.display_family, 8)
        self.f_body = (self.mono_family, 13)
        self.f_small = (self.mono_family, 11)
        self.f_log = (self.mono_family, 12)

        self._running = False
        self.out_queue: queue.Queue[str] = queue.Queue()
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT)
        self.type_vars: dict[str, tk.BooleanVar] = {}
        self.steppers: dict[str, YearStepper] = {}

        self._build_ui()
        self.after(100, self._poll_output)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Header ---------------------------------------------------- #
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(anchor="w")
        tk.Label(title_row, text="FILINGS", font=self.f_title,
                bg=BG, fg=INK).pack(side="left")
        tk.Label(title_row, text=" DOWNLOADER", font=self.f_title,
                bg=BG, fg=ACCENT).pack(side="left")
        pixel_rule(outer).pack(fill="x", pady=(4, 6))

        # --- Company name ------------------------------------------------ #
        tk.Label(outer, text="COMPANY NAME", font=self.f_section,
                bg=BG, fg=INK, anchor="w").pack(anchor="w")
        self.company_entry = tk.Entry(outer, font=self.f_body, bg=FIELD, fg=INK,
                                      insertbackground=INK, relief="flat",
                                      highlightthickness=2,
                                      highlightbackground=INK,
                                      highlightcolor=ACCENT)
        self.company_entry.pack(fill="x", pady=(3, 6), ipady=2)
        self.company_entry.focus()

        # --- Document types + years ------------------------------------- #
        tk.Label(outer, text="WHAT TO DOWNLOAD", font=self.f_section,
                bg=BG, fg=INK, anchor="w").pack(anchor="w", pady=(0, 3))
        types_card = tk.Frame(outer, bg=CARD, highlightthickness=2,
                              highlightbackground=INK)
        types_card.pack(fill="x", pady=(0, 6))
        types_inner = tk.Frame(types_card, bg=CARD)
        types_inner.pack(fill="x", padx=6, pady=4)

        for code, label, default_years, has_years in DOC_TYPES:
            row = tk.Frame(types_inner, bg=CARD)
            row.pack(fill="x", pady=1)

            var = tk.BooleanVar(value=True)
            self.type_vars[code] = var
            PixelCheck(row, var, self.f_small).pack(side="left")

            tk.Label(row, text=label, font=self.f_small, bg=CARD, fg=INK,
                    anchor="w").pack(side="left", padx=(8, 0), fill="x", expand=True)

            if has_years:
                stepper = YearStepper(row, default_years, self.f_small)
                stepper.pack(side="left")
                self.steppers[code] = stepper
            else:
                tk.Label(row, text="one-time", font=self.f_small, bg=CARD,
                        fg=MUTED).pack(side="left")

        # --- Output folder ------------------------------------------------ #
        tk.Label(outer, text="SAVE TO FOLDER", font=self.f_section,
                bg=BG, fg=INK, anchor="w").pack(anchor="w")
        out_row = tk.Frame(outer, bg=BG)
        out_row.pack(fill="x", pady=(3, 2))
        self.output_entry = tk.Entry(out_row, textvariable=self.output_dir,
                                     font=self.f_small, bg=FIELD, fg=INK,
                                     insertbackground=INK, relief="flat",
                                     highlightthickness=2, highlightbackground=INK,
                                     highlightcolor=ACCENT)
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=2)
        PixelButton(out_row, "...", command=self._browse, font=self.f_button_sm,
                   bg=CARD, hover=ACCENT_LIGHT, fg=INK, padx=8, pady=3,
                   shadow=2).pack(side="left", padx=(6, 0))

        self.dry_run_var = tk.BooleanVar(value=False)
        preview_row = tk.Frame(outer, bg=BG)
        preview_row.pack(fill="x", pady=(4, 2))
        PixelCheck(preview_row, self.dry_run_var, self.f_small).pack(side="left")
        tk.Label(preview_row, text="Preview only (don't download)",
                font=self.f_small, bg=BG, fg=MUTED).pack(side="left", padx=(8, 0))

        pixel_rule(outer).pack(fill="x", pady=(6, 6))

        # --- Actions ------------------------------------------------------ #
        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x")
        self.download_btn = PixelButton(actions, "DOWNLOAD", command=self._start,
                                        font=self.f_button, padx=12, pady=5)
        self.download_btn.pack(side="left")
        self.open_folder_btn = PixelButton(actions, "OPEN FOLDER",
                                           command=self._open_folder,
                                           font=self.f_button_sm, bg=CARD,
                                           hover=ACCENT_LIGHT, fg=INK, padx=8,
                                           pady=5, shadow=2)
        self.open_folder_btn.pack(side="left", padx=(8, 0))
        self.open_folder_btn.configure_state("disabled")
        self.status_label = tk.Label(actions, text="", font=self.f_small,
                                     bg=BG, fg=MUTED)
        self.status_label.pack(side="left", padx=(10, 0))

        # --- Initiating coverage (search-only, no auto-scrape) ------------ #
        ic_frame = tk.Frame(outer, bg=BG)
        ic_frame.pack(fill="x", pady=(4, 0))
        tk.Label(ic_frame, text="Broker reports aren't auto-downloaded:",
                font=self.f_small, bg=BG, fg=MUTED, anchor="w").pack(anchor="w")
        PixelButton(ic_frame, "SEARCH INITIATING COVERAGE",
                   command=self._search_initiating_coverage, font=self.f_button_sm,
                   bg=CARD, hover=ACCENT_LIGHT, fg=INK, padx=8, pady=4,
                   shadow=2).pack(anchor="w")

        pixel_rule(outer).pack(fill="x", pady=(6, 6))

        # --- Log ------------------------------------------------------ #
        tk.Label(outer, text="PROGRESS", font=self.f_section, bg=BG, fg=INK,
                anchor="w").pack(anchor="w", pady=(0, 3))
        log_card = tk.Frame(outer, bg=LOG_BG, highlightthickness=2,
                            highlightbackground=INK)
        log_card.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_card, height=3, width=30, wrap="word",
                                state="disabled",
                                bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG,
                                font=self.f_log, relief="flat", padx=6, pady=4,
                                borderwidth=0)
        scroll = tk.Scrollbar(log_card, command=self.log_text.yview,
                              bg=CARD, troughcolor=LOG_BG, activebackground=ACCENT)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------- actions
    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir.get() or APP_DIR)
        if chosen:
            self.output_dir.set(chosen)

    def _open_folder(self) -> None:
        path = self.output_dir.get()
        if os.path.isdir(path):
            os.startfile(path)  # Windows

    def _search_initiating_coverage(self) -> None:
        company = self.company_entry.get().strip()
        if not company:
            messagebox.showwarning("Company name needed",
                                   "Type a company name first, then search.")
            return
        query = f'"{company}" "initiating coverage" filetype:pdf'
        webbrowser.open(f"https://www.bing.com/search?q={quote(query)}")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start(self) -> None:
        if self._running:
            return

        company = self.company_entry.get().strip()
        if not company:
            messagebox.showwarning("Company name needed", "Please type a company name first.")
            return

        selected_types = {code for code, *_ in DOC_TYPES if self.type_vars[code].get()}
        if not selected_types:
            messagebox.showwarning("Nothing selected", "Pick at least one document type.")
            return

        output_dir = self.output_dir.get().strip() or DEFAULT_OUTPUT
        os.makedirs(output_dir, exist_ok=True)

        cmd = list(_WORKER_BASE_CMD) + ["--cli-worker", company,
                                        "--types", ",".join(sorted(selected_types)),
                                        "--output", output_dir]
        for code, stepper in self.steppers.items():
            if code in selected_types:
                cmd += [f"--years-{code.lower()}", str(stepper.get())]
        if self.dry_run_var.get():
            cmd.append("--dry-run")

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._append_log(f"Starting download for '{company}'...\n\n")

        self._running = True
        self.download_btn.configure_state("disabled")
        self.open_folder_btn.configure_state("disabled")
        self.status_label.configure(text="Working...", fg=MUTED)

        threading.Thread(target=self._run_worker, args=(cmd,), daemon=True).start()

    def _run_worker(self, cmd: list[str]) -> None:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=APP_DIR, bufsize=1, creationflags=creationflags,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.out_queue.put(line)
            proc.wait()
            code = proc.returncode
        except Exception as exc:  # noqa: BLE001
            self.out_queue.put(f"\nCould not start the download: {exc}\n")
            code = 1
        self.out_queue.put(f"__DONE__{code}\n")

    def _poll_output(self) -> None:
        try:
            while True:
                line = self.out_queue.get_nowait()
                if line.startswith("__DONE__"):
                    code = line.strip().replace("__DONE__", "")
                    self._running = False
                    self.download_btn.configure_state("normal")
                    self.open_folder_btn.configure_state("normal")
                    if code == "0":
                        self.status_label.configure(text="Done", fg=SUCCESS)
                    else:
                        self.status_label.configure(text="Finished with issues - see log",
                                                    fg=DANGER)
                else:
                    self._append_log(line)
        except queue.Empty:
            pass
        self.after(100, self._poll_output)


if __name__ == "__main__":
    App().mainloop()
