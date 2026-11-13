import os
import re
from pathlib import Path

from modules.config import geometry, loader
from modules.config.values import Icon

ROOT = Path(__file__).resolve().parents[3]
CONFIG_FILE = loader.config_path(ROOT)
SETTINGS, PROBLEMS = loader.load(CONFIG_FILE, ROOT)
_get = SETTINGS.get


def _glyph(key):
    icon = _get(key)
    if icon is not None and icon.path is not None:
        loader.report([f"{key}: SVG и картинки здесь пока не поддерживаются, используется глиф по умолчанию"],
                      CONFIG_FILE.name if CONFIG_FILE else "конфиг")
        icon = loader.default_value(key)
    return getattr(icon, "glyph", None)


BASE_DIR = _get("BASE_DIR")
ASSETS_DIR = _get("ASSETS_DIR")
STYLE_FILE = _get("STYLE_FILE")
GLOBAL_FONT = _get("GLOBAL_FONT") or ()
ANIMATION_MS = _get("GLOBAL_ANIMATION_SPEED")
OUTLINE_THICKNESS = _get("outline-thickness")
VIM_KEYBINDS = _get("vim-keybinds")
ICON_FONT = _get("ICON_FONT") or ()
WM = _get("wm")

BAR_ENABLED = _get("bar.module-enabled")
TRAY_ENABLED = _get("bar.tray.module-enabled") and _get("bar.tray.tray-shown")
TRAY_ICON = _glyph("bar.tray.tray-icon")
TRAY_LIMIT = _get("bar.tray.tray-expand-by-icon-limit")
TRAY_SCROLLABLE = _get("bar.tray.tray-scrollable")
FRAME_ENABLED = _get("frame.module-enabled")
NOTCH_ENABLED = _get("notch.module-enabled")
CC_ENABLED = _get("cc.module-enabled")
LAUNCHER_ENABLED = _get("launcher.module-enabled")
DOCK_ENABLED = _get("dock.module-enabled")
WALLPAPERS_ENABLED = _get("wallpapers.module-enabled")
NOTIFICATIONS_ENABLED = _get("notifications.module-enabled")
FLOODGUARD_ENABLED = _get("floodguard.module-enabled")

DOCK_H = 40
UNDERCOVER = BAR_ENABLED and _get("bar.undercover-module-enabled")
TRAY_LIMIT = 0 if UNDERCOVER else TRAY_LIMIT
TRAY_UNDERCOVER = _get("bar.tray.undercover")
UNDERCOVER_LEFT = _get("bar.launcher-btn.undercover-position") == "left"
UNDERCOVER_ICON = _get("bar.launcher-btn.undercover-icon") or Icon()
BAR_WIDTH = DOCK_H if UNDERCOVER else _get("bar.bar-width")
BAR_POSITION = ("bottom" if UNDERCOVER else _get("bar.position")) if BAR_ENABLED else None
BAR_HORIZONTAL = geometry.is_horizontal(BAR_POSITION)
BAR_SIZE = BAR_WIDTH if BAR_ENABLED else 0
BAR_SCALE = 1 if UNDERCOVER else geometry.bar_scale(BAR_WIDTH)
BAR_SPLIT = BAR_ENABLED and not UNDERCOVER and _get("bar.style") == "split"
_FRAME = {side: _get(f"frame.{side}") for side in geometry.SIDES}
_BAR_GEOMETRY = (_FRAME, FRAME_ENABLED, BAR_POSITION, BAR_WIDTH if BAR_ENABLED else 0, _get("frame.include-bar"),
                 UNDERCOVER, BAR_SPLIT)
_SIDES = geometry.frame_sides(*_BAR_GEOMETRY)
LEFT, TOP, RIGHT, BOTTOM = (_SIDES[side] for side in geometry.SIDES)
_VISIBLE = geometry.visible_frame(*_BAR_GEOMETRY)
FRAME_LEFT, FRAME_TOP, FRAME_RIGHT, FRAME_BOTTOM = (_VISIBLE[side] for side in geometry.SIDES)
_BAR_ATTACH = (FRAME_ENABLED, BAR_POSITION, _get("frame.include-bar"), UNDERCOVER, BAR_SPLIT)
BAR_DETACHED = geometry.bar_detached(*_BAR_ATTACH)
BAR_BAND = geometry.bar_band(*_BAR_GEOMETRY)
BAR_OFFSET = BAR_BAND[0] + geometry.bar_gap(*_BAR_ATTACH) if BAR_DETACHED else 0
BAR_GAP = geometry.BAR_GAP
BAR_MARGINS = geometry.bar_margins(_VISIBLE, BAR_POSITION, BAR_OFFSET) if BAR_DETACHED else {}
LAUNCHER_BUTTON_ICON = _get("bar.launcher-btn.launcher-button-icon") or Icon()


