#!/usr/bin/env python3
"""Uygulama giriş noktası."""

from __future__ import annotations

import argparse

from backend import BackendError, IconSettingsBackend
from constants import APP_ICON_NAME
from desktop_layouts import DesktopLayoutService, LayoutError
from i18n import t, translate_backend_message
from layout_store import LayoutStore
from preferences import PreferencesStore


def show_error_dialog(language: str, message: str) -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk  # pyright: ignore[reportMissingModuleSource]

    dialog = Gtk.MessageDialog(
        transient_for=None,
        flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.CLOSE,
        text=t(language, "app_title"),
    )
    dialog.format_secondary_text(translate_backend_message(language, message))
    dialog.run()
    dialog.destroy()


def restore_startup_layout(preferences_store: PreferencesStore) -> int:
    preferences = preferences_store.load()
    if not preferences.startup_layout_key:
        return 0

    record = LayoutStore().get_layout(preferences.startup_layout_key)
    if record is None:
        return 0

    try:
        DesktopLayoutService().restore_layout(record.layout)
    except LayoutError:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--restore-startup-layout", action="store_true")
    args, _unknown = parser.parse_known_args()

    preferences_store = PreferencesStore()
    preferences = preferences_store.load()
    if args.restore_startup_layout:
        return restore_startup_layout(preferences_store)

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk  # pyright: ignore[reportMissingModuleSource]
    from ui import IconSettingsWindow

    Gtk.Window.set_default_icon_name(APP_ICON_NAME)

    try:
        backend = IconSettingsBackend()
    except BackendError as exc:
        show_error_dialog(preferences.language, str(exc))
        return 1

    window = IconSettingsWindow(backend, preferences_store)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
