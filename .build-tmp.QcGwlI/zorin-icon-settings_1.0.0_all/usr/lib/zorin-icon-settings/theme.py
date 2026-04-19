#!/usr/bin/env python3
"""GTK CSS temaları."""


def get_theme_css(theme_name: str) -> str:
    palettes = {
        "dark": {
            "window_bg": "#1f262d",
            "surface": "#26313a",
            "surface_alt": "#2d3944",
            "text": "#e8f1f7",
            "muted": "#9fb0bc",
            "border": "#364651",
            "accent": "#63b3ed",
            "accent_text": "#081723",
            "danger": "#ff7f7f",
            "danger_text": "#2f0e0e",
            "input_bg": "#182026",
            "input_border": "#4c5d69",
        },
        "light": {
            "window_bg": "#f3f7fb",
            "surface": "#ffffff",
            "surface_alt": "#edf4fa",
            "text": "#173041",
            "muted": "#5f7483",
            "border": "#cfdae4",
            "accent": "#5bb8f0",
            "accent_text": "#103041",
            "danger": "#ff9d9d",
            "danger_text": "#4b1616",
            "input_bg": "#ffffff",
            "input_border": "#9fb6c8",
        },
    }
    colors = palettes.get(theme_name, palettes["dark"])
    return f"""
window.icon-settings-window,
window.icon-settings-window box,
window.icon-settings-window separator,
window.icon-settings-window menubar,
window.icon-settings-window menu,
window.icon-settings-window treeview,
window.icon-settings-window scrolledwindow {{
    background-color: {colors['window_bg']};
    color: {colors['text']};
}}

window.icon-settings-window label {{
    color: {colors['text']};
}}

window.icon-settings-window menubar > menuitem {{
    color: {colors['text']};
    padding: 6px 10px;
}}

window.icon-settings-window menu menuitem {{
    color: {colors['text']};
}}

window.icon-settings-window .dim-label {{
    color: {colors['muted']};
}}

window.icon-settings-window button {{
    background: {colors['surface_alt']};
    color: {colors['text']};
    border-radius: 12px;
    border: 1px solid {colors['border']};
    box-shadow: none;
    padding: 8px 16px;
}}

window.icon-settings-window button:hover {{
    background: {colors['surface']};
}}

window.icon-settings-window button.suggested-action {{
    background: {colors['accent']};
    color: {colors['accent_text']};
    border-color: {colors['accent']};
}}

window.icon-settings-window button.suggested-action:hover {{
    background: shade({colors['accent']}, 1.08);
}}

window.icon-settings-window button.destructive-action {{
    background: {colors['danger']};
    color: {colors['danger_text']};
    border-color: {colors['danger']};
}}

window.icon-settings-window entry {{
    background: {colors['input_bg']};
    color: {colors['text']};
    border-radius: 10px;
    border: 1px solid {colors['input_border']};
}}

window.icon-settings-window combobox,
window.icon-settings-window combobox button,
window.icon-settings-window combobox box.linked,
window.icon-settings-window combobox box {{
    background: transparent;
    box-shadow: none;
    border: none;
}}

window.icon-settings-window combobox button.combo,
window.icon-settings-window combobox button {{
    background: {colors['input_bg']};
    color: {colors['text']};
    border-radius: 10px;
    border: 1px solid {colors['input_border']};
    padding: 6px 12px;
}}

window.icon-settings-window combobox button.combo:hover,
window.icon-settings-window combobox button:hover {{
    background: {colors['surface']};
}}

window.icon-settings-window combobox arrow {{
    color: {colors['muted']};
}}

window.icon-settings-window button.mini-adjust {{
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    border-radius: 999px;
    font-weight: bold;
    background: {colors['surface_alt']};
}}

window.icon-settings-window treeview.view {{
    background: {colors['surface']};
    color: {colors['text']};
    border: 1px solid {colors['border']};
}}

window.icon-settings-window treeview.view:selected,
window.icon-settings-window treeview.view:selected:focus {{
    background: {colors['accent']};
    color: {colors['accent_text']};
}}

window.icon-settings-window frame {{
    border-color: {colors['border']};
}}

window.icon-settings-window scale trough {{
    background: {colors['surface_alt']};
    border-radius: 999px;
    min-height: 6px;
}}

window.icon-settings-window scale highlight {{
    background: {colors['accent']};
    border-radius: 999px;
}}

window.icon-settings-window scale slider {{
    background: {colors['accent']};
    border: 2px solid {colors['surface']};
    min-width: 18px;
    min-height: 18px;
    border-radius: 999px;
}}
"""