WORKSPACES = _get("bar.workspace.ws-shown")
WS_CLICKABLE = _get("bar.workspace.ws-clickable")
WS_STYLE = _get("bar.workspace.ws-style")
WS_ICONS = {state: _glyph(f"bar.workspace.ws-{key}-icon")
            for state, key in (("empty", "empty"), ("occupied", "inuse"), ("active", "active"))}
WS_HIGHLIGHT = _get("bar.workspace.ws-active-highlighting")
BAR_LAUNCHER_SHOWN = _get("bar.launcher-btn.launcher-button-shown")
BAR_PROFILES_SHOWN = _get("bar.power-profiles-shown")
BAR_CLOCK_SHOWN = _get("bar.clock-shown")
BAR_LAYOUT_SHOWN = _get("bar.keyboard-layout-shown")
BAR_POWER_SHOWN = _get("bar.powerbutton-shown")
BAR_OUTLINE = {
    "box-avatar": _get("bar.launcher-btn.outline"),
    "box-workspaces": _get("bar.workspace.outline"),
    "box-tray": _get("bar.tray.outline"),
    "box-battery": _get("bar.power-profiles-outline"),
    "box-layout": _get("bar.keyboard-layout-outline"),
    "box-clock": _get("bar.clock-outline"),
    "box-power": _get("bar.powerbutton-outline"),
}
LAUNCHER_ICON_SIZE = geometry.scaled(_get("bar.launcher-btn.launcher-icon-size"), BAR_SCALE)

NOTCH_SIDE = _get("notch.position")
NOTCH_ISLAND = _get("notch.style") == "island"
NOTCH_OUTLINE = _get("notch.outline")
FRAME_OUTLINE = _get("frame.outline")
CC_OUTLINE = _get("cc.outline")
LAUNCHER_OUTLINE = _get("launcher.outline")
DOCK_OUTLINE = _get("dock.outline")
PICKER_OUTLINE = _get("wallpapers.outline")
NOTCH_INSCRIBED = BAR_POSITION == NOTCH_SIDE and not UNDERCOVER
DOCK_TOP = _get("dock.position") == "top" and not UNDERCOVER
UNDERCOVER_LAUNCHER = UNDERCOVER and _get("bar.launcher-btn.undercover")
LAUNCHER_TOP = geometry.follows_dock(_get("launcher.position"), DOCK_TOP) and not UNDERCOVER_LAUNCHER
PICKER_TOP = geometry.follows_dock(_get("wallpapers.position"), DOCK_TOP) and not UNDERCOVER

NOTCH_W = _get("notch.expand.width")
NOTCH_H = _get("notch.expand.height")

IDLE_SPACING = _get("notch.placeholder-edge-spacing")
IDLE_PADDING = _get("notch.placeholder-spacing")
IDLE_TEXT = _get("notch.placeholder-text")

NOTCH_HIDE_BY_WINDOW = _get("notch.hide-by-window")
_EXPAND = _get("notch.expand.enable")
NOTCH_MENUS = tuple(name for name, key in (("battery", "power-profiles"), ("power", "power"), ("player", "player"))
                    if _EXPAND and _get(f"notch.expand.{key}.module-enabled"))
NOTCH_PROFILES = tuple(profile for profile, key in (("power-saver", "eco"), ("balanced", "balance"),
                                                    ("performance", "performance"))
                       if _get(f"notch.expand.power-profiles.profiles.{key}"))
NOTCH_SHOW_PERCENTAGE = _get("notch.expand.power-profiles.show-percentage")
NOTCH_SHOW_TEXT_STATUS = _get("notch.expand.power-profiles.show-text-status")
NOTCH_SHOW_STATUS_ICON = _get("notch.expand.power-profiles.show-status-icon")
# The power profiles menu opens above the Undercover taskbar's profiles button instead of in the notch.
PROFILES_BY_TASKBAR = UNDERCOVER and "battery" in NOTCH_MENUS and _get("notch.expand.power-profiles.undercover")
NOTCH_POWER_OPTIONS = tuple(name for name in ("reboot", "sleep", "shutdown")
                            if _get(f"notch.expand.power.options.{name}"))
