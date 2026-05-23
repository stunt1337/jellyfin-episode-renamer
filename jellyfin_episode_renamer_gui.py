#!/usr/bin/env python3
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from jellyfin_episode_renamer import (
    CONFIG_FILE,
    UNDO_LOG_FILE,
    RenameItem,
    build_episode_plans,
    build_movie_plans,
    build_multi_season_episode_plans,
    detect_season_folders,
    delete_stale_source_dirs,
    find_stale_source_dirs,
    count_changed,
    flatten_plan,
    read_config,
    rename_files,
    undo_from_log,
    validate_plan,
)
from media_detection import parse_movie_folder_name, parse_show_folder_name, looks_like_season_folder


DEFAULT_EXTENSIONS = ".mkv,.mp4,.avi,.mov,.m4v,.webm,.ts"
EXAMPLE_CONFIG_FILE = Path(__file__).with_name("settings.example.txt")
PROFILES_FILE = Path(__file__).with_name("profiles.json")
BaseTk = TkinterDnD.Tk if TkinterDnD is not None else tk.Tk

PRESET_PROFILES: dict[str, dict[str, object]] = {
    "Custom": {},
    "Jellyfin Movie": {
        "movie_mode": True,
        "show_mode": False,
        "include_sidecars": True,
        "flatten": True,
        "normalize_movie_nfo": True,
        "normalize_show_nfo": False,
        "rename_show_folder": False,
        "normalize_season_folder": False,
        "multi_season": False,
        "cleanup_stale_paths": False,
        "recursive": False,
        "episode_from_path": False,
    },
    "Jellyfin Show Root": {
        "movie_mode": False,
        "show_mode": True,
        "include_sidecars": True,
        "flatten": False,
        "normalize_movie_nfo": False,
        "normalize_show_nfo": True,
        "rename_show_folder": True,
        "normalize_season_folder": False,
        "multi_season": False,
        "cleanup_stale_paths": False,
    },
    "Jellyfin Season": {
        "movie_mode": False,
        "show_mode": True,
        "include_sidecars": True,
        "flatten": False,
        "normalize_movie_nfo": False,
        "normalize_show_nfo": True,
        "rename_show_folder": True,
        "normalize_season_folder": True,
        "multi_season": False,
        "cleanup_stale_paths": False,
        "episode_from_path": True,
    },
    "Loose Release Folder": {
        "movie_mode": False,
        "show_mode": False,
        "include_sidecars": True,
        "flatten": True,
        "normalize_movie_nfo": False,
        "normalize_show_nfo": False,
        "rename_show_folder": False,
        "normalize_season_folder": False,
        "multi_season": False,
        "cleanup_stale_paths": False,
        "recursive": True,
        "episode_from_path": True,
    },
}


def parse_extensions(value: str) -> set[str]:
    return {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in value.split(",")
        if ext.strip()
    }


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow: tk.Toplevel | None = None
        self.after_id: str | None = None
        self.widget.bind("<Enter>", self.schedule, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, event: tk.Event | None = None) -> None:
        self.unschedule()
        self.after_id = self.widget.after(350, self.show)

    def unschedule(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self) -> None:
        if self.tipwindow is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(background="#11151a")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#11151a",
            foreground="#f2f4f8",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=320,
        )
        label.pack()

    def hide(self, event: tk.Event | None = None) -> None:
        self.unschedule()
        if self.tipwindow is not None:
            self.tipwindow.destroy()
            self.tipwindow = None


