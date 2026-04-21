#!/usr/bin/env python3
"""Oturum açılışında düzen yükleme için autostart yardımcıları."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import sys


AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "zorin-desktop-studio-autoload.desktop"
WATCHER_AUTOSTART_FILE = AUTOSTART_DIR / "zorin-desktop-studio-watcher.desktop"


class AutostartManager:
    def __init__(self, script_path: str | None = None):
        self.script_path = Path(script_path).resolve() if script_path else Path(__file__).resolve().parent / "main.py"

    @property
    def file_path(self) -> Path:
        return AUTOSTART_FILE

    def is_enabled(self) -> bool:
        return self.file_path.exists()

    def enable(self) -> None:
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        exec_command = self._build_exec_command()
        self.file_path.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Zorin Desktop Studio Autoload",
                    "Name[tr]=Zorin Masaüstü Stüdyo Otomatik Yükleme",
                    "Comment=Restore the selected desktop layout at login",
                    "Comment[tr]=Seçili masaüstü düzenini oturum açılışında geri yükle",
                    f"Exec={exec_command}",
                    "Terminal=false",
                    "X-GNOME-Autostart-enabled=true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def disable(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink()

    def _build_exec_command(self) -> str:
        installed_command = Path("/usr/bin/zorin-icon-settings")
        if installed_command.exists():
            return shlex.join([str(installed_command), "--restore-startup-layout"])
        return shlex.join([sys.executable, str(self.script_path), "--restore-startup-layout"])


class WatcherAutostartManager:
    """Masaüstü değişikliklerini arka planda izleyen servis için autostart yöneticisi."""

    def __init__(self, script_path: str | None = None):
        self.script_path = Path(script_path).resolve() if script_path else Path(__file__).resolve().parent / "main.py"

    @property
    def file_path(self) -> Path:
        return WATCHER_AUTOSTART_FILE

    def is_enabled(self) -> bool:
        return self.file_path.exists()

    def enable(self) -> None:
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        exec_command = self._build_exec_command()
        self.file_path.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Zorin Desktop Studio Watcher",
                    "Name[tr]=Zorin Masaüstü Stüdyo İzleyici",
                    "Comment=Watch desktop for changes and restore the selected layout automatically",
                    "Comment[tr]=Masaüstü değişikliklerini izle ve seçili düzeni otomatik geri yükle",
                    f"Exec={exec_command}",
                    "Terminal=false",
                    "X-GNOME-Autostart-enabled=true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def disable(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink()

    def _build_exec_command(self) -> str:
        installed_command = Path("/usr/bin/zorin-icon-settings")
        if installed_command.exists():
            return shlex.join([str(installed_command), "--watch-desktop"])
        return shlex.join([sys.executable, str(self.script_path), "--watch-desktop"])