PLAYER_SHOW = {name: _get(f"notch.expand.player.show-{name}")
               for name in ("cover", "playbutton", "time", "timeline", "title", "artist")}

COVER_FALLBACK = Path(_get("notch.expand.player.cover-fallback-image"))
ICON_ECO = _glyph("notch.expand.power-profiles.profiles.eco-icon")
ICON_BALANCE = _glyph("notch.expand.power-profiles.profiles.balance-icon")
ICON_PERF = _glyph("notch.expand.power-profiles.profiles.performance-icon")
ICON_REBOOT = _glyph("notch.expand.power.options.reboot-icon")
ICON_POWEROFF = _glyph("notch.expand.power.options.shutdown-icon")
ICON_SLEEP = _glyph("notch.expand.power.options.sleep-icon")

DOCK_ICON = _get("dock.icon-size")
DOCK_HIDE_BY_WINDOW = _get("dock.hide-by-window") and not UNDERCOVER
DOCK_MARK_RUNNED = _get("dock.mark-runned")
DOCK_SHOW_LAUNCHED = _get("dock.show-launched")
DOCK_EDGE = _get("dock.edge-spacing")
DOCK_SEPARATE = _get("dock.style") == "sep"
_LAUNCHER_STYLE = _get("launcher.style")
LAUNCHER_SEPARATE = DOCK_SEPARATE if _LAUNCHER_STYLE == "dock.style" else _LAUNCHER_STYLE == "sep"
DOCK_GAP = _get("dock.item-spacing")

KC_W = _get("cc.stage1-width")
CC_LEFT = _get("cc.position").startswith("left") and not UNDERCOVER
CC_TOP = _get("cc.position").endswith("top") and not UNDERCOVER
CC_SEPARATE = _get("cc.cc-style") == "sep"
CC_HOVER = _get("cc.hover-enabled") and not UNDERCOVER
CC_CALENDAR = _get("cc.calendar-enabled")
CC_STAGES = tuple(level for level in (1, 2) if _get(f"cc.stage{level}-enabled") and not (UNDERCOVER and level == 1))


def _cc_rows():
    cc = SETTINGS.get("cc")
    names = sorted((key for key in cc if re.fullmatch(r"row\d+", key)), key=lambda key: int(key[3:]))
    seen, rows = set(), []
    for name in names:
        items = []
        for item in cc[name].visible():
            if isinstance(item, str):
                if item in seen:
                    continue
                seen.add(item)
            items.append(item)
        rows.append((name, items))
    return rows


CC_ROWS = _cc_rows()
CC_ROW_PRIORITIES = {f"row{n}": _get(f"cc.row{n}-priority") for n in (1, 2)}
CC_SLIDERS_PRIORITY = _get("cc.sliders-priority")
CC_HORIZONTAL = _get("cc.sliders.orientation") == "horizontal"
CC_SLIDERS = [(kind, _get(f"cc.sliders.{kind}-position")) for kind in ("brightness", "volume")
              if _get(f"cc.sliders.{kind}")]
KC_ROW1_H = 52
KC_FULL_H = 440
KC_CARD_ICON = 32
KC_FLOOD_ICON = 24

PUSH_SECONDS = 5
FLOOD_COUNT = _get("floodguard.floodguard-trigger-count")
FLOOD_WINDOW = float(_get("floodguard.floodguard-trigger-time"))
PUSH_ALLOWED = _get("notifications.push-allowed")
DND_TO_LIST = _get("notifications.ignore-dnd-inlist")
HISTORY_MAX = 50

SCREENSHOT_DIR = Path.home() / "Pictures" / "Screenshots"
RECORD_DIR = Path.home() / "Videos"

STATES_DIR = ROOT / "states"
PINNED_FILE = STATES_DIR / "pinned.txt"
HIDDEN_FILE = STATES_DIR / "hidden.txt"
LIKED_FILE = STATES_DIR / "liked.txt"
STATE_FILE = STATES_DIR / "state.conf"

IPC_SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "leech.sock"

WALLPAPER_DIR = Path(_get("wallpapers.dir"))
WALLPAPER_OVERVIEW_BLUR = _get("wallpapers.overview-blur")
WALLPAPER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mkv", ".gif", ".avi", ".mov", ".m4v")

