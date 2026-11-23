import os
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QAbstractTextDocumentLayout, QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPalette, QTextCursor, QTextDocument, QTextOption

from . import fonts
from . import format as dnf

FRAME_SIDE = 5
FRAME_BOTTOM = 5
TAB_BAR_HEIGHT = 44
TAB_TOP = 13
TAB_X0 = 45
TAB_WIDTH = 240
TAB_PAD = 12
TAB_TEXT_WIDTH = 194
MENU_HEIGHT = 32
STATUS_HEIGHT = 32
EDITOR_PAD = 16
EDITOR_TOP_PAD = 17
UI_FONT, ICON_FONT, TEXT_FONT = fonts.UI, fonts.ICON, fonts.MONO
UI_PX = 12
TAB_PX = 13
TAB_SPACING = 96
ICON_PX = 14
TEXT_PX = 15
STRIP_BG = QColor(32, 32, 32)
ACTIVE_BG = QColor(44, 44, 44)
EDITOR_BG = QColor(39, 39, 39)
TEXT_FG = QColor(255, 255, 255)
DIM_FG = QColor(159, 159, 159)
TAB_FG = QColor(200, 200, 200)
SELECTION_BG = QColor(0, 120, 212)
ICON_CLOSE, ICON_MINIMIZE, ICON_MAXIMIZE, ICON_ADD, ICON_CHEVRON = "", "", "", "", ""
ICON_FALLBACKS = {ICON_CLOSE: "✕", ICON_MINIMIZE: "–", ICON_MAXIMIZE: "☐", ICON_ADD: "+", ICON_CHEVRON: "▾", "": "☰", "": "B", "": "I", "": "✎", "": "⚙"}
TOOLBAR_ICONS = ((997, ""), (1051, ""), (1083, ""), (1115, ""), (1147, ""), (1181, ""), (1235, ""), (2025, ""), (2082, ""), (2116, ""), (2150, ""))
TOOLBAR_CHEVRONS = (1017, 1202, 2045)
MENU_ITEMS = ((15, "File"), (64, "Edit"), (115, "View"))
ASSUMED_ZOOM = "100%"


def font(family, px, spacing=100):
    f = fonts.qfont(family)
    f.setPixelSize(px)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, spacing)
    return f


def put(p, x, y, text, color, family=UI_FONT, px=UI_PX, width=None, spacing=100):
    p.setFont(font(family, px, spacing))
    p.setPen(color)
    p.drawText(QRectF(x, y - 16, width or 600, 32), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


def put_center(p, cx, y, text, color, family=ICON_FONT, px=ICON_PX):
    if family == ICON_FONT and fonts.family(ICON_FONT) is None:
        family, text = UI_FONT, ICON_FALLBACKS.get(text, "")
    if not text:
        return
    p.setFont(font(family, px))
    p.setPen(color)
    p.drawText(QRectF(cx - 20, y - 16, 40, 32), Qt.AlignmentFlag.AlignCenter, text)


def draw_tabs(p, width, entries, selected):
    p.fillRect(0, 0, width, TAB_BAR_HEIGHT, STRIP_BG)
    p.fillRect(14, 8, 12, 14, QColor(70, 170, 230))
    for i, e in enumerate(entries):
        x = TAB_X0 + i * TAB_WIDTH
        if i == selected:
            p.setBrush(ACTIVE_BG)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, TAB_TOP, TAB_WIDTH - 4, TAB_BAR_HEIGHT - TAB_TOP + 8), 6, 6)
        p.save()
        p.setClipRect(QRectF(x + TAB_PAD, 0, TAB_TEXT_WIDTH, TAB_BAR_HEIGHT))
        put(p, x + TAB_PAD, 28, dnf.entry_title(e), TEXT_FG if i == selected else TAB_FG, px=TAB_PX, spacing=TAB_SPACING)
        p.restore()
        if dnf.entry_modified(e):
            p.setBrush(DIM_FG)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x + 222, 28), 3.5, 3.5)
        elif i == selected:
            put_center(p, x + 222, 28, ICON_CLOSE, TAB_FG, px=10)
    put_center(p, TAB_X0 + len(entries) * TAB_WIDTH + 24, 28, ICON_ADD, TAB_FG)
    for dx, icon in ((116, ICON_MINIMIZE), (70, ICON_MAXIMIZE), (24, ICON_CLOSE)):
        put_center(p, width - dx, 17, icon, TEXT_FG, px=10)


