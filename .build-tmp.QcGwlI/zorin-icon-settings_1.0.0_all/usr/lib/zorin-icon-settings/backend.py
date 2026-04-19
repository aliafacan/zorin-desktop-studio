#!/usr/bin/env python3
"""Sistem ayarlariyla haberlesen arka plan katmani."""

from __future__ import annotations

from dataclasses import dataclass
import glob
import json
import os
import re
import shutil
import subprocess

from constants import (
    CUSTOM_SETTING,
    ENUMS_CANDIDATES,
    SCHEMA_XML_CANDIDATES,
    SETTING_KEY,
    SETTING_SCHEMA,
    IconValues,
)


class BackendError(RuntimeError):
    """Ayar altyapisi hatasi."""


class AuthRequiredError(BackendError):
    """Ayricalikli islem icin parola gerekiyor."""

    def __init__(self, message: str, password_failed: bool = False):
        super().__init__(message)
        self.password_failed = password_failed


@dataclass(frozen=True)
class SessionState:
    active_setting: str
    custom_values: IconValues
    effective_values: IconValues


class IconSettingsBackend:
    def __init__(self):
        self.host_bridge_available = self._detect_host_bridge()
        self._sudo_password: str | None = None
        self.enums_path = self._resolve_enums_path()
        self.schema_xml_path = self._resolve_schema_xml_path()

    def set_sudo_password(self, password: str) -> None:
        self._sudo_password = password

    def clear_sudo_password(self) -> None:
        self._sudo_password = None

    def load_state(self) -> SessionState:
        value_maps = self.read_value_maps()
        active_setting = self.get_current_setting()
        custom_values = IconValues(
            size=value_maps["ICON_SIZE"].get(CUSTOM_SETTING, IconValues().size),
            width=value_maps["ICON_WIDTH"].get(CUSTOM_SETTING, IconValues().width),
            height=value_maps["ICON_HEIGHT"].get(CUSTOM_SETTING, IconValues().height),
        )

        if (
            active_setting in value_maps["ICON_SIZE"]
            and active_setting in value_maps["ICON_WIDTH"]
            and active_setting in value_maps["ICON_HEIGHT"]
        ):
            effective_values = IconValues(
                size=value_maps["ICON_SIZE"][active_setting],
                width=value_maps["ICON_WIDTH"][active_setting],
                height=value_maps["ICON_HEIGHT"][active_setting],
            )
        else:
            effective_values = custom_values

        return SessionState(
            active_setting=active_setting,
            custom_values=custom_values,
            effective_values=effective_values,
        )

    def preview(self, values: IconValues) -> None:
        self._ensure_custom_setting_available()
        self.write_custom_values(values)
        self.set_current_setting(CUSTOM_SETTING)
        self.refresh_desktop_icons()

    def commit(self, values: IconValues) -> SessionState:
        self.preview(values)
        return SessionState(
            active_setting=CUSTOM_SETTING,
            custom_values=values,
            effective_values=values,
        )

    def restore_state(self, state: SessionState) -> None:
        self.write_custom_values(state.custom_values)
        self.set_current_setting(state.active_setting)
        self.refresh_desktop_icons()

    def read_value_maps(self) -> dict[str, dict[str, int]]:
        content = self._read_text(self.enums_path)
        value_maps = {}
        for var_name in ("ICON_SIZE", "ICON_WIDTH", "ICON_HEIGHT"):
            match = re.search(rf"var {var_name} = (\{{.*?\}});", content, re.DOTALL)
            if not match:
                raise BackendError(f"{var_name} degeri enums.js icinde bulunamadi.")
            value_maps[var_name] = json.loads(match.group(1).replace("'", '"'))
        return value_maps

    def get_current_setting(self) -> str:
        result = self._run_command(
            ["gsettings", "get", SETTING_SCHEMA, SETTING_KEY],
            check=True,
        )
        return result.stdout.strip().strip("'")

    def set_current_setting(self, setting_name: str) -> None:
        self._run_command(
            ["gsettings", "set", SETTING_SCHEMA, SETTING_KEY, setting_name],
            check=True,
        )

    def write_custom_values(self, values: IconValues) -> None:
        content = self._read_text(self.enums_path)
        replacements = {
            "ICON_SIZE": values.size,
            "ICON_WIDTH": values.width,
            "ICON_HEIGHT": values.height,
        }

        for var_name, value in replacements.items():
            content = self._replace_custom_value(content, var_name, value)

        self._write_text(self.enums_path, content)

    def refresh_desktop_icons(self) -> None:
        try:
            self._run_command(
                ["pkill", "-f", "ding.js"],
                check=False,
            )
        except Exception as exc:
            raise BackendError(f"Masaustu ikonlari yenilenemedi: {exc}") from exc

    def _resolve_enums_path(self) -> str:
        dynamic_candidates = []
        for pattern in (
            "/usr/share/gnome-shell/extensions/*desktop-icons*/app/enums.js",
            os.path.expanduser("~/.local/share/gnome-shell/extensions/*desktop-icons*/app/enums.js"),
            os.path.expanduser("~/.local/share/gnome-shell/extensions/zorin-desktop-icons*/app/enums.js"),
        ):
            dynamic_candidates.extend(sorted(glob.glob(pattern)))

        for path in [*ENUMS_CANDIDATES, *dynamic_candidates]:
            if self._path_exists(path):
                return path

        raise BackendError(
            "Desktop icon enums.js dosyasi bulunamadi. Uzanti yolu farkliysa constants.py icindeki aday yollari guncelle."
        )

    def _resolve_schema_xml_path(self) -> str | None:
        for path in SCHEMA_XML_CANDIDATES:
            if self._path_exists(path):
                return path
        return None

    def _ensure_custom_setting_available(self) -> None:
        if self._custom_setting_exists():
            return

        if not self.schema_xml_path:
            raise BackendError(
                "GSettings icinde 'custom' secenegi yok ve sema XML dosyasi bulunamadi."
            )

        schema = self._read_text(self.schema_xml_path)
        if 'nick="custom"' not in schema:
            updated_schema = self._inject_custom_setting(schema)
            self._write_text(self.schema_xml_path, updated_schema)
            self._run_privileged_command(
                ["glib-compile-schemas", "/usr/share/glib-2.0/schemas/"]
            )

        if not self._custom_setting_exists():
            raise BackendError("'custom' ayari semaya eklenemedi.")

    def _custom_setting_exists(self) -> bool:
        current_setting = self.get_current_setting()
        if current_setting == CUSTOM_SETTING:
            return True

        result = self._run_command(
            ["gsettings", "range", SETTING_SCHEMA, SETTING_KEY],
            check=False,
        )
        return CUSTOM_SETTING in result.stdout

    def _inject_custom_setting(self, schema: str) -> str:
        if 'nick="custom"' in schema:
            return schema

        replacements = (
            '<value value="12" nick="p90"/>',
            '<value value="2" nick="large"/>',
        )

        for marker in replacements:
            if marker in schema:
                return schema.replace(
                    marker,
                    marker + '\n        <value value="13" nick="custom"/>',
                    1,
                )

        raise BackendError("Sema XML icinde uygun enum ekleme noktasi bulunamadi.")

    def _replace_custom_value(self, content: str, var_name: str, value: int) -> str:
        match = re.search(rf"var {var_name} = (\{{.*?\}});", content, re.DOTALL)
        if not match:
            raise BackendError(f"{var_name} blogu guncellenemedi.")

        data = json.loads(match.group(1).replace("'", '"'))
        data[CUSTOM_SETTING] = value
        ordered = ", ".join(f"'{key}': {item}" for key, item in data.items())
        return re.sub(
            rf"var {var_name} = \{{.*?\}};",
            f"var {var_name} = {{{ordered}}};",
            content,
            count=1,
            flags=re.DOTALL,
        )

    def _read_text(self, path: str) -> str:
        if self._path_exists_locally(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except OSError as exc:
                raise BackendError(f"{path} okunamadi: {exc}") from exc

        if self.host_bridge_available and self._path_exists_on_host(path):
            result = self._run_host_command(["cat", path], check=True)
            return result.stdout

        raise BackendError(f"{path} okunamadi: dosya bulunamadi.")

    def _write_text(self, path: str, content: str) -> None:
        if self._path_exists_locally(path) and os.access(path, os.W_OK):
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(content)
                return
            except OSError as exc:
                raise BackendError(f"{path} yazilamadi: {exc}") from exc

        if self.host_bridge_available and self._path_exists_on_host(path):
            self._write_host_text(path, content)
            return

        raise BackendError(f"{path} yazilamadi: uygun yazma yolu bulunamadi.")

    def _write_host_text(self, path: str, content: str) -> None:
        result = self._run_privileged_command(["tee", path], input_text=content)
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "bilinmeyen hata"
            raise BackendError(f"{path} sudo ile yazilamadi: {stderr}")

    def _run_command(self, command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        if self.host_bridge_available:
            return self._run_host_command(command, check)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "bilinmeyen hata"
            raise BackendError(f"Komut basarisiz oldu: {' '.join(command)}\n{stderr}")
        return result

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

    def _path_exists(self, path: str) -> bool:
        return self._path_exists_locally(path) or self._path_exists_on_host(path)

    def _path_exists_locally(self, path: str) -> bool:
        return os.path.exists(path)

    def _path_exists_on_host(self, path: str) -> bool:
        if not self.host_bridge_available:
            return False

        result = subprocess.run(
            ["flatpak-spawn", "--host", "test", "-e", path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0

    def _run_host_command(self, command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["flatpak-spawn", "--host", *command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "bilinmeyen hata"
            raise BackendError(f"Komut basarisiz oldu: {' '.join(command)}\n{stderr}")
        return result

    def _run_privileged_command(
        self,
        command: list[str],
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        sudo_probe = self._run_host_command(["sudo", "-n", "true"], check=False)
        if sudo_probe.returncode == 0:
            return self._run_host_command(["sudo", "-n", *command], check=False)

        if not self._sudo_password:
            raise AuthRequiredError(
                "Yonetici parolasi gerekiyor. Canli onizlemeyi uygulama icinden acmak icin parolayi gir.",
            )

        stdin_text = f"{self._sudo_password}\n"
        if input_text is not None:
            stdin_text += input_text

        result = subprocess.run(
            ["flatpak-spawn", "--host", "sudo", "-S", "-p", "", *command],
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().lower()
            if "password" in stderr or "try again" in stderr or "incorrect" in stderr:
                self.clear_sudo_password()
                raise AuthRequiredError(
                    "Yonetici parolasi hatali. Lutfen tekrar dene.",
                    password_failed=True,
                )
        return result
