#!/usr/bin/env python3
"""Zorin masaüstü ikon yerleşimlerini okur ve geri yükler."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess


POSITION_ATTR = "metadata::nautilus-icon-position"


class LayoutError(RuntimeError):
    """Masaüstü düzen işlemleri hatası."""


@dataclass(frozen=True)
class LayoutSnapshot:
    layout: dict[str, str]
    found_count: int


class DesktopLayoutService:
    def __init__(self):
        self.host_bridge_available = self._detect_host_bridge()
        self.desktop_dir = self._detect_desktop_dir()

    def capture_current_layout(self) -> LayoutSnapshot:
        layout: dict[str, str] = {}
        for path in self._desktop_items():
            pos = self._get_position(path)
            if pos:
                layout[path.name] = pos

        if not layout:
            raise LayoutError("NO_COORD")

        return LayoutSnapshot(layout=layout, found_count=len(layout))

    def restore_layout(self, layout: dict[str, str]) -> int:
        restored = 0
        for name, pos in layout.items():
            path = self.desktop_dir / name
            if path.exists() and self._set_position(path, pos):
                restored += 1
        self.refresh_desktop_icons()
        return restored

    def refresh_desktop_icons(self) -> None:
        self._run_command(["pkill", "-f", "ding.js"], check=False)

    def _desktop_items(self) -> list[Path]:
        if not self.desktop_dir.exists():
            return []
        return [item for item in self.desktop_dir.iterdir() if not item.name.startswith(".")]

    def _get_position(self, path: Path) -> str | None:
        result = self._run_command(["gio", "info", "-a", POSITION_ATTR, str(path)], check=False)
        output = f"{result.stdout}\n{result.stderr}"
        for line in output.splitlines():
            if POSITION_ATTR in line and ":" in line:
                pos = line.split(":")[-1].strip()
                if re.match(r"^\d+,\d+$", pos):
                    return pos
        return None

    def _set_position(self, path: Path, pos: str) -> bool:
        result = self._run_command(["gio", "set", "-t", "string", str(path), POSITION_ATTR, pos], check=False)
        return result.returncode == 0

    def _detect_desktop_dir(self) -> Path:
        result = self._run_command(
            ["sh", "-lc", 'xdg-user-dir DESKTOP 2>/dev/null || printf "%s/Desktop\\n" "$HOME"'],
            check=False,
            host_preferred=True,
        )
        desktop = result.stdout.strip()
        return Path(desktop) if desktop else Path.home() / "Desktop"

    def _detect_host_bridge(self) -> bool:
        if not shutil.which("flatpak-spawn"):
            return False
        result = subprocess.run(
            ["flatpak-spawn", "--host", "true"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0

    def _run_command(
        self,
        command: list[str],
        check: bool,
        host_preferred: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        use_host = self.host_bridge_available and (host_preferred or command[0] in {"gio", "pkill"})
        full_command = ["flatpak-spawn", "--host", *command] if use_host else command
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise LayoutError(stderr)
        return result
