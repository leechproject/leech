from dataclasses import dataclass

from modules.config.values import (Bool, BindType, Duration, Enum, Float, IconType, Int, PathType,
                                   PositionType, Text, Type)


@dataclass
class P:
    type: Type
    default: str = ""
    show: bool = True
    named: bool = False
    implemented: bool = True


@dataclass
class Rows:
    names: tuple


def now(type_, default=""):
    return P(type_, default, implemented=False)


def later(type_, default=""):
    return P(type_, default, show=False, implemented=False)


def named(default="y"):
    return P(Bool(), default, named=True)


PX = Int(0, 10000)
SIZE = Int(1, 10000)
COUNT = Int(0, 1000)

VARIABLES = ("BASE_DIR", "ASSETS_DIR", "STYLE_FILE", "WALLPAPERS_DIR")

SCHEMA = {
    "BASE_DIR": P(PathType()),
    "ASSETS_DIR": P(PathType(), 'BASE_DIR / "assets"'),
    "STYLE_FILE": P(PathType(), 'BASE_DIR / "style.css"'),
    "WALLPAPERS_DIR": P(PathType(), "~/Pictures/Wallpapers"),
    "ICON_FONT": P(PathType(pattern=True)),
    "GLOBAL_FONT": P(PathType(pattern=True)),
    "GLOBAL_ANIMATION_SPEED": P(Duration(), "220ms"),
    "outline-thickness": P(Int(1, 10), "1"),
    "vim-keybinds": P(Bool(), "n"),
    "wm": P(Text(), "hypr"),
    "bar": {
        "module-enabled": P(Bool(), "y"),
        "bar-width": P(SIZE, "60"),
        "position": P(Enum("left", "right", "top", "bottom"), "left"),
        "style": P(Enum("mono", "split"), "mono"),
        "undercover-module-enabled": P(Bool(), "n"),
        "launcher-btn": {
            "launcher-button-shown": P(Bool(), "y"),
            "outline": P(Bool(), "n"),
            "launcher-button-icon": P(IconType(), 'ASSETS_DIR / "launcher.png"'),
            "undercover": P(Bool(), "y"),
            "undercover-position": P(Enum("left", "center"), "center"),
            "undercover-icon": P(IconType(), 'ASSETS_DIR / "undercover.png"'),
            "launcher-icon-spacing": later(PX),
            "launcher-icon-size": P(SIZE, "18"),
        },
        "workspace": {
            "ws-shown": P(Int(1, 100), "10"),
            "ws-clickable": P(Bool(), "y"),
            "ws-style": P(Enum("digit", "roman", "chinese"), "digit"),
            "ws-empty-icon": P(IconType()),
            "ws-inuse-icon": P(IconType()),
            "ws-active-highlighting": P(Bool(), "y"),
            "ws-active-icon": P(IconType(), "ws-inuse-icon:invertcolor"),
            "outline": P(Bool(), "n"),
        },
        "tray": {
            "module-enabled": P(Bool(), "y"),
            "tray-shown": P(Bool(), "y"),
            "outline": P(Bool(), "n"),
            "undercover": P(Bool(), "y"),
            "tray-expand-by-icon-limit": P(COUNT, "4"),
            "tray-scrollable": P(Bool(), "y"),
            "tray-icon": P(IconType(), "\\uf077"),
        },
        "power-profiles-shown": P(Bool(), "y"),
        "power-profiles-outline": P(Bool(), "n"),
        "keyboard-layout-shown": P(Bool(), "y"),
        "keyboard-layout-outline": P(Bool(), "n"),
        "clock-shown": P(Bool(), "y"),
        "clock-outline": P(Bool(), "n"),
        "powerbutton-shown": P(Bool(), "y"),
        "powerbutton-outline": P(Bool(), "n"),
    },
    "frame": {
        "module-enabled": P(Bool(), "y"),
        "outline": P(Bool(), "n"),
        "include-bar": P(Bool(), "y"),
        "left": P(PX, "9"),
        "right": P(PX, "9"),
        "top": P(PX, "9"),
        "bottom": P(PX, "9"),
    },
    "notch": {
        "module-enabled": P(Bool(), "y"),
        "style": P(Enum("notch", "island"), "notch"),
        "position": P(Enum("top", "bottom"), "top"),
        "outline": P(Bool(), "n"),
        "width": later(SIZE),
        "height": later(SIZE),
        "hide-by-window": P(Bool(), "y"),
        "placeholder-text": P(Text(), "userhost"),
        "placeholder-spacing": P(PX, "5"),
        "placeholder-edge-spacing": P(PX, "5"),
        "expand": {
            "enable": P(Bool(), "y"),
            "width": P(SIZE, "370"),
            "height": P(SIZE, "90"),
            "power-profiles": {
                "module-enabled": P(Bool(), "y"),
                "profiles": {
                    "eco": P(Bool(), "y"),
                    "eco-icon": P(IconType(), "\\uf06c"),
                    "balance": P(Bool(), "y"),
                    "balance-icon": P(IconType(), "\\uf24e"),
                    "performance": P(Bool(), "y"),
                    "performance-icon": P(IconType(), "\\uf135"),
                },
                "show-percentage": P(Bool(), "y"),
                "show-text-status": P(Bool(), "y"),
                "show-status-icon": P(Bool(), "y"),
                "undercover": P(Bool(), "n"),
            },
            "power": {
                "module-enabled": P(Bool(), "y"),
                "options": {
                    "reboot": P(Bool(), "y"),
                    "reboot-icon": P(IconType(), "\\uf021"),
                    "sleep": P(Bool(), "y"),
                    "sleep-icon": P(IconType(), "\\uf186"),
                    "shutdown": P(Bool(), "y"),
                    "shutdown-icon": P(IconType(), "\\uf011"),
                },
            },
            "player": {
                "module-enabled": P(Bool(), "y"),
                "show-cover": P(Bool(), "y"),
                "cover-fallback-image": P(PathType(), 'ASSETS_DIR / "cover.png"'),
                "show-playbutton": P(Bool(), "y"),
                "show-time": P(Bool(), "y"),
                "show-timeline": P(Bool(), "y"),
                "show-title": P(Bool(), "y"),
                "show-artist": P(Bool(), "y"),
            },
        },
    },
    "cc": {
        "module-enabled": P(Bool(), "y"),
        "position": P(Enum("right-bottom", "left-bottom", "right-top", "left-top"), "right-bottom"),
        "cc-style": P(Enum("int", "sep"), "int"),
        "outline": P(Bool(), "n"),
        "hover-enabled": P(Bool(), "y"),
        "calendar-enabled": P(Bool(), "y"),
        "stage1-enabled": P(Bool(), "y"),
        "stage2-enabled": P(Bool(), "y"),
        "stage1-width": P(SIZE, "262"),
        "stage1-height": later(SIZE),
        "stage2-width": later(SIZE),
        "stage2-height": later(SIZE),
        "row1-priority": P(Int(1, 100), "1"),
        "sliders-priority": P(Int(1, 100), "2"),
        "row2-priority": P(Int(1, 100), "3"),
        "row1": {"wifi": named(), "bluetooth": named()},
        "sliders": {
            "orientation": P(Enum("vertical", "horizontal"), "vertical"),
            "brightness": P(Bool(), "y"),
            "volume": P(Bool(), "y"),
            "brightness-position": P(PositionType(), "rhalf:left"),
            "volume-position": P(PositionType(), "rhalf:right"),
        },
        "row2": {"caffeine": named(), "dnd": named()},
        "row3": {"screenshot": named(), "record": named()},
        "*rows": Rows(("wifi", "bluetooth", "caffeine", "dnd", "screenshot", "record")),
    },
    "launcher": {
        "module-enabled": P(Bool(), "y"),
        "position": P(Enum("dock.position", "top", "bottom"), "dock.position"),
        "style": P(Enum("dock.style", "int", "sep"), "dock.style"),
        "outline": P(Bool(), "n"),
        "open-on-super": P(Bool(), "n"),
        "min-width": later(SIZE),
        "max-width": later(SIZE),
        "min-height": later(SIZE),
        "max-height": later(SIZE),
        "show-hidden-apps": P(Bool(), "y"),
        "show-searchbar": P(Bool(), "y"),
        "item-spacing": P(PX, "4"),
        "edge-spacing": P(PX, "7"),
        "context-menu": {
            "enabled": P(Bool(), "y"),
            "bind": P(BindType(), "SHIFT, ENTER"),
            "pin-icon": P(IconType(), "\\uf08d"),
            "hide-icon": P(IconType(), "\\uf070"),
            "like-icon": later(IconType()),
            "item-spacing": P(PX, "5"),
            "edge-spacing": P(PX, "5"),
        },
    },
    "dock": {
        "module-enabled": P(Bool(), "y"),
        "hide-by-window": P(Bool(), "y"),
        "position": P(Enum("top", "bottom"), "bottom"),
        "style": P(Enum("int", "sep"), "int"),
        "outline": P(Bool(), "n"),
        "mark-runned": P(Bool(), "n"),
        "show-launched": P(Bool(), "n"),
        "icon-size": P(SIZE, "24"),
        "item-spacing": P(PX, "8"),
        "edge-spacing": P(PX, "8"),
    },
    "wallpapers": {
        "module-enabled": P(Bool(), "y"),
        "dir": P(PathType(), "WALLPAPERS_DIR"),
        "size": P(Enum("full"), "full"),
        "position": P(Enum("dock.position", "top", "bottom"), "dock.position"),
        "style": P(Enum("dock.style", "int", "sep"), "dock.style"),
        "outline": P(Bool(), "n"),
        "top-spacing": P(PX, "25"),
        "right-spacing": P(PX, "25"),
        "left-spacing": P(PX, "25"),
        "row-size": P(Int(1, 100), "5"),
        "column-size": P(Int(1, 100), "5"),
        "overview-blur": P(Bool(), "y"),
    },
    "notifications": {
        "module-enabled": P(Bool(), "y"),
        "push-allowed": P(Bool(), "y"),
        "ignore-dnd-inlist": P(Bool(), "n"),
    },
    "floodguard": {
        "module-enabled": P(Bool(), "y"),
        "floodguard-trigger-count": P(Int(1, 1000), "3"),
        "floodguard-trigger-time": P(Float(0.1, 3600), "3"),
    },
}