_PICKER_STYLE = _get("wallpapers.style")
PICKER_SEPARATE = DOCK_SEPARATE if _PICKER_STYLE == "dock.style" else _PICKER_STYLE == "sep"
PICKER_MARGIN = (_get("wallpapers.top-spacing"), _get("wallpapers.right-spacing"), _get("wallpapers.left-spacing"))
PICKER_COLUMNS = _get("wallpapers.row-size")
PICKER_ROWS = _get("wallpapers.column-size")
THUMB_CACHE_MAX = 60

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "leech"

LAUNCHER_HEIGHT = 0.5
LAUNCHER_MIN_ICONS = 9
LAUNCHER_EDGE = _get("launcher.edge-spacing")
LAUNCHER_ROW_H = 34
LAUNCHER_ROW_GAP = _get("launcher.item-spacing")
LAUNCHER_SHOW_HIDDEN_TOGGLE = _get("launcher.show-hidden-apps")
LAUNCHER_SEARCHBAR = _get("launcher.show-searchbar")
LAUNCHER_SUPER_TAP = _get("launcher.open-on-super")
LAUNCHER_MENU_ENABLED = _get("launcher.context-menu.enabled")
LAUNCHER_HEAD_H = 24 if LAUNCHER_SHOW_HIDDEN_TOGGLE else LAUNCHER_EDGE
LAUNCHER_MENU_EDGE = _get("launcher.context-menu.edge-spacing")
LAUNCHER_MENU_GAP = _get("launcher.context-menu.item-spacing")
LAUNCHER_MENU_BIND = _get("launcher.context-menu.bind")
ICON_PIN = _glyph("launcher.context-menu.pin-icon")
ICON_HIDE = _glyph("launcher.context-menu.hide-icon")
LAUNCHER_MENU_ICON = 16

LAUNCHER_SEARCH_H = 30 if LAUNCHER_SEARCHBAR else 0

KC_CAL_COLLAPSED_H = 15
KC_CAL_H = 236
CALENDAR_WEEK_START = 0

PLAYER_TIMELINE_H = 6


CONTROL_STEP = 5
BRIGHTNESS_EXPONENT = 4
OSD_SECONDS = 1.6
LAUNCHER_HEART = 16


def __getattr__(name):
    # Colours and radii live in style.css (modules/common/theme.py); these names are read at draw time.
    from modules.common import theme
    if name == "COLOR":
        return theme.bg("#leech-surface")
    if name == "RADIUS":
        return theme.radius("#leech-surface")
    if name == "FRAME_RADIUS":
        return theme.radius("#leech-frame") if FRAME_ENABLED else 0
    # Spacings that leech.conf does not set (see the "Отрисовка" section of style.css).
    if name in _SPACINGS:
        selector, kind = _SPACINGS[name]
        return (theme.pad if kind == "padding" else theme.gap)(selector)
    if name == "KC_CARD_H":
        return KC_CARD_ICON + 2 * theme.pad("#cc-push-card")
    if name == "LAUNCHER_SEARCH_GAP":
        return theme.gap("#launcher-search") if LAUNCHER_SEARCHBAR else 0
    raise AttributeError(name)


_SPACINGS = {
    "NOTCH_SPACING": ("#notch-menu", "margin"),
    "BUTTONS_EDGE": ("#notch-menu", "padding"),
    "PLAYER_SPACING": ("#notch-player", "padding"),
    "PLAYER_GAP": ("#notch-player", "margin"),
    "PLAYER_TIMELINE_BOTTOM": ("#notch-timeline", "margin"),
    "DOCK_SEP_GAP": ("#leech-separate", "margin"),
    "CC_SEP_GAP": ("#leech-separate", "margin"),
    "KC_PAD": ("#cc-body", "padding"),
    "KC_PUSH_PAD": ("#cc-push", "padding"),
    "KC_CARD_PAD": ("#cc-push-card", "padding"),
    "PICKER_PAD": ("#picker", "padding"),
    "PICKER_SPACING": ("#picker", "margin"),
    "PICKER_BORDER": ("#picker-cell", "padding"),
    "LAUNCHER_MENU_PAD": ("#launcher-menu-item", "padding"),
    "LAUNCHER_SEARCH_EDGE": ("#launcher-search", "padding"),
}
