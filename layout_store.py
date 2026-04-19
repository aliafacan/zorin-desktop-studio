#!/usr/bin/env python3
"""Masaüstü düzenlerini JSON olarak saklar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path


LAYOUTS_PATH = Path.home() / ".local" / "share" / "zorin-desktop-studio" / "layouts.json"


@dataclass(frozen=True)
class LayoutRecord:
    key: str
    name: str
    saved_at: str
    item_count: int
    layout: dict[str, str]


class LayoutStore:
    @property
    def save_path(self) -> Path:
        return LAYOUTS_PATH

    def load_all(self) -> list[LayoutRecord]:
        raw = self._load_raw()
        records = []
        for key, entry in raw.items():
            layout = entry.get("layout", {})
            records.append(
                LayoutRecord(
                    key=key,
                    name=entry.get("name", key),
                    saved_at=entry.get("saved_at", ""),
                    item_count=entry.get("item_count", len(layout)),
                    layout=layout,
                )
            )
        records.sort(key=lambda item: item.saved_at, reverse=True)
        return records

    def save_layout(self, name: str, layout: dict[str, str]) -> LayoutRecord:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key = self._slugify(name) or datetime.now().strftime("layout-%Y%m%d-%H%M%S")
        raw = self._load_raw()
        while key in raw:
            key = f"{key}-1"
        raw[key] = {
            "name": name,
            "saved_at": now,
            "item_count": len(layout),
            "layout": layout,
        }
        self._save_raw(raw)
        return LayoutRecord(key=key, name=name, saved_at=now, item_count=len(layout), layout=layout)

    def rename_layout(self, key: str, new_name: str) -> LayoutRecord:
        raw = self._load_raw()
        if key not in raw:
            raise KeyError(key)
        raw[key]["name"] = new_name
        self._save_raw(raw)
        entry = raw[key]
        layout = entry.get("layout", {})
        return LayoutRecord(key=key, name=new_name, saved_at=entry.get("saved_at", ""), item_count=entry.get("item_count", len(layout)), layout=layout)

    def delete_layout(self, key: str) -> None:
        raw = self._load_raw()
        if key in raw:
            del raw[key]
            self._save_raw(raw)

    def get_layout(self, key: str) -> LayoutRecord | None:
        for record in self.load_all():
            if record.key == key:
                return record
        return None

    def _load_raw(self) -> dict:
        if LAYOUTS_PATH.exists():
            try:
                with open(LAYOUTS_PATH, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception:
                return {}
        return {}

    def _save_raw(self, data: dict) -> None:
        os.makedirs(LAYOUTS_PATH.parent, exist_ok=True)
        with open(LAYOUTS_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def _slugify(self, name: str) -> str:
        result = []
        for char in name.strip().lower():
            if char.isalnum():
                result.append(char)
            elif char in {" ", "-", "_"}:
                result.append("-")
        return "".join(result).strip("-")
