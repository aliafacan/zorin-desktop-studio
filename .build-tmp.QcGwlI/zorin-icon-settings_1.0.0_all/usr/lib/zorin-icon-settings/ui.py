#!/usr/bin/env python3
"""GTK arayuzu."""

from __future__ import annotations

from collections.abc import Callable
import os
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # pyright: ignore[reportMissingModuleSource]

from backend import AuthRequiredError, BackendError, IconSettingsBackend, SessionState
from constants import APP_ICON_NAME, CUSTOM_SETTING, PREVIEW_DEBOUNCE_MS, IconValues
from desktop_entries import DesktopEntryInfo, DesktopEntryStore
from i18n import t, translate_backend_message
from preferences import PreferencesStore
from theme import get_theme_css


class IconSettingsWindow(Gtk.Window):
    def __init__(self, backend: IconSettingsBackend, preferences_store: PreferencesStore):
        self.preferences_store = preferences_store
        self.preferences = self.preferences_store.load()
        super().__init__(title=t(self.preferences.language, "app_title"))
        self.backend = backend
        self.desktop_store = DesktopEntryStore()
        self.revert_state = self.backend.load_state()
        self.last_preview_state = self.revert_state
        self.preview_source_id = None
        self.has_unsaved_preview = False
        self.is_updating_sliders = False
        self.is_refreshing_selectors = False
        self.css_provider = Gtk.CssProvider()
        self.selected_desktop_path: str | None = None

        self.set_default_size(760, 620)
        self.set_icon_name(APP_ICON_NAME)
        self.set_border_width(20)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(True)
        self.connect("delete-event", self.on_delete_event)
        self.get_style_context().add_class("icon-settings-window")

        self._build_ui()
        self._set_slider_values(self.revert_state.effective_values)
        self._update_value_labels()
        self._apply_theme()
        self._refresh_texts()
        self._set_status(t(self.preferences.language, "status_ready"), "#666666")

    def _ask_sudo_password(self, retry: bool) -> str | None:
        dialog = Gtk.Dialog(
            title=t(self.preferences.language, "password_title"),
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.add_button(t(self.preferences.language, "password_cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(t(self.preferences.language, "password_continue"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        message = (
            t(self.preferences.language, "password_message")
            if not retry
            else t(self.preferences.language, "password_retry")
        )
        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_xalign(0)
        content.pack_start(label, False, False, 0)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_activates_default(True)
        entry.set_placeholder_text(t(self.preferences.language, "password_placeholder"))
        content.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        password = entry.get_text()
        dialog.destroy()

        if response != Gtk.ResponseType.OK:
            return None
        return password

    def _run_with_auth_retry(self, action: Callable[[], None]) -> bool:
        retry = False
        while True:
            try:
                action()
                return True
            except AuthRequiredError as exc:
                password = self._ask_sudo_password(retry=retry or exc.password_failed)
                if password is None:
                    self._set_status(t(self.preferences.language, "status_cancelled"), "#cc7a00")
                    return False
                self.backend.set_sudo_password(password)
                retry = True
            except BackendError as exc:
                self._set_status(translate_backend_message(self.preferences.language, str(exc)), "red")
                return False

    def _build_ui(self) -> None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.add(vbox)

        self.menu_bar = Gtk.MenuBar()
        vbox.pack_start(self.menu_bar, False, False, 0)

        self.sections_menu_item = Gtk.MenuItem()
        self.sections_menu = Gtk.Menu()
        self.sections_menu_item.set_submenu(self.sections_menu)
        self.menu_bar.append(self.sections_menu_item)

        self.icon_settings_menu_item = Gtk.MenuItem()
        self.icon_settings_menu_item.connect("activate", self.on_open_page, 0)
        self.sections_menu.append(self.icon_settings_menu_item)

        self.desktop_entries_menu_item = Gtk.MenuItem()
        self.desktop_entries_menu_item.connect("activate", self.on_open_page, 1)
        self.sections_menu.append(self.desktop_entries_menu_item)

        self.actions_menu_item = Gtk.MenuItem()
        self.actions_menu = Gtk.Menu()
        self.actions_menu_item.set_submenu(self.actions_menu)
        self.menu_bar.append(self.actions_menu_item)

        self.refresh_entries_menu_item = Gtk.MenuItem()
        self.refresh_entries_menu_item.connect("activate", self.on_reload_desktop_entries)
        self.actions_menu.append(self.refresh_entries_menu_item)

        self.pages = Gtk.Notebook()
        self.pages.set_show_tabs(False)
        self.pages.set_show_border(False)
        vbox.pack_start(self.pages, True, True, 0)

        settings_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.pages.append_page(settings_page, Gtk.Label())

        desktop_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.pages.append_page(desktop_page, Gtk.Label())

        self._build_settings_page(settings_page)
        self._build_desktop_entries_page(desktop_page)

    def _build_settings_page(self, container: Gtk.Box) -> None:
        vbox = container

        self.title_label = Gtk.Label()
        vbox.pack_start(self.title_label, False, False, 5)

        self.subtitle_label = Gtk.Label()
        self.subtitle_label.set_line_wrap(True)
        self.subtitle_label.set_justify(Gtk.Justification.CENTER)
        self.subtitle_label.get_style_context().add_class("dim-label")
        vbox.pack_start(self.subtitle_label, False, False, 0)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)

        self.theme_caption = Gtk.Label()
        self.theme_combo = Gtk.ComboBoxText()
        self.theme_combo.connect("changed", self.on_theme_changed)
        controls_box.pack_start(self.theme_caption, False, False, 0)
        controls_box.pack_start(self.theme_combo, False, False, 0)

        self.language_caption = Gtk.Label()
        self.language_combo = Gtk.ComboBoxText()
        self.language_combo.connect("changed", self.on_language_changed)
        controls_box.pack_start(self.language_caption, False, False, 0)
        controls_box.pack_start(self.language_combo, False, False, 0)

        vbox.pack_start(controls_box, False, False, 0)

        vbox.pack_start(Gtk.Separator(), False, False, 0)

        self.size_slider, self.size_value_label = self._build_slider_section(
            vbox,
            title_key="icon_size",
            minimum=24,
            maximum=128,
            marks=((36, "tiny"), (48, "small"), (64, "standard"), (96, "large")),
        )
        self.width_slider, self.width_value_label = self._build_slider_section(
            vbox,
            title_key="horizontal_spacing",
            minimum=60,
            maximum=180,
        )
        self.height_slider, self.height_value_label = self._build_slider_section(
            vbox,
            title_key="vertical_spacing",
            minimum=60,
            maximum=180,
        )

        for slider in (self.size_slider, self.width_slider, self.height_slider):
            slider.connect("value-changed", self.on_slider_changed)

        vbox.pack_start(Gtk.Separator(), False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.reset_btn = Gtk.Button()
        self.reset_btn.get_style_context().add_class("destructive-action")
        self.reset_btn.connect("clicked", self.on_reset)
        btn_box.pack_start(self.reset_btn, False, False, 0)

        self.apply_btn = Gtk.Button()
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply)
        btn_box.pack_start(self.apply_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 10)

        self.status = Gtk.Label(label="")
        self.status.set_line_wrap(True)
        self.status.set_justify(Gtk.Justification.CENTER)
        vbox.pack_start(self.status, False, False, 0)

    def _build_desktop_entries_page(self, container: Gtk.Box) -> None:
        self.desktop_title_label = Gtk.Label()
        self.desktop_title_label.set_xalign(0)
        container.pack_start(self.desktop_title_label, False, False, 0)

        self.desktop_subtitle_label = Gtk.Label()
        self.desktop_subtitle_label.set_xalign(0)
        self.desktop_subtitle_label.set_line_wrap(True)
        self.desktop_subtitle_label.get_style_context().add_class("dim-label")
        container.pack_start(self.desktop_subtitle_label, False, False, 0)

        content = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        container.pack_start(content, True, True, 0)

        left_frame = Gtk.Frame()
        content.add1(left_frame)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left_box.set_border_width(10)
        left_frame.add(left_box)

        self.desktop_list_title = Gtk.Label()
        self.desktop_list_title.set_xalign(0)
        left_box.pack_start(self.desktop_list_title, False, False, 0)

        self.desktop_list_store = Gtk.ListStore(str, str, str)
        self.desktop_tree = Gtk.TreeView(model=self.desktop_list_store)
        self.desktop_tree.set_headers_visible(False)
        self.desktop_tree.get_selection().connect("changed", self.on_desktop_entry_selected)

        icon_renderer = Gtk.CellRendererPixbuf()
        text_renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn()
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "icon-name", 1)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", 2)
        self.desktop_tree.append_column(column)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.desktop_tree)
        left_box.pack_start(scroller, True, True, 0)

        self.reload_desktop_btn = Gtk.Button()
        self.reload_desktop_btn.connect("clicked", self.on_reload_desktop_entries)
        left_box.pack_start(self.reload_desktop_btn, False, False, 0)

        right_frame = Gtk.Frame()
        content.add2(right_frame)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_box.set_border_width(10)
        right_frame.add(right_box)

        self.desktop_details_title = Gtk.Label()
        self.desktop_details_title.set_xalign(0)
        right_box.pack_start(self.desktop_details_title, False, False, 0)

        self.desktop_dir_label = Gtk.Label()
        self.desktop_dir_label.set_xalign(0)
        self.desktop_dir_label.set_line_wrap(True)
        self.desktop_dir_label.get_style_context().add_class("dim-label")
        right_box.pack_start(self.desktop_dir_label, False, False, 0)

        self.desktop_icon_preview = Gtk.Image.new_from_icon_name("application-x-desktop", Gtk.IconSize.DIALOG)
        right_box.pack_start(self.desktop_icon_preview, False, False, 0)

        form = Gtk.Grid(column_spacing=10, row_spacing=10)
        right_box.pack_start(form, False, False, 0)

        self.desktop_display_name_label = Gtk.Label()
        self.desktop_display_name_label.set_xalign(0)
        self.desktop_file_name_label = Gtk.Label()
        self.desktop_file_name_label.set_xalign(0)
        self.desktop_icon_label = Gtk.Label()
        self.desktop_icon_label.set_xalign(0)
        self.desktop_exec_label = Gtk.Label()
        self.desktop_exec_label.set_xalign(0)
        self.desktop_comment_label = Gtk.Label()
        self.desktop_comment_label.set_xalign(0)

        self.desktop_display_name_entry = Gtk.Entry()
        self.desktop_file_name_entry = Gtk.Entry()
        self.desktop_icon_entry = Gtk.Entry()
        self.desktop_icon_entry.connect("changed", self.on_icon_entry_changed)
        self.desktop_exec_entry = Gtk.Entry()
        self.desktop_comment_entry = Gtk.Entry()

        form.attach(self.desktop_display_name_label, 0, 0, 1, 1)
        form.attach(self.desktop_display_name_entry, 1, 0, 1, 1)
        form.attach(self.desktop_file_name_label, 0, 1, 1, 1)
        form.attach(self.desktop_file_name_entry, 1, 1, 1, 1)
        form.attach(self.desktop_icon_label, 0, 2, 1, 1)

        icon_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_row.pack_start(self.desktop_icon_entry, True, True, 0)
        self.desktop_browse_icon_btn = Gtk.Button()
        self.desktop_browse_icon_btn.connect("clicked", self.on_choose_icon)
        icon_row.pack_start(self.desktop_browse_icon_btn, False, False, 0)
        self.desktop_clear_icon_btn = Gtk.Button()
        self.desktop_clear_icon_btn.connect("clicked", self.on_clear_icon)
        icon_row.pack_start(self.desktop_clear_icon_btn, False, False, 0)
        form.attach(icon_row, 1, 2, 1, 1)

        form.attach(self.desktop_exec_label, 0, 3, 1, 1)
        form.attach(self.desktop_exec_entry, 1, 3, 1, 1)
        form.attach(self.desktop_comment_label, 0, 4, 1, 1)
        form.attach(self.desktop_comment_entry, 1, 4, 1, 1)

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_box.pack_start(button_row, False, False, 0)
        self.desktop_save_btn = Gtk.Button()
        self.desktop_save_btn.connect("clicked", self.on_save_desktop_entry)
        button_row.pack_start(self.desktop_save_btn, False, False, 0)

        self.desktop_status = Gtk.Label()
        self.desktop_status.set_xalign(0)
        self.desktop_status.set_line_wrap(True)
        right_box.pack_start(self.desktop_status, False, False, 0)

    def _build_slider_section(
        self,
        parent: Gtk.Box,
        title_key: str,
        minimum: int,
        maximum: int,
        marks: tuple[tuple[int, str], ...] = (),
    ):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        title_label = Gtk.Label()
        title_label.set_halign(Gtk.Align.START)
        header.pack_start(title_label, True, True, 0)

        value_label = Gtk.Label(label="")
        value_label.set_halign(Gtk.Align.END)
        header.pack_end(value_label, False, False, 0)

        section.pack_start(header, False, False, 0)

        controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        minus_button = Gtk.Button(label="−")
        minus_button.get_style_context().add_class("mini-adjust")
        minus_button.connect("clicked", self.on_adjust_slider, title_key, -1)
        controls_row.pack_start(minus_button, False, False, 0)

        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, minimum, maximum, 1)
        slider.set_draw_value(False)
        controls_row.pack_start(slider, True, True, 0)

        plus_button = Gtk.Button(label="+")
        plus_button.get_style_context().add_class("mini-adjust")
        plus_button.connect("clicked", self.on_adjust_slider, title_key, 1)
        controls_row.pack_start(plus_button, False, False, 0)

        section.pack_start(controls_row, False, False, 0)

        parent.pack_start(section, False, False, 0)
        slider._title_key = title_key
        slider._marks = marks
        slider._title_label = title_label
        return slider, value_label

    def _populate_selector_options(self) -> None:
        self.is_refreshing_selectors = True

        self.theme_combo.remove_all()
        self.theme_combo.append("dark", t(self.preferences.language, "theme_dark"))
        self.theme_combo.append("light", t(self.preferences.language, "theme_light"))
        self.theme_combo.set_active_id(self.preferences.theme)

        self.language_combo.remove_all()
        self.language_combo.append("tr", t(self.preferences.language, "language_tr"))
        self.language_combo.append("en", t(self.preferences.language, "language_en"))
        self.language_combo.set_active_id(self.preferences.language)

        self.is_refreshing_selectors = False

    def _apply_theme(self) -> None:
        self.css_provider.load_from_data(get_theme_css(self.preferences.theme).encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _save_preferences(self) -> None:
        self.preferences_store.save(self.preferences)

    def _set_desktop_status(self, message: str, color: str) -> None:
        safe_message = GLib.markup_escape_text(message)
        self.desktop_status.set_markup(f'<span foreground="{color}">{safe_message}</span>')

    def _refresh_texts(self) -> None:
        language = self.preferences.language
        self.sections_menu_item.set_label(t(language, "menu_sections"))
        self.actions_menu_item.set_label(t(language, "menu_actions"))
        self.icon_settings_menu_item.set_label(t(language, "menu_page_icon_settings"))
        self.desktop_entries_menu_item.set_label(t(language, "menu_page_desktop_entries"))
        self.refresh_entries_menu_item.set_label(t(language, "menu_refresh_entries"))
        self.set_title(t(language, "app_title"))
        self.title_label.set_markup(f'<span size="large" weight="bold">{t(language, "app_title")}</span>')
        self.subtitle_label.set_text(t(language, "subtitle"))
        self.theme_caption.set_text(f"{t(language, 'theme')}: ")
        self.language_caption.set_text(f"{t(language, 'language')}: ")
        self.reset_btn.set_label(f" {t(language, 'reset')} ")
        self.apply_btn.set_label(f" {t(language, 'apply')} ")
        self._populate_selector_options()
        self._refresh_slider_titles()
        self.desktop_title_label.set_markup(f'<span size="large" weight="bold">{t(language, "desktop_entries_title")}</span>')
        self.desktop_subtitle_label.set_text(t(language, "desktop_entries_subtitle"))
        self.desktop_list_title.set_markup(f"<b>{t(language, 'desktop_list')}</b>")
        self.desktop_details_title.set_markup(f"<b>{t(language, 'desktop_details')}</b>")
        self.desktop_dir_label.set_text(f"{t(language, 'desktop_path')}: {self.desktop_store.desktop_dir}")
        self.desktop_display_name_label.set_text(f"{t(language, 'desktop_display_name')}: ")
        self.desktop_file_name_label.set_text(f"{t(language, 'desktop_file_name')}: ")
        self.desktop_icon_label.set_text(f"{t(language, 'desktop_icon')}: ")
        self.desktop_exec_label.set_text(f"{t(language, 'desktop_exec')}: ")
        self.desktop_comment_label.set_text(f"{t(language, 'desktop_comment')}: ")
        self.desktop_browse_icon_btn.set_label(t(language, "desktop_browse_icon"))
        self.desktop_clear_icon_btn.set_label(t(language, "desktop_icon_clear"))
        self.desktop_save_btn.set_label(t(language, "desktop_save"))
        self.reload_desktop_btn.set_label(t(language, "desktop_reload"))
        if not self.selected_desktop_path:
            self._set_desktop_status(t(language, "desktop_select_hint"), "#666666")
        self.reload_desktop_entries(preserve_selection=True)

    def _refresh_slider_titles(self) -> None:
        for slider in (self.size_slider, self.width_slider, self.height_slider):
            slider._title_label.set_markup(f"<b>{t(self.preferences.language, slider._title_key)}</b>")
            self._refresh_slider_marks(slider)

    def _refresh_slider_marks(self, slider: Gtk.Scale) -> None:
        clear_marks = getattr(slider, "clear_marks", None)
        if callable(clear_marks):
            clear_marks()
        for position, label_key in slider._marks:
            slider.add_mark(position, Gtk.PositionType.BOTTOM, t(self.preferences.language, label_key))

    def _set_desktop_form_enabled(self, enabled: bool) -> None:
        for widget in (
            self.desktop_display_name_entry,
            self.desktop_file_name_entry,
            self.desktop_icon_entry,
            self.desktop_exec_entry,
            self.desktop_comment_entry,
            self.desktop_browse_icon_btn,
            self.desktop_clear_icon_btn,
            self.desktop_save_btn,
        ):
            widget.set_sensitive(enabled)

    def _fill_desktop_form(self, entry: DesktopEntryInfo) -> None:
        self.selected_desktop_path = entry.path
        self.desktop_display_name_entry.set_text(entry.display_name)
        self.desktop_file_name_entry.set_text(entry.file_name)
        self.desktop_icon_entry.set_text(entry.icon)
        self.desktop_exec_entry.set_text(entry.exec_command)
        self.desktop_comment_entry.set_text(entry.comment)
        self._update_icon_preview(entry.icon)
        self._set_desktop_form_enabled(True)

    def _clear_desktop_form(self) -> None:
        self.selected_desktop_path = None
        self.desktop_display_name_entry.set_text("")
        self.desktop_file_name_entry.set_text("")
        self.desktop_icon_entry.set_text("")
        self.desktop_exec_entry.set_text("")
        self.desktop_comment_entry.set_text("")
        self._update_icon_preview("")
        self._set_desktop_form_enabled(False)

    def _update_icon_preview(self, icon_value: str) -> None:
        icon_value = icon_value.strip()
        if icon_value and os.path.exists(icon_value):
            self.desktop_icon_preview.set_from_file(icon_value)
            return
        if icon_value:
            self.desktop_icon_preview.set_from_icon_name(icon_value, Gtk.IconSize.DIALOG)
            return
        self.desktop_icon_preview.set_from_icon_name("application-x-desktop", Gtk.IconSize.DIALOG)

    def reload_desktop_entries(self, preserve_selection: bool = False) -> None:
        selected_path = self.selected_desktop_path if preserve_selection else None
        self.desktop_list_store.clear()
        entries = self.desktop_store.list_entries()

        if not entries:
            self._clear_desktop_form()
            self._set_desktop_status(t(self.preferences.language, "desktop_empty"), "#cc7a00")
            return

        first_path = None
        target_iter = None
        for entry in entries:
            icon_name = entry.icon if entry.icon and not os.path.exists(entry.icon) else "application-x-desktop"
            tree_iter = self.desktop_list_store.append([entry.path, icon_name, entry.display_name])
            if first_path is None:
                first_path = entry.path
            if selected_path and entry.path == selected_path:
                target_iter = tree_iter

        selection = self.desktop_tree.get_selection()
        if target_iter is not None:
            selection.select_iter(target_iter)
        elif first_path is not None:
            selection.select_path(Gtk.TreePath.new_from_indices([0]))
        self._set_desktop_status(t(self.preferences.language, "desktop_select_hint"), "#666666")

    def _slider_for_key(self, title_key: str) -> Gtk.Scale:
        slider_map = {
            "icon_size": self.size_slider,
            "horizontal_spacing": self.width_slider,
            "vertical_spacing": self.height_slider,
        }
        return slider_map[title_key]

    def _step_slider(self, slider: Gtk.Scale, delta: int) -> None:
        adjustment = slider.get_adjustment()
        step = int(adjustment.get_step_increment()) or 1
        lower = int(adjustment.get_lower())
        upper = int(adjustment.get_upper())
        next_value = int(slider.get_value()) + (delta * step)
        slider.set_value(max(lower, min(upper, next_value)))

    def _set_slider_values(self, values: IconValues) -> None:
        self.is_updating_sliders = True
        self.size_slider.set_value(values.size)
        self.width_slider.set_value(values.width)
        self.height_slider.set_value(values.height)
        self.is_updating_sliders = False

    def _current_values(self) -> IconValues:
        return IconValues(
            size=int(self.size_slider.get_value()),
            width=int(self.width_slider.get_value()),
            height=int(self.height_slider.get_value()),
        )

    def _update_value_labels(self) -> None:
        values = self._current_values()
        self.size_value_label.set_text(f"{values.size} px")
        self.width_value_label.set_text(f"{values.width} px")
        self.height_value_label.set_text(f"{values.height} px")

    def _set_status(self, message: str, color: str) -> None:
        safe_message = GLib.markup_escape_text(message)
        self.status.set_markup(f'<span foreground="{color}">{safe_message}</span>')

    def _schedule_preview(self) -> None:
        if self.preview_source_id is not None:
            GLib.source_remove(self.preview_source_id)
        self.preview_source_id = GLib.timeout_add(PREVIEW_DEBOUNCE_MS, self._run_live_preview)
        self._set_status(t(self.preferences.language, "status_preview_pending"), "#666666")

    def _run_live_preview(self):
        self.preview_source_id = None
        values = self._current_values()

        if self._preview_matches_revert_state(values):
            self.has_unsaved_preview = False
            self.last_preview_state = self.revert_state
            self._set_status(t(self.preferences.language, "status_saved_state"), "#666666")
            return False

        if not self._run_with_auth_retry(lambda: self.backend.preview(values)):
            return False

        self.last_preview_state = SessionState(
            active_setting=CUSTOM_SETTING,
            custom_values=values,
            effective_values=values,
        )
        self.has_unsaved_preview = True
        self._set_status(t(self.preferences.language, "status_preview_done"), "#1f7a1f")
        return False

    def _flush_preview(self) -> None:
        if self.preview_source_id is not None:
            GLib.source_remove(self.preview_source_id)
            self.preview_source_id = None
            self._run_live_preview()

    def _preview_matches_revert_state(self, values: IconValues) -> bool:
        if self.revert_state.active_setting != CUSTOM_SETTING:
            return False
        return values == self.revert_state.custom_values

    def on_slider_changed(self, _slider: Gtk.Scale) -> None:
        self._update_value_labels()
        if self.is_updating_sliders:
            return
        self._schedule_preview()

    def on_apply(self, _button: Gtk.Button) -> None:
        self._flush_preview()
        values = self._current_values()

        committed_state: SessionState | None = None

        def commit_action() -> None:
            nonlocal committed_state
            committed_state = self.backend.commit(values)

        if not self._run_with_auth_retry(commit_action):
            return

        self.revert_state = committed_state or self.revert_state
        self.last_preview_state = self.revert_state
        self.has_unsaved_preview = False
        self._set_status(t(self.preferences.language, "status_saved"), "#1f7a1f")

    def on_reset(self, _button: Gtk.Button) -> None:
        self._set_slider_values(IconValues())
        self._update_value_labels()
        self._schedule_preview()
        self._set_status(t(self.preferences.language, "status_defaults_selected"), "#cc7a00")

    def on_adjust_slider(self, _button: Gtk.Button, title_key: str, delta: int) -> None:
        self._step_slider(self._slider_for_key(title_key), delta)

    def on_open_page(self, _item: Gtk.MenuItem, page_index: int) -> None:
        self.pages.set_current_page(page_index)

    def on_reload_desktop_entries(self, *_args) -> None:
        self.reload_desktop_entries(preserve_selection=True)

    def on_desktop_entry_selected(self, selection: Gtk.TreeSelection) -> None:
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            self._clear_desktop_form()
            self._set_desktop_status(t(self.preferences.language, "desktop_select_hint"), "#666666")
            return

        path = model.get_value(tree_iter, 0)
        entry = self.desktop_store.load_entry(path)
        self._fill_desktop_form(entry)
        self._set_desktop_status(t(self.preferences.language, "desktop_select_hint"), "#666666")

    def on_icon_entry_changed(self, entry: Gtk.Entry) -> None:
        self._update_icon_preview(entry.get_text())

    def on_choose_icon(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserDialog(
            title=t(self.preferences.language, "desktop_icon_dialog"),
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button(t(self.preferences.language, "password_cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(t(self.preferences.language, "password_continue"), Gtk.ResponseType.OK)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected = dialog.get_filename()
            if selected:
                self.desktop_icon_entry.set_text(selected)
        dialog.destroy()

    def on_clear_icon(self, _button: Gtk.Button) -> None:
        self.desktop_icon_entry.set_text("")

    def on_save_desktop_entry(self, _button: Gtk.Button) -> None:
        if not self.selected_desktop_path:
            self._set_desktop_status(t(self.preferences.language, "desktop_select_hint"), "#cc7a00")
            return

        try:
            saved = self.desktop_store.save_entry(
                original_path=self.selected_desktop_path,
                file_name=self.desktop_file_name_entry.get_text(),
                display_name=self.desktop_display_name_entry.get_text(),
                icon=self.desktop_icon_entry.get_text(),
                exec_command=self.desktop_exec_entry.get_text(),
                comment=self.desktop_comment_entry.get_text(),
            )
        except FileExistsError:
            self._set_desktop_status(t(self.preferences.language, "desktop_conflict"), "red")
            return
        except OSError as exc:
            self._set_desktop_status(str(exc), "red")
            return

        self.selected_desktop_path = saved.path
        self.reload_desktop_entries(preserve_selection=True)
        self._set_desktop_status(t(self.preferences.language, "desktop_saved"), "#1f7a1f")

    def on_theme_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self.is_refreshing_selectors:
            return
        theme = combo.get_active_id()
        if theme not in {"dark", "light"}:
            return
        self.preferences.theme = theme
        self._apply_theme()
        self._save_preferences()

    def on_language_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self.is_refreshing_selectors:
            return
        language = combo.get_active_id()
        if language not in {"tr", "en"}:
            return
        self.preferences.language = language
        self._refresh_texts()
        self._save_preferences()

    def on_delete_event(self, _widget: Gtk.Widget, _event) -> bool:
        if self.preview_source_id is not None:
            GLib.source_remove(self.preview_source_id)
            self.preview_source_id = None

        if not self.has_unsaved_preview:
            return False

        if not self._run_with_auth_retry(lambda: self.backend.restore_state(self.revert_state)):
            self._set_status(t(self.preferences.language, "status_restore_failed"), "red")
            return True

        return False
