#!/usr/bin/env python3
"""Sabitler ve varsayılanlar."""

from dataclasses import dataclass


APP_TITLE = "Masaüstü Simge Ayarları"
APP_ICON_NAME = "zorin-desktop-studio"
SETTING_SCHEMA = "org.gnome.shell.extensions.zorin-desktop-icons"
SETTING_KEY = "icon-size"
CUSTOM_SETTING = "custom"
DEFAULT_SETTING = "standard"
PREVIEW_DEBOUNCE_MS = 250

ENUMS_CANDIDATES = [
    "/usr/share/gnome-shell/extensions/zorin-desktop-icons@zorinos.com/app/enums.js",
    "/usr/share/gnome-shell/extensions/desktop-icons-ng@rastersoft.com/app/enums.js",
]

SCHEMA_XML_CANDIDATES = [
    "/usr/share/glib-2.0/schemas/org.gnome.shell.extensions.zorin-desktop-icons.gschema.xml",
]


@dataclass(frozen=True)
class IconValues:
    size: int = 64
    width: int = 120
    height: int = 106
