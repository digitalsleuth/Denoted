from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication

UI, MONO, ICON = "ui", "mono", "icon"
FAMILIES = {
    UI: ("Segoe UI", "Helvetica Neue", "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans", "Liberation Sans"),
    MONO: ("Consolas", "Menlo", "SF Mono", "DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "Ubuntu Mono"),
    ICON: ("Segoe Fluent Icons", "Segoe MDL2 Assets"),
}
STYLE_HINTS = {UI: QFont.StyleHint.SansSerif, MONO: QFont.StyleHint.Monospace, ICON: QFont.StyleHint.AnyStyle}
CSS_STACKS = {
    UI: ", ".join(f'"{name}"' for name in FAMILIES[UI]) + ", system-ui, sans-serif",
    MONO: ", ".join(f'"{name}"' for name in FAMILIES[MONO]) + ", monospace",
}
resolved = {}


def family(role):
    if role not in resolved and QGuiApplication.instance() is not None:
        installed = {name.lower() for name in QFontDatabase.families()}
        resolved[role] = next((name for name in FAMILIES[role] if name.lower() in installed), None)
    return resolved.get(role)


def qfont(role, points=None):
    font = QFont(family(role) or FAMILIES[role][0])
    font.setStyleHint(STYLE_HINTS[role])
    if points:
        font.setPointSize(points)
    return font