def draw_menu(p, width, top, formatting):
    p.fillRect(0, top, width, MENU_HEIGHT, ACTIVE_BG)
    y = top + MENU_HEIGHT // 2
    for x, label in MENU_ITEMS:
        put(p, x, y, label, TEXT_FG)
    put(p, 933, y, "H1", TEXT_FG)
    for x in TOOLBAR_CHEVRONS:
        put_center(p, x, y, ICON_CHEVRON, TAB_FG, px=8)
    for x, icon in TOOLBAR_ICONS:
        put_center(p, x, y, icon, TAB_FG)


def draw_editor(p, width, top, bottom, entry):
    cfg, sel, _ = dnf.effective(entry)
    doc = QTextDocument()
    doc.setDefaultFont(font(TEXT_FONT, TEXT_PX))
    doc.setDocumentMargin(0)
    opt = QTextOption()
    wrap = cfg is not None and cfg.word_wrap
    opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if wrap else QTextOption.WrapMode.NoWrap)
    if cfg is not None and cfg.rtl:
        opt.setTextDirection(Qt.LayoutDirection.RightToLeft)
    doc.setDefaultTextOption(opt)
    doc.setTextWidth(width - 2 * EDITOR_PAD if wrap else -1)
    doc.setPlainText(dnf.entry_text(entry))
    last = doc.characterCount() - 1
    start, end = min(sel[0], last), min(sel[1], last)
    cursor = QTextCursor(doc)
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    ctx = QAbstractTextDocumentLayout.PaintContext()
    palette = ctx.palette
    palette.setColor(QPalette.ColorRole.Text, TEXT_FG)
    ctx.palette = palette
    if start != end:
        selection = QAbstractTextDocumentLayout.Selection()
        selection.cursor = cursor
        selection.format.setBackground(SELECTION_BG)
        ctx.selections = [selection]
    p.save()
    p.setClipRect(QRectF(0, top, width, bottom - top))
    p.translate(EDITOR_PAD, top + EDITOR_TOP_PAD)
    doc.documentLayout().draw(p, ctx)
    block = doc.findBlock(end)
    line = block.layout().lineForTextPosition(end - block.position())
    x = line.cursorToX(end - block.position())
    x = x[0] if isinstance(x, tuple) else x
    if start == end:
        p.fillRect(QRectF(x, doc.documentLayout().blockBoundingRect(block).top() + line.y(), 1.5, line.height()), TEXT_FG)
    p.restore()
    return doc.findBlock(end).blockNumber() + 1, end - block.position() + 1, len(doc.toPlainText())


def draw_status(p, width, top, entry, line, col, chars):
    p.fillRect(0, top, width, STATUS_HEIGHT, ACTIVE_BG)
    cfg = dnf.effective(entry)[0]
    eol, enc = dnf.entry_format(entry)
    y = top + STATUS_HEIGHT // 2
    put(p, 23, y, f"Ln {line}, Col {col}", TAB_FG)
    put(p, 106, y, f"{chars} characters", TAB_FG)
    put(p, 313, y, dnf.formatting_name(cfg), TAB_FG)
    put(p, width - 369, y, ASSUMED_ZOOM, TAB_FG)
    put(p, width - 302, y, eol, TAB_FG)
    put(p, width - 133, y, enc, TAB_FG)


def render(view, selected=None):
    w, h = view.window.geometry[4:]
    width, height = w - 2 * FRAME_SIDE, h - FRAME_BOTTOM
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(EDITOR_BG)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    selected = min(max(view.window.selected if selected is None else selected, 0), len(view.entries) - 1)
    entry = view.entries[selected]
    draw_tabs(p, width, view.entries, selected)
    draw_menu(p, width, TAB_BAR_HEIGHT, entry)
    status_top = height - STATUS_HEIGHT
    line, col, chars = draw_editor(p, width, TAB_BAR_HEIGHT + MENU_HEIGHT, status_top, entry)
    draw_status(p, width, status_top, entry, line, col, chars)
    p.end()
    return img


def main():
    app = QGuiApplication(sys.argv)
    directory = dnf.load_directory(os.path.abspath(sys.argv[1]))
    out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else "notepad_mockup.png")
    views = [v for v in directory.views if v.window is not None and v.entries]
    for i, view in enumerate(views):
        path = out if len(views) == 1 else f"{os.path.splitext(out)[0]}-{i + 1}{os.path.splitext(out)[1]}"
        img = render(view)
        img.save(path)
        print(f"{view.label}: {img.width()}x{img.height()} -> {path}")
    del app


if __name__ == "__main__":
    main()
