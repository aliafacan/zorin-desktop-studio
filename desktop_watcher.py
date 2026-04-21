#!/usr/bin/env python3
"""Masaüstü dizinini izler; dosya kaybolduğunda seçili düzeni yeniden uygular."""

from __future__ import annotations

from desktop_layouts import DesktopLayoutService, LayoutError
from layout_store import LayoutStore
from preferences import PreferencesStore

# Tetiklemeden sonra kaç ms beklenecek (birden fazla değişikliği birleştirmek için)
_DEBOUNCE_MS = 3000


class DesktopWatcher:
    """
    Masaüstü dizinini Gio.FileMonitor ile izler.
    startup_layout_key ayarlanmışsa, herhangi bir dosya değişikliğinde
    (silme, oluşturma, yeniden adlandırma) o düzeni otomatik olarak yeniden uygular.
    """

    def __init__(self, preferences_store: PreferencesStore) -> None:
        self._preferences_store = preferences_store
        self._layout_service = DesktopLayoutService()
        self._layout_store = LayoutStore()
        self._monitor = None
        self._debounce_id = None
        self._GLib = None

    # ── Genel Arayüz ──────────────────────────────────────────

    def start(self) -> None:
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib  # pyright: ignore[reportMissingModuleSource]
            self._GLib = GLib
            desktop_path = self._layout_service.desktop_dir
            gfile = Gio.File.new_for_path(str(desktop_path))
            self._monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect("changed", self._on_changed)
        except Exception:
            self._monitor = None

    def stop(self) -> None:
        if self._monitor is not None:
            self._monitor.cancel()
            self._monitor = None
        if self._debounce_id is not None and self._GLib is not None:
            self._GLib.source_remove(self._debounce_id)
            self._debounce_id = None

    # ── İç Mantık ─────────────────────────────────────────────

    def _on_changed(self, _monitor, _file, _other, event_type) -> None:
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio  # pyright: ignore[reportMissingModuleSource]
            relevant = {
                Gio.FileMonitorEvent.DELETED,
                Gio.FileMonitorEvent.CREATED,
                Gio.FileMonitorEvent.MOVED_IN,
                Gio.FileMonitorEvent.MOVED_OUT,
                Gio.FileMonitorEvent.RENAMED,
            }
            if event_type not in relevant:
                return
        except Exception:
            return

        prefs = self._preferences_store.load()
        if not prefs.startup_layout_key:
            return

        GLib = self._GLib
        if GLib is None:
            return

        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)

        self._debounce_id = GLib.timeout_add(
            _DEBOUNCE_MS,
            self._apply_layout,
            prefs.startup_layout_key,
        )

    def _apply_layout(self, key: str) -> bool:
        GLib = self._GLib
        self._debounce_id = None

        prefs = self._preferences_store.load()
        if prefs.startup_layout_key != key:
            return GLib.SOURCE_REMOVE if GLib else False

        record = self._layout_store.get_layout(key)
        if record is None:
            return GLib.SOURCE_REMOVE if GLib else False

        try:
            self._layout_service.restore_layout(record.layout)
        except LayoutError:
            pass

        return GLib.SOURCE_REMOVE if GLib else False
