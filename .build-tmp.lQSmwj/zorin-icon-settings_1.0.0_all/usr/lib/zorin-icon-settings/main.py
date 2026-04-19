#!/usr/bin/env python3
"""Uygulama giriş noktası."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # pyright: ignore[reportMissingModuleSource]

from backend import BackendError, IconSettingsBackend
from constants import APP_ICON_NAME
from i18n import t, translate_backend_message
from preferences import PreferencesStore
from ui import IconSettingsWindow


def show_error_dialog(language: str, message: str) -> None:
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


def main() -> int:
    Gtk.Window.set_default_icon_name(APP_ICON_NAME)
    preferences = PreferencesStore().load()
    try:
        backend = IconSettingsBackend()
    except BackendError as exc:
        show_error_dialog(preferences.language, str(exc))
        return 1

    window = IconSettingsWindow(backend, PreferencesStore())
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
