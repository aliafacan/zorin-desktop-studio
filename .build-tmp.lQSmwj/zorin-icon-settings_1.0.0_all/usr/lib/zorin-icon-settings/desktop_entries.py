#!/usr/bin/env python3
"""Masaüstü .desktop girdilerini okuma ve düzenleme."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class DesktopEntryInfo:
    path: str
    file_name: str
    display_name: str
    icon: str
    exec_command: str
    comment: str


class DesktopEntryStore:
    def __init__(self):
        self.desktop_dir = self._detect_desktop_dir()

    def list_entries(self) -> list[DesktopEntryInfo]:
        if not self.desktop_dir.exists():
            return []

        entries = []
        for path in sorted(self.desktop_dir.glob("*.desktop"), key=lambda item: item.name.lower()):
            try:
                entries.append(self.load_entry(str(path)))
            except OSError:
                continue
        return entries

    def load_entry(self, path: str) -> DesktopEntryInfo:
        parser = self._read_parser(path)
        section = parser["Desktop Entry"]
        file_name = Path(path).name
        display_name = section.get("Name", Path(path).stem)
        icon = section.get("Icon", "")
        exec_command = section.get("Exec", "")
        comment = section.get("Comment", "")
        return DesktopEntryInfo(
            path=path,
            file_name=file_name,
            display_name=display_name,
            icon=icon,
            exec_command=exec_command,
            comment=comment,
        )

    def save_entry(
        self,
        original_path: str,
        file_name: str,
        display_name: str,
        icon: str,
        exec_command: str,
        comment: str,
    ) -> DesktopEntryInfo:
        parser = self._read_parser(original_path)
        if "Desktop Entry" not in parser:
            parser["Desktop Entry"] = {}

        target_name = self._normalize_file_name(file_name)
        target_path = str(self.desktop_dir / target_name)

        section = parser["Desktop Entry"]
        section["Name"] = display_name.strip() or Path(target_name).stem
        section["Icon"] = icon.strip()
        section["Exec"] = exec_command.strip()
        section["Comment"] = comment.strip()

        if os.path.abspath(target_path) != os.path.abspath(original_path) and os.path.exists(target_path):
            raise FileExistsError(target_name)

        original_mode = os.stat(original_path).st_mode if os.path.exists(original_path) else None
        with open(target_path, "w", encoding="utf-8") as handle:
            parser.write(handle, space_around_delimiters=False)

        if original_mode is not None:
            os.chmod(target_path, original_mode)

        if os.path.abspath(target_path) != os.path.abspath(original_path) and os.path.exists(original_path):
            os.remove(original_path)

        return self.load_entry(target_path)

    def _read_parser(self, path: str) -> ConfigParser:
        parser = ConfigParser(interpolation=None)
        parser.optionxform = str
        with open(path, "r", encoding="utf-8") as handle:
            parser.read_file(handle)
        if "Desktop Entry" not in parser:
            raise OSError(f"Invalid desktop entry: {path}")
        return parser

    def _normalize_file_name(self, file_name: str) -> str:
        cleaned = file_name.strip().replace("/", "-")
        if not cleaned:
            cleaned = "launcher.desktop"
        if not cleaned.endswith(".desktop"):
            cleaned += ".desktop"
        return cleaned

    def _detect_desktop_dir(self) -> Path:
        host_dir = self._run_host_desktop_dir()
        if host_dir:
            return Path(host_dir)
        return Path.home() / "Desktop"

    def _run_host_desktop_dir(self) -> str | None:
        if not shutil.which("flatpak-spawn"):
            return None

        result = subprocess.run(
            [
                "flatpak-spawn",
                "--host",
                "sh",
                "-lc",
                'xdg-user-dir DESKTOP 2>/dev/null || printf "%s/Desktop\\n" "$HOME"',
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return None
        desktop_dir = result.stdout.strip()
        return desktop_dir or None