class EpisodeRenamerApp(BaseTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Jellyfin Episode Renamer")
        self.geometry("1180x700")
        self.minsize(980, 560)

        self.plan: list[RenameItem] = []
        self._tooltips: list[Tooltip] = []

        self.folder_var = tk.StringVar()
        self.series_var = tk.StringVar()
        self.year_var = tk.StringVar()
        self.preview_kind_var = tk.StringVar()
        self.preview_target_folder_var = tk.StringVar()
        self.preview_current_path_var = tk.StringVar()
        self.preview_target_path_var = tk.StringVar()
        self.profile_name_var = tk.StringVar()
        self.preset_var = tk.StringVar(value="Custom")
        self.movie_mode_var = tk.BooleanVar(value=False)
        self.show_mode_var = tk.BooleanVar(value=True)
        self.season_var = tk.StringVar(value="1")
        self.start_episode_var = tk.StringVar(value="1")
        self.extensions_var = tk.StringVar(value=DEFAULT_EXTENSIONS)
        self.recursive_var = tk.BooleanVar(value=False)
        self.episode_from_path_var = tk.BooleanVar(value=False)
        self.include_sidecars_var = tk.BooleanVar(value=False)
        self.normalize_movie_nfo_var = tk.BooleanVar(value=False)
        self.normalize_show_nfo_var = tk.BooleanVar(value=False)
        self.rename_show_folder_var = tk.BooleanVar(value=False)
        self.normalize_season_folder_var = tk.BooleanVar(value=False)
        self.multi_season_var = tk.BooleanVar(value=False)
        self.cleanup_stale_paths_var = tk.BooleanVar(value=False)
        self.flatten_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Choose a folder and run Preview.")

        self._build_ui()
        self.ensure_settings_file()
        if CONFIG_FILE.exists():
            self.load_settings(show_errors=False)

    def show_scrollable_error(self, title: str, message: str) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("720x320")
        dialog.minsize(560, 240)
        dialog.configure(background=self.cget("background"))

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="word",
            height=12,
            borderwidth=0,
            highlightthickness=0,
            background="#1f232a",
            foreground="#f2f4f8",
            insertbackground="#f2f4f8",
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", message)
        text.configure(state="disabled")

        button_row = ttk.Frame(frame)
        button_row.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def close_dialog() -> None:
            dialog.grab_release()
            dialog.destroy()

        ttk.Button(button_row, text="Close", command=close_dialog).pack(side="right")
        dialog.bind("<Escape>", lambda _event: close_dialog())
        dialog.bind("<Return>", lambda _event: close_dialog())
        self.wait_window(dialog)

    def show_error(self, title: str, message: str) -> None:
        if len(message) > 180 or "\n" in message:
            self.show_scrollable_error(title, message)
            return
        messagebox.showerror(title, message)

    def _build_ui(self) -> None:
        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        settings = ttk.Frame(self, padding=12)
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        folder_frame = ttk.Frame(settings)
        folder_frame.grid(row=0, column=1, sticky="ew", pady=4)
        folder_frame.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var)
        self.folder_entry.grid(row=0, column=0, sticky="ew")
        folder_scroll = ttk.Scrollbar(folder_frame, orient="horizontal", command=self.folder_entry.xview)
        folder_scroll.grid(row=1, column=0, sticky="ew")
        self.folder_entry.configure(xscrollcommand=folder_scroll.set)
        self.enable_folder_drop()
        ttk.Button(settings, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(settings, text="Title").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.series_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)

        mode_options = ttk.Frame(settings)
        mode_options.grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        movie_mode_check = ttk.Checkbutton(
            mode_options,
            text="Movie mode",
            variable=self.movie_mode_var,
            command=self.set_movie_mode,
        )
        movie_mode_check.grid(row=0, column=0, padx=(0, 12))
        self.add_tooltip(movie_mode_check, "Use film rules: movie title plus release year, movie.nfo, movie artwork, and optional flattening.")
        show_mode_check = ttk.Checkbutton(
            mode_options,
            text="Show/Series mode",
            variable=self.show_mode_var,
            command=self.set_show_mode,
        )
        show_mode_check.grid(row=0, column=1, padx=(0, 12))
        self.add_tooltip(show_mode_check, "Use TV rules: season and episode naming, show-root metadata, season folders, and multi-season support.")
        self.year_label = ttk.Label(mode_options, text="Year")
        self.year_label.grid(row=0, column=2, padx=(0, 6))
        self.year_entry = ttk.Entry(mode_options, width=8, textvariable=self.year_var)
        self.year_entry.grid(row=0, column=3)
        self.add_tooltip(self.year_entry, "Movie release year or show-root year, depending on the selected mode.")

        profile_row = ttk.Frame(settings)
        profile_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(profile_row, text="Preset").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.preset_combo = ttk.Combobox(profile_row, textvariable=self.preset_var, values=list(PRESET_PROFILES), state="readonly", width=22)
        self.preset_combo.grid(row=0, column=1, sticky="w")
        ttk.Button(profile_row, text="Apply Preset", command=self.apply_selected_preset).grid(row=0, column=2, padx=(8, 16))
        ttk.Label(profile_row, text="Profile").grid(row=0, column=3, sticky="w", padx=(0, 8))
        self.profile_combo = ttk.Combobox(profile_row, textvariable=self.profile_name_var, values=self.available_profiles(), width=26)
        self.profile_combo.grid(row=0, column=4, sticky="w")
        ttk.Button(profile_row, text="Load Profile", command=self.load_selected_profile).grid(row=0, column=5, padx=(8, 0))
        ttk.Button(profile_row, text="Save Profile", command=self.save_current_profile).grid(row=0, column=6, padx=(8, 0))
        ttk.Button(profile_row, text="Delete Profile", command=self.delete_selected_profile).grid(row=0, column=7, padx=(8, 0))
        self.add_tooltip(self.preset_combo, "Load one of the built-in layouts for movie, show-root, season, or loose release folders.")
        self.add_tooltip(self.profile_combo, "Load or save your own named settings profile.")

        show_options = ttk.Frame(settings)
        show_options.grid(row=4, column=1, columnspan=2, sticky="w", pady=4)
        self.season_label = ttk.Label(show_options, text="Season")
        self.season_label.grid(row=0, column=0, padx=(0, 6))
        self.season_spinbox = ttk.Spinbox(show_options, from_=0, to=999, width=5, textvariable=self.season_var)
        self.season_spinbox.grid(row=0, column=1, padx=(0, 12))
        self.start_episode_label = ttk.Label(show_options, text="Start")
        self.start_episode_label.grid(row=0, column=2, padx=(0, 6))
        self.start_episode_spinbox = ttk.Spinbox(show_options, from_=1, to=999, width=5, textvariable=self.start_episode_var)
        self.start_episode_spinbox.grid(row=0, column=3, padx=(0, 12))
        self.episode_from_path_check = ttk.Checkbutton(
            show_options,
            text="Episode from path",
            variable=self.episode_from_path_var,
        )
        self.episode_from_path_check.grid(row=0, column=4, padx=(0, 12))
        self.add_tooltip(self.episode_from_path_check, "Read the episode number from the filename or folder path instead of counting items in order.")
        self.normalize_show_nfo_check = ttk.Checkbutton(
            show_options,
            text="Show NFO",
            variable=self.normalize_show_nfo_var,
        )
        self.normalize_show_nfo_check.grid(row=0, column=5, padx=(0, 12))
        self.add_tooltip(self.normalize_show_nfo_check, "Normalize show-level metadata to tvshow.nfo in the show root.")
        self.rename_show_folder_check = ttk.Checkbutton(
            show_options,
            text="Show folder",
            variable=self.rename_show_folder_var,
        )
        self.rename_show_folder_check.grid(row=0, column=6, padx=(0, 12))
        self.add_tooltip(self.rename_show_folder_check, "Rename the top-level show folder to Jellyfin's Series Name (Year) style.")
        self.normalize_season_folder_check = ttk.Checkbutton(
            show_options,
            text="Season folder",
            variable=self.normalize_season_folder_var,
        )
        self.normalize_season_folder_check.grid(row=0, column=7, padx=(0, 12))
        self.add_tooltip(self.normalize_season_folder_check, "Move each season into a Season XX folder and normalize season metadata there.")
        self.multi_season_check = ttk.Checkbutton(
            show_options,
            text="Multi-season",
            variable=self.multi_season_var,
        )
        self.multi_season_check.grid(row=0, column=8, padx=(0, 12))
        self.add_tooltip(self.multi_season_check, "Detect and process multiple season folders in one scan.")
        self.cleanup_stale_paths_check = ttk.Checkbutton(
            show_options,
            text="Clean old paths",
            variable=self.cleanup_stale_paths_var,
        )
        self.cleanup_stale_paths_check.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.add_tooltip(self.cleanup_stale_paths_check, "After apply, offer to delete old source folders that are no longer part of the new Jellyfin structure.")

        ttk.Label(settings, text="Extensions").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.extensions_var).grid(row=5, column=1, sticky="ew", pady=4)

        options = ttk.Frame(settings)
        options.grid(row=5, column=2, sticky="e", padx=(8, 0), pady=4)
        recursive_check = ttk.Checkbutton(options, text="Recursive", variable=self.recursive_var)
        recursive_check.grid(row=0, column=0, padx=(0, 10))
        self.add_tooltip(recursive_check, "Scan nested release folders below the selected folder.")
        sidecars_check = ttk.Checkbutton(options, text="Sidecars", variable=self.include_sidecars_var)
        sidecars_check.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.add_tooltip(sidecars_check, "Rename matching .nfo, artwork, subtitle, and trickplay sidecar files.")
        flatten_check = ttk.Checkbutton(options, text="Flatten", variable=self.flatten_var)
        flatten_check.grid(row=0, column=2, padx=(0, 10), sticky="w")
        self.add_tooltip(flatten_check, "Move each video into a clean folder next to the selected source folder.")
        self.normalize_movie_nfo_check = ttk.Checkbutton(
            options,
            text="Movie NFO",
            variable=self.normalize_movie_nfo_var,
        )
        self.normalize_movie_nfo_check.grid(row=0, column=3, sticky="w")
        self.add_tooltip(self.normalize_movie_nfo_check, "Normalize movie metadata to movie.nfo in movie mode.")

        actions = ttk.Frame(settings)
        actions.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Preview", command=self.preview).pack(side="left")
        ttk.Button(actions, text="Apply Renames", command=self.apply_renames).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Undo Last", command=self.undo_last).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Load Settings", command=self.load_settings).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Save Settings", command=self.save_settings).pack(side="left", padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_var).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("kind", "current", "new", "folder")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", style="Preview.Treeview")
        self.tree.heading("kind", text="Kind")
        self.tree.heading("current", text="Current name")
        self.tree.heading("new", text="Target name")
        self.tree.heading("folder", text="Target folder")
        self.tree.column("kind", width=90, minwidth=70)
        self.tree.column("current", width=300, minwidth=180)
        self.tree.column("new", width=300, minwidth=180)
        self.tree.column("folder", width=380, minwidth=220)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._update_preview_details)

        details = ttk.LabelFrame(table_frame, text="Selected item", padding=(10, 8), style="Preview.TLabelframe")
        details.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        ttk.Label(details, text="Kind").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(details, textvariable=self.preview_kind_var, state="readonly", style="Preview.TEntry").grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(details, text="Target folder").grid(row=0, column=2, sticky="w", padx=(12, 8), pady=2)
        ttk.Entry(details, textvariable=self.preview_target_folder_var, state="readonly", style="Preview.TEntry").grid(row=0, column=3, sticky="ew", pady=2)

        diff = ttk.LabelFrame(table_frame, text="Diff preview", padding=(10, 8), style="Preview.TLabelframe")
        diff.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        diff.columnconfigure(0, weight=1)
        diff.columnconfigure(1, weight=1)
        diff.rowconfigure(1, weight=1)
        ttk.Label(diff, text="Old").grid(row=0, column=0, sticky="w")
        ttk.Label(diff, text="New").grid(row=0, column=1, sticky="w")
        self.old_diff_text = tk.Text(diff, height=7, wrap="word", borderwidth=0, highlightthickness=0, background="#1f232a", foreground="#f2f4f8", insertbackground="#f2f4f8")
        self.new_diff_text = tk.Text(diff, height=7, wrap="word", borderwidth=0, highlightthickness=0, background="#1f232a", foreground="#f2f4f8", insertbackground="#f2f4f8")
        self.old_diff_text.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.new_diff_text.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self._make_readonly_text(self.old_diff_text)
        self._make_readonly_text(self.new_diff_text)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure(
            "Preview.Treeview",
            background="#1f232a",
            fieldbackground="#1f232a",
            foreground="#f2f4f8",
            rowheight=26,
            borderwidth=0,
        )
        style.map(
            "Preview.Treeview",
            background=[("selected", "#355c8a")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Preview.Treeview.Heading",
            background="#2a2f36",
            foreground="#ffffff",
            relief="flat",
        )
        style.map(
            "Preview.Treeview.Heading",
            background=[("active", "#343941")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Preview.TLabelframe",
            background=self.cget("background"),
            foreground="#f2f4f8",
        )
        style.configure(
            "Preview.TLabelframe.Label",
            background=self.cget("background"),
            foreground="#f2f4f8",
        )
        style.configure(
            "Preview.TEntry",
            fieldbackground="#262b33",
            foreground="#f2f4f8",
            insertcolor="#f2f4f8",
        )

    def _make_readonly_text(self, widget: tk.Text) -> None:
        widget.configure(state="disabled")
        widget.tag_configure("label", foreground="#9fb3c8")
        widget.tag_configure("path", foreground="#f2f4f8")
        widget.tag_configure("old", foreground="#ff9aa2")
        widget.tag_configure("new", foreground="#8be28b")

    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        self._tooltips.append(Tooltip(widget, text))

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose episode folder")
        if folder:
            self.folder_var.set(folder)
            self.autofill_fields_from_folder(Path(folder))

    def enable_folder_drop(self) -> None:
        if DND_FILES is None:
            return
        self.folder_entry.drop_target_register(DND_FILES)
        self.folder_entry.dnd_bind("<<Drop>>", self.handle_folder_drop)

    def handle_folder_drop(self, event: tk.Event) -> None:
        paths = self.tk.splitlist(event.data)
        if not paths:
            return
        path = Path(paths[0]).expanduser()
        if path.is_file():
            path = path.parent
        self.folder_var.set(str(path))
        self.autofill_fields_from_folder(path)
        self.folder_entry.xview_moveto(1.0)
        self.status_var.set("Folder set from dropped path.")

    def autofill_fields_from_folder(self, folder: Path) -> None:
        if self.movie_mode_var.get():
            if looks_like_season_folder(folder):
                messagebox.showwarning(
                    "Season folder detected",
                    "This folder looks like a TV season folder, but Movie mode is enabled.",
                )
            self.autofill_movie_fields_from_folder(folder)
        else:
            self.autofill_show_fields_from_folder(folder)
            self.apply_show_drop_recommended_settings(folder)

    def autofill_movie_fields_from_folder(self, folder: Path) -> None:
        title, year = parse_movie_folder_name(folder.name)
        if title:
            self.series_var.set(title)
        if year:
            self.year_var.set(year)

    def autofill_show_fields_from_folder(self, folder: Path) -> None:
        title, season = parse_show_folder_name(folder)
        if title:
            clean_title, year = parse_movie_folder_name(title)
            self.series_var.set(clean_title)
            if year:
                self.year_var.set(year)
        if season is not None:
            self.season_var.set(str(season))

    def ensure_settings_file(self) -> None:
        if CONFIG_FILE.exists() or not EXAMPLE_CONFIG_FILE.exists():
            return
        CONFIG_FILE.write_text(EXAMPLE_CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        self.status_var.set("Created settings.txt from settings.example.txt.")

    def load_settings(self, show_errors: bool = True) -> None:
        try:
            config = read_config(CONFIG_FILE)
        except FileNotFoundError:
            if show_errors:
                self.show_error("Settings not found", f"No settings file found at:\n{CONFIG_FILE}")
            return

        self.folder_var.set(config.get("folder", ""))
        self.series_var.set(config.get("movie_name") or config.get("series_name", ""))
        movie_mode = config.get("movie_mode", "false").lower() in {"1", "true", "yes", "y"}
        show_mode = config.get("show_mode", str(not movie_mode).lower()).lower() in {"1", "true", "yes", "y"}
        self.movie_mode_var.set(movie_mode)
        self.show_mode_var.set((show_mode and not movie_mode) or not movie_mode)
        if movie_mode:
            self.year_var.set(config.get("movie_year") or config.get("series_year", ""))
        else:
            self.year_var.set(config.get("series_year", ""))
        self.season_var.set(config.get("season", "1"))
        self.start_episode_var.set(config.get("start_episode", "1"))
        self.extensions_var.set(config.get("extensions", DEFAULT_EXTENSIONS))
        self.recursive_var.set(config.get("recursive", "false").lower() in {"1", "true", "yes", "y"})
        self.episode_from_path_var.set(config.get("episode_from_path", "false").lower() in {"1", "true", "yes", "y"})
        self.include_sidecars_var.set(config.get("include_sidecars", "false").lower() in {"1", "true", "yes", "y"})
        self.normalize_movie_nfo_var.set(config.get("normalize_movie_nfo", "false").lower() in {"1", "true", "yes", "y"})
        self.normalize_show_nfo_var.set(config.get("normalize_show_nfo", "false").lower() in {"1", "true", "yes", "y"})
        self.rename_show_folder_var.set(config.get("rename_show_folder", "false").lower() in {"1", "true", "yes", "y"})
        self.normalize_season_folder_var.set(config.get("normalize_season_folder", "false").lower() in {"1", "true", "yes", "y"})
        self.multi_season_var.set(config.get("multi_season", "false").lower() in {"1", "true", "yes", "y"})
        self.cleanup_stale_paths_var.set(config.get("cleanup_stale_paths", "false").lower() in {"1", "true", "yes", "y"})
        self.flatten_var.set(config.get("flatten", "false").lower() in {"1", "true", "yes", "y"})
        self.update_mode_state()
        self.preset_var.set("Custom")
        self.status_var.set("Settings loaded.")

    def set_movie_mode(self) -> None:
        self.preset_var.set("Custom")
        if self.movie_mode_var.get():
            self.show_mode_var.set(False)
            self.apply_movie_recommended_settings()
        elif not self.show_mode_var.get():
            self.show_mode_var.set(True)
            self.apply_show_recommended_settings()
        self.update_mode_state()

    def set_show_mode(self) -> None:
        self.preset_var.set("Custom")
        if self.show_mode_var.get():
            self.movie_mode_var.set(False)
            self.apply_show_recommended_settings()
        elif not self.movie_mode_var.get():
            self.movie_mode_var.set(True)
            self.apply_movie_recommended_settings()
        self.update_mode_state()

    def apply_movie_recommended_settings(self) -> None:
        self.include_sidecars_var.set(True)
        self.flatten_var.set(True)
        self.normalize_movie_nfo_var.set(True)
        self.normalize_show_nfo_var.set(False)
        self.rename_show_folder_var.set(False)
        self.normalize_season_folder_var.set(False)
        self.multi_season_var.set(False)
        self.cleanup_stale_paths_var.set(False)
        self.episode_from_path_var.set(False)
        self.preset_var.set("Jellyfin Movie")

    def apply_show_recommended_settings(self) -> None:
        self.include_sidecars_var.set(True)
        self.flatten_var.set(False)
        self.normalize_movie_nfo_var.set(False)
        self.normalize_show_nfo_var.set(True)
        self.rename_show_folder_var.set(True)
        self.normalize_season_folder_var.set(True)
        self.multi_season_var.set(False)
        self.preset_var.set("Jellyfin Show Root")

    def apply_show_drop_recommended_settings(self, folder: Path) -> None:
        if not self.show_mode_var.get():
            return
        if looks_like_season_folder(folder):
            self.apply_show_season_recommended_settings()
        else:
            self.apply_show_root_recommended_settings()

    def apply_show_root_recommended_settings(self) -> None:
        self.include_sidecars_var.set(True)
        self.flatten_var.set(False)
        self.normalize_movie_nfo_var.set(False)
        self.normalize_show_nfo_var.set(True)
        self.rename_show_folder_var.set(True)
        self.normalize_season_folder_var.set(False)
        self.multi_season_var.set(self.folder_has_season_folders(Path(self.folder_var.get()).expanduser()))
        if self.multi_season_var.get():
            self.normalize_season_folder_var.set(True)
            self.episode_from_path_var.set(True)
            self.recursive_var.set(True)
            self.preset_var.set("Jellyfin Season")
        else:
            self.preset_var.set("Jellyfin Show Root")

    def folder_has_season_folders(self, folder: Path) -> bool:
        if not folder.exists() or not folder.is_dir():
            return False
        return bool(detect_season_folders(folder, parse_extensions(self.extensions_var.get())))

    def apply_show_season_recommended_settings(self) -> None:
        self.include_sidecars_var.set(True)
        self.flatten_var.set(False)
        self.normalize_movie_nfo_var.set(False)
        self.normalize_show_nfo_var.set(True)
        self.rename_show_folder_var.set(True)
        self.normalize_season_folder_var.set(True)
        self.multi_season_var.set(False)
        self.preset_var.set("Jellyfin Season")

    def available_profiles(self) -> list[str]:
        return sorted(self.load_profiles().keys())

    def load_profiles(self) -> dict[str, dict[str, object]]:
        if not PROFILES_FILE.exists():
            return {}
        try:
            data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        profiles: dict[str, dict[str, object]] = {}
        for name, value in data.items():
            if isinstance(name, str) and isinstance(value, dict):
                profiles[name] = value
        return profiles

    def write_profiles(self, profiles: dict[str, dict[str, object]]) -> None:
        PROFILES_FILE.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")

    def current_settings_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder_var.get(),
            "series_name": self.series_var.get(),
            "series_year": self.year_var.get(),
            "movie_mode": self.movie_mode_var.get(),
            "show_mode": self.show_mode_var.get(),
            "season": self.season_var.get(),
            "start_episode": self.start_episode_var.get(),
            "extensions": self.extensions_var.get(),
            "recursive": self.recursive_var.get(),
            "episode_from_path": self.episode_from_path_var.get(),
            "include_sidecars": self.include_sidecars_var.get(),
            "normalize_movie_nfo": self.normalize_movie_nfo_var.get(),
            "normalize_show_nfo": self.normalize_show_nfo_var.get(),
            "rename_show_folder": self.rename_show_folder_var.get(),
            "normalize_season_folder": self.normalize_season_folder_var.get(),
            "multi_season": self.multi_season_var.get(),
            "cleanup_stale_paths": self.cleanup_stale_paths_var.get(),
            "flatten": self.flatten_var.get(),
        }

    def apply_settings_dict(self, settings: dict[str, object]) -> None:
        self.folder_var.set(str(settings.get("folder", self.folder_var.get())))
        self.series_var.set(str(settings.get("series_name", self.series_var.get())))
        self.year_var.set(str(settings.get("series_year", self.year_var.get())))
        self.movie_mode_var.set(bool(settings.get("movie_mode", self.movie_mode_var.get())))
        self.show_mode_var.set(bool(settings.get("show_mode", self.show_mode_var.get())))
        self.season_var.set(str(settings.get("season", self.season_var.get())))
        self.start_episode_var.set(str(settings.get("start_episode", self.start_episode_var.get())))
        self.extensions_var.set(str(settings.get("extensions", self.extensions_var.get())))
        self.recursive_var.set(bool(settings.get("recursive", self.recursive_var.get())))
        self.episode_from_path_var.set(bool(settings.get("episode_from_path", self.episode_from_path_var.get())))
        self.include_sidecars_var.set(bool(settings.get("include_sidecars", self.include_sidecars_var.get())))
        self.normalize_movie_nfo_var.set(bool(settings.get("normalize_movie_nfo", self.normalize_movie_nfo_var.get())))
        self.normalize_show_nfo_var.set(bool(settings.get("normalize_show_nfo", self.normalize_show_nfo_var.get())))
        self.rename_show_folder_var.set(bool(settings.get("rename_show_folder", self.rename_show_folder_var.get())))
        self.normalize_season_folder_var.set(bool(settings.get("normalize_season_folder", self.normalize_season_folder_var.get())))
        self.multi_season_var.set(bool(settings.get("multi_season", self.multi_season_var.get())))
        self.cleanup_stale_paths_var.set(bool(settings.get("cleanup_stale_paths", self.cleanup_stale_paths_var.get())))
        self.flatten_var.set(bool(settings.get("flatten", self.flatten_var.get())))
        self.update_mode_state()

    def apply_selected_preset(self) -> None:
        preset_name = self.preset_var.get()
        preset = PRESET_PROFILES.get(preset_name)
        if preset is None:
            self.preset_var.set("Custom")
            return
        self.apply_settings_dict(preset)
        self.status_var.set(f"Applied preset: {preset_name}.")

    def load_selected_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        profiles = self.load_profiles()
        profile = profiles.get(name)
        if not profile:
            self.show_error("Profile not found", f"No saved profile named '{name}' was found.")
            return
        self.apply_settings_dict(profile)
        self.preset_var.set("Custom")
        self.status_var.set(f"Loaded profile: {name}.")

    def save_current_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        if not name:
            self.show_error("Profile name missing", "Enter a profile name first.")
            return
        profiles = self.load_profiles()
        profiles[name] = self.current_settings_dict()
        self.write_profiles(profiles)
        self.profile_combo["values"] = self.available_profiles()
        self.status_var.set(f"Saved profile: {name}.")

    def delete_selected_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        profiles = self.load_profiles()
        if name not in profiles:
            self.show_error("Profile not found", f"No saved profile named '{name}' was found.")
            return
        if not messagebox.askyesno("Delete profile", f"Delete saved profile '{name}'?"):
            return
        profiles.pop(name, None)
        self.write_profiles(profiles)
        self.profile_combo["values"] = self.available_profiles()
        self.profile_name_var.set("")
        self.status_var.set(f"Deleted profile: {name}.")

    def update_mode_state(self) -> None:
        movie_mode = self.movie_mode_var.get()
        show_mode = self.show_mode_var.get()
        movie_state = "normal" if movie_mode else "disabled"
        show_state = "normal" if show_mode else "disabled"
        self.year_label.configure(state="normal")
        self.year_entry.configure(state="normal")
        self.season_label.configure(state=show_state)
        self.season_spinbox.configure(state=show_state)
        self.start_episode_label.configure(state=show_state)
        self.start_episode_spinbox.configure(state=show_state)
        self.episode_from_path_check.configure(state=show_state)
        self.normalize_movie_nfo_check.configure(state=movie_state)
        self.normalize_show_nfo_check.configure(state=show_state)
        self.rename_show_folder_check.configure(state=show_state)
        self.normalize_season_folder_check.configure(state=show_state)
        self.multi_season_check.configure(state=show_state)
        self.cleanup_stale_paths_check.configure(state=show_state)

    def save_settings(self) -> None:
        content = "\n".join(
            [
                f"folder={self.folder_var.get()}",
                f"series_name={self.series_var.get()}",
                f"series_year={self.year_var.get()}",
                f"movie_mode={str(self.movie_mode_var.get()).lower()}",
                f"show_mode={str(self.show_mode_var.get()).lower()}",
                f"movie_name={self.series_var.get()}",
                f"movie_year={self.year_var.get()}",
                f"season={self.season_var.get()}",
                f"start_episode={self.start_episode_var.get()}",
                "dry_run=true",
                f"recursive={str(self.recursive_var.get()).lower()}",
                f"episode_from_path={str(self.episode_from_path_var.get()).lower()}",
                f"include_sidecars={str(self.include_sidecars_var.get()).lower()}",
                f"normalize_movie_nfo={str(self.normalize_movie_nfo_var.get()).lower()}",
                f"normalize_show_nfo={str(self.normalize_show_nfo_var.get()).lower()}",
                f"rename_show_folder={str(self.rename_show_folder_var.get()).lower()}",
                f"normalize_season_folder={str(self.normalize_season_folder_var.get()).lower()}",
                f"multi_season={str(self.multi_season_var.get()).lower()}",
                f"cleanup_stale_paths={str(self.cleanup_stale_paths_var.get()).lower()}",
                f"flatten={str(self.flatten_var.get()).lower()}",
                f"extensions={self.extensions_var.get()}",
                "",
            ]
        )
        CONFIG_FILE.write_text(content, encoding="utf-8")
        self.status_var.set("Settings saved.")

    def preview(self) -> None:
        try:
            self.plan = self._build_plan_from_form()
        except ValueError as error:
            self.show_error("Invalid settings", str(error))
            return

        self._fill_table(self.plan)

        if not self.plan:
            self.status_var.set("No video files found.")
            self._update_preview_details()
            return

        errors = validate_plan(self.plan)
        if errors:
            self.status_var.set(f"{len(errors)} conflict(s) found.")
            self.show_error("Conflicts found", "\n".join(errors[:20]))
            return

        changed = count_changed(self.plan)
        self.status_var.set(f"Preview ready: {len(self.plan)} files, {changed} rename(s).")
        self._update_preview_details()

    def apply_renames(self) -> None:
        if not self.plan:
            self.preview()
            if not self.plan:
                return

        errors = validate_plan(self.plan)
        if errors:
            self.show_error("Conflicts found", "\n".join(errors[:20]))
            return

        changed = count_changed(self.plan)
        if changed == 0:
            messagebox.showinfo("Nothing to rename", "All files already match the target names.")
            return

        confirmed = messagebox.askyesno(
            "Apply renames",
            f"Rename {changed} item(s)?\n\nAn undo log will be written to rename-log.json.",
        )
        if not confirmed:
            return

        stale_dirs = self.stale_source_dirs_for_apply()
        try:
            result = rename_files(self.plan)
        except OSError as error:
            self.show_error("Rename failed", str(error))
            return

        removed_stale_dirs: list[Path] = []
        if stale_dirs:
            removed_stale_dirs = self.confirm_and_delete_stale_dirs(stale_dirs)

        cleanup_text = ""
        if result.removed_empty_dirs:
            cleanup_text = f"\nRemoved {len(result.removed_empty_dirs)} empty source folder(s)."
        if removed_stale_dirs:
            cleanup_text += f"\nDeleted {len(removed_stale_dirs)} old source folder(s)."

        self.status_var.set(
            f"Done: renamed {result.renamed_count} item(s), removed {len(result.removed_empty_dirs) + len(removed_stale_dirs)} folder(s)."
        )
        messagebox.showinfo("Done", f"Renamed {result.renamed_count} item(s).{cleanup_text}")
        self.preview()

    def stale_source_dirs_for_apply(self) -> list[Path]:
        if self.movie_mode_var.get() or not self.show_mode_var.get() or not self.cleanup_stale_paths_var.get():
            return []
        selected_folder = Path(self.folder_var.get()).expanduser()
        return find_stale_source_dirs(selected_folder, self.plan)

    def confirm_and_delete_stale_dirs(self, stale_dirs: list[Path]) -> list[Path]:
        existing_dirs = [path for path in stale_dirs if path.exists()]
        if not existing_dirs:
            return []
        preview = "\n".join(str(path) for path in existing_dirs[:8])
        if len(existing_dirs) > 8:
            preview += f"\n... and {len(existing_dirs) - 8} more"
        confirmed = messagebox.askyesno(
            "Delete old source folders?",
            "The rename completed. Delete these old source folder(s) that were not part of the new structure?\n\n"
            f"{preview}\n\nThis cannot be undone by the rename undo log.",
        )
        if not confirmed:
            return []
        try:
            return delete_stale_source_dirs(existing_dirs)
        except OSError as error:
            self.show_error("Cleanup failed", str(error))
            return []

    def undo_last(self) -> None:
        confirmed = messagebox.askyesno(
            "Undo last rename",
            f"Undo the last rename operation from:\n{UNDO_LOG_FILE}?",
        )
        if not confirmed:
            return
        try:
            count = undo_from_log(UNDO_LOG_FILE)
        except FileNotFoundError:
            self.show_error("Undo failed", "rename-log.json was not found.")
            return
        except Exception as error:
            self.show_error("Undo failed", str(error))
            return
        self.status_var.set(f"Undo complete: reverted {count} item(s).")
        messagebox.showinfo("Undo complete", f"Reverted {count} item(s).")
        self.preview()

    def _build_plan_from_form(self) -> list[RenameItem]:
        folder = Path(self.folder_var.get()).expanduser()
        title = self.series_var.get().strip()

        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Folder does not exist: {folder}")
        if not title:
            raise ValueError("Title is required.")

        if self.movie_mode_var.get():
            media_plans = build_movie_plans(
                folder=folder,
                movie_name=title,
                release_year=self.year_var.get(),
                extensions=parse_extensions(self.extensions_var.get()),
                recursive=self.recursive_var.get(),
                include_sidecars=self.include_sidecars_var.get(),
                flatten=self.flatten_var.get(),
                normalize_movie_nfo=self.normalize_movie_nfo_var.get(),
            )
        elif self.show_mode_var.get() and self.multi_season_var.get():
            media_plans = build_multi_season_episode_plans(
                folder=folder,
                series_name=title,
                start_episode=int(self.start_episode_var.get()),
                extensions=parse_extensions(self.extensions_var.get()),
                recursive=self.recursive_var.get(),
                include_sidecars=self.include_sidecars_var.get(),
                flatten=self.flatten_var.get(),
                series_year=self.year_var.get(),
                rename_show_folder=self.rename_show_folder_var.get(),
                normalize_season_folder=self.normalize_season_folder_var.get(),
                normalize_show_nfo=self.normalize_show_nfo_var.get(),
            )
        else:
            try:
                season = int(self.season_var.get())
                start_episode = int(self.start_episode_var.get())
            except ValueError as error:
                raise ValueError("Season and start episode must be numbers.") from error

            media_plans = build_episode_plans(
                folder=folder,
                series_name=title,
                season=season,
                start_episode=start_episode,
                extensions=parse_extensions(self.extensions_var.get()),
                recursive=self.recursive_var.get(),
                episode_from_path=self.episode_from_path_var.get(),
                include_sidecars=self.include_sidecars_var.get(),
                flatten=self.flatten_var.get(),
                series_year=self.year_var.get() if self.show_mode_var.get() else "",
                rename_show_folder=self.show_mode_var.get() and self.rename_show_folder_var.get(),
                normalize_season_folder=self.show_mode_var.get() and self.normalize_season_folder_var.get(),
                normalize_show_nfo=self.show_mode_var.get() and self.normalize_show_nfo_var.get(),
            )
        return flatten_plan(media_plans)

    def _fill_table(self, plan: list[RenameItem]) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(plan):
            folder_text = self._short_target_folder(item)
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("even",) if index % 2 == 0 else ("odd",),
                values=(
                    item.kind,
                    item.old_path.name,
                    item.new_path.name,
                    folder_text,
            ),
        )
        self.tree.tag_configure("even", background="#1f232a", foreground="#f2f4f8")
        self.tree.tag_configure("odd", background="#262b33", foreground="#f2f4f8")
        self.tree.tag_configure("evendelete", background="#33272d", foreground="#f2f4f8")
        self.tree.tag_configure("odddelete", background="#3a2c33", foreground="#f2f4f8")
        self._update_preview_details()

    def _set_text(self, widget: tk.Text, lines: list[tuple[str, str]]) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for tag, text in lines:
            widget.insert("end", text + "\n", tag)
        widget.configure(state="disabled")

    def _short_target_folder(self, item: RenameItem) -> str:
        folder = item.new_path.parent
        root = self._selected_folder()
        if root is not None:
            try:
                return str(folder.relative_to(root))
            except ValueError:
                pass
        return str(folder)

    def _selected_folder(self) -> Path | None:
        raw = self.folder_var.get().strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        return path if path.exists() else None

    def _update_preview_details(self, event: tk.Event | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            self.preview_kind_var.set("")
            self.preview_current_path_var.set("")
            self.preview_target_path_var.set("")
            self.preview_target_folder_var.set("")
            self._set_text(self.old_diff_text, [("label", "No item selected.")])
            self._set_text(self.new_diff_text, [("label", "No item selected.")])
            return

        item_id = selection[0]
        try:
            plan_item = self.plan[int(item_id)]
        except (ValueError, IndexError):
            return
        values = self.tree.item(item_id, "values")
        if len(values) < 4:
            return
        kind, _, _, folder_text = values[:4]
        self.preview_kind_var.set(kind)
        self.preview_current_path_var.set(str(plan_item.old_path))
        self.preview_target_path_var.set(str(plan_item.new_path))
        self.preview_target_folder_var.set(folder_text if folder_text else str(plan_item.new_path.parent))
        self._set_text(
            self.old_diff_text,
            [
                ("label", "Old"),
                ("path", str(plan_item.old_path)),
                ("label", f"Folder: {plan_item.old_path.parent}"),
            ],
        )
        self._set_text(
            self.new_diff_text,
            [
                ("label", "New"),
                ("path", str(plan_item.new_path)),
                ("label", f"Folder: {plan_item.new_path.parent}"),
            ],
        )


def main() -> None:
    app = EpisodeRenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
