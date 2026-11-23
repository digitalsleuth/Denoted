from dataclasses import dataclass, field

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor, QPalette

from ._vendor.qt_themes import get_themes, update_palette

SETTINGS_ORGANIZATION = "digitalsleuth"
SETTINGS_APPLICATION = "Denoted"
THEME_KEY = "appearance/theme"
NAME_WORDS = {"github": "GitHub"}
DEFAULT_SCHEME = "Nord"
OK_DEFAULT = "#3b8f5a"
WARN_DEFAULT = "#c08a1a"
BLACK = QColor("black")


@dataclass(frozen=True)
class Scheme:
    window: str
    base: str
    alternate: str
    text: str
    highlight: str
    highlight_text: str
    match: str
    match_text: str
    link: str = ""
    handle: str = ""
    handle_hover: str = ""
    theme: object = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class Colors:
    window: str
    base: str
    alt: str
    text: str
    muted: str
    border: str
    button_border: str
    hover: str
    accent: str
    accent_bg: str
    accent_fg: str
    strip: str
    select_bg: str
    select_fg: str
    pills: dict = field(compare=False)


CLASSIC = Scheme(
    window="#f0f0f0",
    base="white",
    alternate="#f5f5f5",
    text="black",
    highlight="#0078d7",
    highlight_text="white",
    match="lightgreen",
    match_text="black",
)
ORIGINAL = Scheme(
    window="white",
    base="white",
    alternate="#d9ebfb",
    text="black",
    highlight="#d9ebfb",
    highlight_text="black",
    match="lightgreen",
    match_text="black",
    link="#1644b9",
    handle="#a0a0a0",
    handle_hover="#808080",
)


def from_theme(theme):
    dark = theme.is_dark_theme()
    highlight_text = theme.mantle if theme.primary.valueF() > 0.5 else theme.text
    match_text = theme.mantle if theme.green.valueF() > 0.5 else theme.text
    return Scheme(
        window=theme.base.name(),
        base=(theme.mantle if dark else theme.crust).name(),
        alternate=(theme.base if dark else theme.mantle).name(),
        text=theme.text.name(),
        highlight=theme.primary.name(),
        highlight_text=highlight_text.name(),
        match=theme.green.name(),
        match_text=match_text.name(),
        theme=theme,
    )


def display_name(name):
    return " ".join(NAME_WORDS.get(word, word.title()) for word in name.split("_"))


def themed_schemes():
    schemes = {
        display_name(name): from_theme(theme) for name, theme in get_themes().items()
    }
    return dict(sorted(schemes.items()))


SCHEMES = {"Classic": CLASSIC, "Original": ORIGINAL, **themed_schemes()}


def available_schemes():
    return dict(SCHEMES)


def default_scheme():
    return SCHEMES.get(DEFAULT_SCHEME, CLASSIC)


def settings():
    return QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        SETTINGS_ORGANIZATION,
        SETTINGS_APPLICATION,
    )


def saved_scheme():
    name = settings().value(THEME_KEY)
    return (
        available_schemes().get(name, default_scheme())
        if isinstance(name, str)
        else default_scheme()
    )


def save_scheme_name(name):
    store = settings()
    store.setValue(THEME_KEY, name)
    store.sync()


def mix(first, second, amount):
    return QColor.fromRgbF(
        first.redF() * (1 - amount) + second.redF() * amount,
        first.greenF() * (1 - amount) + second.greenF() * amount,
        first.blueF() * (1 - amount) + second.blueF() * amount,
    )


def build_palette(scheme, base_palette=None):
    if scheme.theme is not None:
        palette = QPalette(base_palette) if base_palette is not None else QPalette()
        update_palette(palette, scheme.theme)
        return palette
    window, base, alternate = (
        QColor(scheme.window),
        QColor(scheme.base),
        QColor(scheme.alternate),
    )
    text = QColor(scheme.text)
    highlight, highlight_text = QColor(scheme.highlight), QColor(scheme.highlight_text)
    link = QColor(scheme.link or scheme.highlight)
    dim = mix(text, window, 0.5)
    palette = QPalette(window, window)
    roles = QPalette.ColorRole
    for role, color in (
        (roles.Window, window),
        (roles.WindowText, text),
        (roles.Base, base),
        (roles.AlternateBase, alternate),
        (roles.Text, text),
        (roles.Button, window),
        (roles.ButtonText, text),
        (roles.BrightText, text),
        (roles.ToolTipBase, base),
        (roles.ToolTipText, text),
        (roles.Highlight, highlight),
        (roles.HighlightedText, highlight_text),
        (roles.Link, link),
        (roles.LinkVisited, link),
        (roles.PlaceholderText, dim),
    ):
        palette.setColor(role, color)
    for role in (roles.WindowText, roles.Text, roles.ButtonText, roles.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, dim)
    return palette


def colors_for(scheme, palette):
    role = palette.color
    roles = QPalette.ColorRole
    window, base, alt, text, highlight = role(roles.Window), role(roles.Base), role(roles.AlternateBase), role(roles.Text), role(roles.Highlight)
    dark = window.lightnessF() < 0.5
    ok = scheme.theme.green if scheme.theme is not None else QColor(OK_DEFAULT)
    warn = scheme.theme.yellow if scheme.theme is not None else QColor(WARN_DEFAULT)
    return Colors(
        window=window.name(),
        base=base.name(),
        alt=alt.name(),
        text=text.name(),
        muted=mix(text, window, 0.45).name(),
        border=mix(text, window, 0.88).name(),
        button_border=mix(text, window, 0.8).name(),
        hover=mix(text, window, 0.92).name(),
        accent=highlight.name(),
        accent_bg=mix(highlight, window, 0.8).name(),
        accent_fg=text.name(),
        strip=mix(window, BLACK, 0.3 if dark else 0.05).name(),
        select_bg=highlight.name(),
        select_fg=role(roles.HighlightedText).name(),
        pills={
            "ok": (mix(ok, window, 0.8).name(), mix(ok, text, 0.3).name()),
            "warn": (mix(warn, window, 0.8).name(), mix(warn, text, 0.3).name()),
            "note": (mix(text, window, 0.9).name(), mix(text, window, 0.35).name()),
        },
    )
