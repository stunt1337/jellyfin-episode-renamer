#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from jellyfin_episode_renamer import (
    CONFIG_FILE,
    UNDO_LOG_FILE,
    RenameItem,
    build_episode_plans,
    count_changed,
    flatten_plan,
    read_config,
    rename_files,
    undo_from_log,
    validate_plan,
)


DEFAULT_EXTENSIONS = ".mkv,.mp4,.avi,.mov,.m4v,.webm,.ts"
EXAMPLE_CONFIG_FILE = Path(__file__).with_name("settings.example.txt")


def parse_extensions(value: str) -> set[str]:
    return {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in value.split(",")
        if ext.strip()
    }


class EpisodeRenamerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Jellyfin Episode Renamer")
        self.geometry("980x640")
        self.minsize(820, 520)

        self.plan: list[RenameItem] = []

        self.folder_var = tk.StringVar()
        self.series_var = tk.StringVar()
        self.season_var = tk.StringVar(value="1")
        self.start_episode_var = tk.StringVar(value="1")
        self.extensions_var = tk.StringVar(value=DEFAULT_EXTENSIONS)
        self.recursive_var = tk.BooleanVar(value=False)
        self.episode_from_path_var = tk.BooleanVar(value=False)
        self.include_sidecars_var = tk.BooleanVar(value=False)
        self.flatten_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Choose a folder and run Preview.")

        self._build_ui()
        self.ensure_settings_file()
        if CONFIG_FILE.exists():
            self.load_settings(show_errors=False)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        settings = ttk.Frame(self, padding=12)
        settings.grid(row=0, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.folder_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(settings, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(settings, text="Series name").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.series_var).grid(row=1, column=1, sticky="ew", pady=4)

        numbers = ttk.Frame(settings)
        numbers.grid(row=1, column=2, sticky="e", padx=(8, 0), pady=4)
        ttk.Label(numbers, text="Season").grid(row=0, column=0, padx=(0, 6))
        ttk.Spinbox(numbers, from_=1, to=999, width=5, textvariable=self.season_var).grid(row=0, column=1)
        ttk.Label(numbers, text="Start").grid(row=0, column=2, padx=(12, 6))
        ttk.Spinbox(numbers, from_=1, to=999, width=5, textvariable=self.start_episode_var).grid(row=0, column=3)

        ttk.Label(settings, text="Extensions").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.extensions_var).grid(row=2, column=1, sticky="ew", pady=4)

        options = ttk.Frame(settings)
        options.grid(row=2, column=2, sticky="e", padx=(8, 0), pady=4)
        ttk.Checkbutton(options, text="Recursive", variable=self.recursive_var).grid(row=0, column=0, padx=(0, 10))
        ttk.Checkbutton(options, text="Episode from path", variable=self.episode_from_path_var).grid(row=0, column=1)
        ttk.Checkbutton(options, text="Sidecars", variable=self.include_sidecars_var).grid(row=1, column=0, padx=(0, 10), sticky="w")
        ttk.Checkbutton(options, text="Flatten", variable=self.flatten_var).grid(row=1, column=1, sticky="w")

        actions = ttk.Frame(settings)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
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
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("kind", text="Kind")
        self.tree.heading("current", text="Current name")
        self.tree.heading("new", text="New path")
        self.tree.heading("folder", text="Folder")
        self.tree.column("kind", width=90, minwidth=70)
        self.tree.column("current", width=280, minwidth=180)
        self.tree.column("new", width=360, minwidth=220)
        self.tree.column("folder", width=280, minwidth=180)
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose episode folder")
        if folder:
            self.folder_var.set(folder)

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
                messagebox.showerror("Settings not found", f"No settings file found at:\n{CONFIG_FILE}")
            return

        self.folder_var.set(config.get("folder", ""))
        self.series_var.set(config.get("series_name", ""))
        self.season_var.set(config.get("season", "1"))
        self.start_episode_var.set(config.get("start_episode", "1"))
        self.extensions_var.set(config.get("extensions", DEFAULT_EXTENSIONS))
        self.recursive_var.set(config.get("recursive", "false").lower() in {"1", "true", "yes", "y"})
        self.episode_from_path_var.set(config.get("episode_from_path", "false").lower() in {"1", "true", "yes", "y"})
        self.include_sidecars_var.set(config.get("include_sidecars", "false").lower() in {"1", "true", "yes", "y"})
        self.flatten_var.set(config.get("flatten", "false").lower() in {"1", "true", "yes", "y"})
        self.status_var.set("Settings loaded.")

    def save_settings(self) -> None:
        content = "\n".join(
            [
                f"folder={self.folder_var.get()}",
                f"series_name={self.series_var.get()}",
                f"season={self.season_var.get()}",
                f"start_episode={self.start_episode_var.get()}",
                "dry_run=true",
                f"recursive={str(self.recursive_var.get()).lower()}",
                f"episode_from_path={str(self.episode_from_path_var.get()).lower()}",
                f"include_sidecars={str(self.include_sidecars_var.get()).lower()}",
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
            messagebox.showerror("Invalid settings", str(error))
            return

        self._fill_table(self.plan)

        if not self.plan:
            self.status_var.set("No video files found.")
            return

        errors = validate_plan(self.plan)
        if errors:
            self.status_var.set(f"{len(errors)} conflict(s) found.")
            messagebox.showerror("Conflicts found", "\n".join(errors[:20]))
            return

        changed = count_changed(self.plan)
        self.status_var.set(f"Preview ready: {len(self.plan)} files, {changed} rename(s).")

    def apply_renames(self) -> None:
        if not self.plan:
            self.preview()
            if not self.plan:
                return

        errors = validate_plan(self.plan)
        if errors:
            messagebox.showerror("Conflicts found", "\n".join(errors[:20]))
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

        try:
            result = rename_files(self.plan)
        except OSError as error:
            messagebox.showerror("Rename failed", str(error))
            return

        cleanup_text = ""
        if result.removed_empty_dirs:
            cleanup_text = f"\nRemoved {len(result.removed_empty_dirs)} empty source folder(s)."

        self.status_var.set(
            f"Done: renamed {result.renamed_count} item(s), removed {len(result.removed_empty_dirs)} empty folder(s)."
        )
        messagebox.showinfo("Done", f"Renamed {result.renamed_count} item(s).{cleanup_text}")
        self.preview()

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
            messagebox.showerror("Undo failed", "rename-log.json was not found.")
            return
        except Exception as error:
            messagebox.showerror("Undo failed", str(error))
            return
        self.status_var.set(f"Undo complete: reverted {count} item(s).")
        messagebox.showinfo("Undo complete", f"Reverted {count} item(s).")
        self.preview()

    def _build_plan_from_form(self) -> list[RenameItem]:
        folder = Path(self.folder_var.get()).expanduser()
        series_name = self.series_var.get().strip()

        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Folder does not exist: {folder}")
        if not series_name:
            raise ValueError("Series name is required.")

        try:
            season = int(self.season_var.get())
            start_episode = int(self.start_episode_var.get())
        except ValueError as error:
            raise ValueError("Season and start episode must be numbers.") from error

        episode_plans = build_episode_plans(
            folder=folder,
            series_name=series_name,
            season=season,
            start_episode=start_episode,
            extensions=parse_extensions(self.extensions_var.get()),
            recursive=self.recursive_var.get(),
            episode_from_path=self.episode_from_path_var.get(),
            include_sidecars=self.include_sidecars_var.get(),
            flatten=self.flatten_var.get(),
        )
        return flatten_plan(episode_plans)

    def _fill_table(self, plan: list[RenameItem]) -> None:
        self.tree.delete(*self.tree.get_children())
        for item in plan:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.kind,
                    item.old_path.name,
                    str(item.new_path),
                    str(item.old_path.parent),
                ),
            )


def main() -> None:
    app = EpisodeRenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
