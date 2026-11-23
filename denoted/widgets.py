import bisect
import os
import re

from PyQt6.QtCore import QEvent, QModelIndex, QPersistentModelIndex, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetricsF, QPainter, QPalette, QPen, QPolygonF, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QComboBox, QProxyStyle, QFrame, QHBoxLayout, QLabel, QLayout, QListView, QPlainTextEdit, QSplitter, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from . import fonts
from .format import HIVE_GROUPS

colors = None
CORNER_RADIUS = 10
ROW_RADIUS = 6
EMPTY_RAW_TEXT = "Open a state file, a folder, or a live system to see its bytes here."
HOVER_HINT ="Hover bytes, or hover a field in the tabs above, to see where it sits in the file."
CHEVRON_STROKE = 1.7
CHEVRON_HALF_WIDTH = 4.5
CHEVRON_HALF_HEIGHT = 2.5
CHEVRON_RIGHT = 15
POPUP_CONTAINER = "QComboBoxPrivateContainer"
RAW_SPLIT_STRETCH = (3, 2)
GROUP_RADIUS = 5
GROUP_DARKEN = 150
GROUP_INNER_INSET = 1.5
BYTE_RADIUS = 4
SELECT_RADIUS = 1.5
BYTE_PAD_X = 3
ASCII_PAD_X = 0
SWATCH_TEXT_INSET = 8
BYTE_PAD_Y = 1
CHIP_RADIUS = 8
ROW_MIN_HEIGHT = 26
RAW_FONT_SIZE = 9
MAX_RAW_BYTES = 65536
BYTES_PER_ROW = 16
RAW_ROW_SIZES = (16, 8)
HEX_GAP_AFTER = 8
GUI_MARGIN = 8
BYTE_FG = "#f2f2f2"
SWATCH_ROLE = Qt.ItemDataRole.UserRole + 100
PILL_STYLE = "background: {}; color: {}; border-radius: 9px; padding: 2px 10px; font-size: 11px;"
CHIP_STYLE = "background: {}; color: " + BYTE_FG + "; border-radius: " + str(CHIP_RADIUS) + "px; padding: 1px 8px; font-size: 10px;"
KIND_COLORS = {
    "signature": ("Signature", "#4a3fc9"), "header": ("Header, flags and counters", "#a8740a"), "path": ("File path", "#1f9d55"), "size": ("Sizes and lengths", "#2a5bd0"),
    "format": ("Encoding and line endings", "#a63fb0"), "timestamp": ("Timestamp", "#c2336b"), "hash": ("SHA-256", "#5a6b78"), "selection": ("Selection", "#d96a16"),
    "config": ("Settings", "#0e7fa6"), "unidentified": ("Unidentified", "#e03131"), "content": ("Text content", "#8a9a14"), "edit": ("Edit records", "#7b4a2a"),
    "crc": ("CRC32", "#0f8a8a"), "window": ("Window tabs", "#7e47d6"), "geometry": ("Window rectangle", "#8a7d12"), "other": ("Unparsed", "#7d6e6e"),
    "hive-key": ("Registry key", "#3f7fb5"), "hive-value": ("Value record", "#7b5ea7"), "hive-data": ("Setting data", "#c0792b"),
}
HIVE_SOURCE = "hive"
CRC_FIELD = ("CRC32 (big-endian)",)
ROW_LINKS = {
    ("Tab file", "Header byte 0x02"): ("Header byte",),
    ("Document", "Saved to a path"): ("Saved-to-path flag",), ("Document", "Path"): ("Path",), ("Document", "Recorded file size"): ("Recorded file size",),
    ("Document", "Encoding"): ("Encoding",), ("Document", "Line endings"): ("Line endings",), ("Document", "File last-write time"): ("File last-write time",),
    ("Document", "File last-write ticks"): ("File last-write time",), ("Document", "Characters in snapshot"): ("Content length", "Text content"),
    ("Document", "Characters after edits"): ("Text content", "Edit #"), ("Document", "Selection"): ("Selection",), ("Document", "Unsaved-data flag"): ("Unsaved flag",),
    ("Document", "Appended edit records"): ("Edit #",), ("Document", "Text source"): ("Unsaved flag", "Content length"), ("Document", "Unparsed trailing bytes"): ("Unparsed trailing bytes",),
    ("Settings", "Word wrap"): ("Word wrap",), ("Settings", "Right-to-left reading order"): ("Right-to-left",), ("Settings", "Show Unicode control characters"): ("Show Unicode",),
    ("Settings", "Config version"): ("Config version",), ("Settings", "Formatting type"): ("Formatting type",),
    ("Integrity", "Stored SHA256"): ("SHA-256",), ("Integrity", "Hash vs current text"): ("SHA-256",), ("Integrity", "Byte after hash"): ("Byte after hash",),
    ("State record", "Sequence"): ("Sequence number",), ("State record", "Base size"): ("Base file size",), ("State record", "Selection"): ("Selection",),
    ("Window", "Sequence"): ("Sequence number",), ("Window", "Tabs"): ("Tab count",), ("Window", "Selected tab"): ("Selected tab index",),
    ("Window", "Window rectangle (desktop coords)"): ("Window left", "Window top", "Window right", "Window bottom"),
    ("Window", "Window size (incl. invisible frame)"): ("Window width", "Window height"), ("Window", "Trailing byte(s)"): ("Trailing bytes",),
    ("Hive file", "Hive name (stored path)"): ("Hive name",), ("Hive file", "Hive version"): ("Hive version",), ("Hive file", "Sequence numbers"): ("Sequence number",),
    ("Hive file", "Header checksum valid"): ("Header checksum",), ("Hive file", "Hive header time"): ("Last written (hive header)",),
}
ROW_LINKS.update({(group, key): CRC_FIELD for group in ("Integrity", "State record", "Window") for key in ("CRC32 stored", "CRC32 computed", "CRC32 valid")})


def set_colors(value):
    global colors
    colors = value


def build_style(c):
    return f"""
QSplitter::handle {{ background: transparent; }}
QFrame#card {{ background: {c.window}; border: 1px solid {c.border}; border-radius: {CORNER_RADIUS}px; }}
QTreeWidget#nav {{ background: transparent; border: none; padding: 4px; }}
QLabel#sectionLabel {{ color: {c.muted}; font-size: 11px; padding: 4px 8px; }}
QStatusBar QLabel#statusHint {{ color: {c.muted}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {c.muted}; padding: 6px 10px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c.text}; border-bottom: 2px solid {c.accent}; }}
QTabBar::tab:hover {{ color: {c.text}; }}
QPushButton {{ background: {c.window}; border: 1px solid {c.button_border}; border-radius: {ROW_RADIUS}px; padding: 5px 12px; }}
QPushButton:hover {{ background: {c.hover}; }}
QComboBox {{ background: {c.window}; border: 1px solid {c.button_border}; border-radius: {ROW_RADIUS}px; padding: 4px 8px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: none; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox:hover {{ background: {c.hover}; }}
QComboBox:on {{ border-color: {c.accent}; }}
QComboBox QAbstractItemView {{ background: {c.window}; color: {c.text}; border: none; outline: 0; padding: 3px; selection-background-color: {c.accent_bg}; selection-color: {c.text}; }}
QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 2px 8px; border-radius: 5px; }}
QComboBox QAbstractItemView::item:hover {{ background: {c.accent_bg}; color: {c.text}; }}
QComboBox QAbstractItemView::item:selected {{ background: {c.accent_bg}; color: {c.text}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c.button_border}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:horizontal {{ background: {c.button_border}; border-radius: 4px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {c.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QFrame#mock, QFrame#titledCard {{ background: {c.base}; border: 1px solid {c.border}; border-radius: {CORNER_RADIUS}px; }}
QWidget#npTitle {{ background: {c.strip}; border-top-left-radius: {CORNER_RADIUS - 1}px; border-top-right-radius: {CORNER_RADIUS - 1}px; }}
QWidget#npTitle QLabel {{ background: transparent; color: {c.text}; padding: 6px 10px; }}
QLabel#npTitleText {{ font-weight: bold; }}
QLabel#npGeometry {{ color: {c.muted}; }}
QLabel#npMenu {{ background: {c.strip}; color: {c.muted}; padding: 2px 10px 6px 10px; }}
QTabWidget#npTabs::pane {{ border: none; background: {c.base}; }}
QTabWidget#npTabs QTabBar {{ background: {c.strip}; }}
QTabBar#stripTabs {{ background: transparent; }}
QTabWidget#npTabs QTabBar::tab, QTabBar#stripTabs::tab {{ background: transparent; color: {c.muted}; padding: 6px 14px; border: none; border-top-left-radius: {ROW_RADIUS}px; border-top-right-radius: {ROW_RADIUS}px; margin-right: 2px; }}
QTabWidget#npTabs QTabBar::tab:selected, QTabBar#stripTabs::tab:selected {{ background: {c.window}; color: {c.text}; border: none; }}
QTabWidget#npTabs QTabBar::tab {{ margin-top: 1px; }}
QTabBar#stripTabs::tab:selected {{ font-weight: bold; }}
QTabBar#stripTabs::tab:hover {{ color: {c.text}; }}
QTabWidget#npTabs QPlainTextEdit {{ background: {c.base}; color: {c.text}; border: none; selection-background-color: {c.accent}; selection-color: {c.select_fg}; }}
QWidget#npStatus {{ background: {c.window}; border-bottom-left-radius: {CORNER_RADIUS - 1}px; border-bottom-right-radius: {CORNER_RADIUS - 1}px; }}
QWidget#npStatus QLabel {{ background: transparent; color: {c.muted}; padding: 4px 10px; }}
QFrame#rawCard {{ background: {c.base}; border: 1px solid {c.border}; border-radius: {CORNER_RADIUS}px; }}
QFrame#rawCard QLabel {{ background: transparent; color: {c.muted}; }}
QFrame#rawCard QPlainTextEdit {{ background: transparent; color: {c.text}; border: none; }}
QFrame#rawCard QComboBox {{ background: {c.alt}; color: {c.text}; border: 1px solid {c.border}; border-radius: {ROW_RADIUS}px; padding: 3px 8px; }}
QFrame#rawCard QComboBox:hover {{ background: {c.hover}; }}
QFrame#rawCard QTreeWidget {{ background: transparent; color: {c.text}; border: none; }}
QFrame#rawCard QHeaderView {{ background: transparent; }}
QFrame#rawCard QHeaderView::section {{ background: transparent; color: {c.muted}; border: none; padding: 3px 6px; }}
"""


def pill(text, kind):
    label = QLabel(text)
    label.setStyleSheet(PILL_STYLE.format(*colors.pills[kind]))
    return label


def group_source(group):
    short = group.split(" (")[0]
    if short in HIVE_GROUPS:
        return HIVE_SOURCE
    return "delta" if short == "State record" or group.startswith("Settings (from state record") else "window" if short == "Window" else "tab"


def row_fields(group, key, value):
    short = group.split(" (")[0]
    source = group_source(group)
    if short == "Setting values":
        return source, (f"Value {key} (",)
    if key.startswith("Unidentified bytes"):
        return source, ("Unidentified bytes",)
    if short == "Edit records":
        match = re.match(r"#(\d+)", key)
        return source, (f"Edit #{match.group(1)} ",) if match else ()
    if short == "Window" and key == "This tab":
        return source, (f"Tab {value.split()[0]} GUID",)
    return source, ROW_LINKS.get((short, key), ())


def own_row_painting(view, base=None, text=None):
    palette = view.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
    if base is not None:
        palette.setColor(QPalette.ColorRole.Base, QColor(base))
        palette.setColor(QPalette.ColorRole.Text, QColor(text))
    view.setPalette(palette)


class PopupStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if widget is not None and widget.metaObject().className() == POPUP_CONTAINER:
            painter.fillRect(option.rect, QColor(colors.window))
            return
        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        if widget is None or widget.metaObject().className() != POPUP_CONTAINER:
            super().drawControl(element, option, painter, widget)


class PopupOutline(QWidget):
    def __init__(self, container):
        super().__init__(container)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        container.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(obj.rect())
            self.raise_()
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(colors.button_border))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class ChevronCombo(QComboBox):
    def __init__(self):
        super().__init__()
        self.setView(QListView())
        container = self.view().window()
        self.popup_style = PopupStyle(QApplication.style().objectName())
        container.setStyle(self.popup_style)
        container.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint)
        self.popup_outline = PopupOutline(container)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(colors.text if self.underMouse() else colors.muted), CHEVRON_STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() - CHEVRON_RIGHT, self.height() / 2
        painter.drawPolyline(QPolygonF([QPointF(x - CHEVRON_HALF_WIDTH, y - CHEVRON_HALF_HEIGHT), QPointF(x, y + CHEVRON_HALF_HEIGHT), QPointF(x + CHEVRON_HALF_WIDTH, y - CHEVRON_HALF_HEIGHT)]))
        painter.end()


class FlowLayout(QLayout):
    def __init__(self, parent=None, gap=6):
        super().__init__(parent)
        self.entries = []
        self.gap = gap

    def addItem(self, item):
        self.entries.append(item)

    def count(self):
        return len(self.entries)

    def itemAt(self, i):
        return self.entries[i] if 0 <= i < len(self.entries) else None

    def takeAt(self, i):
        return self.entries.pop(i) if 0 <= i < len(self.entries) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, False)

    def minimumSize(self):
        size = QSize()
        for item in self.entries:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        return self.minimumSize()

    def arrange(self, rect, measure_only):
        x, y, row_height = rect.x(), rect.y(), 0
        for item in self.entries:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and row_height > 0:
                x, y, row_height = rect.x(), y + row_height + self.gap, 0
            if not measure_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self.gap
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()


class HoverTree(QTreeWidget):
    hovered = pyqtSignal(object)
    left = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.hover = QPersistentModelIndex()
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def is_hover(self, index):
        return self.hover.isValid() and index.siblingAtColumn(0) == QModelIndex(self.hover).siblingAtColumn(0)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = self.indexAt(event.position().toPoint())
        new = QPersistentModelIndex(index) if index.isValid() else QPersistentModelIndex()
        if new != self.hover:
            self.hover = new
            self.viewport().update()
            self.hovered.emit(self.itemFromIndex(index) if index.isValid() else None)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Leave:
            self.hover = QPersistentModelIndex()
            self.viewport().update()
            self.left.emit()
        return super().viewportEvent(event)


class RowDelegate(QStyledItemDelegate):
    def __init__(self, view, pick=False):
        super().__init__(view)
        self.view, self.pick = view, pick

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), ROW_MIN_HEIGHT))
        if index.data(SWATCH_ROLE):
            size.setWidth(size.width() + SWATCH_TEXT_INSET)
        return size

    def paint(self, painter, option, index):
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if index.column() == 0 and (selected or self.view.is_hover(index)):
            row = QRectF(option.rect.left() + 0.5, option.rect.top() + 1, self.view.viewport().width() - option.rect.left() - 2, option.rect.height() - 2)
            painter.setBrush(QColor((colors.select_bg if self.pick else colors.accent_bg) if selected else colors.hover))
            painter.drawRoundedRect(row, ROW_RADIUS, ROW_RADIUS)
        swatch = index.data(SWATCH_ROLE)
        if swatch:
            painter.setBrush(QColor(swatch))
            painter.drawRoundedRect(QRectF(option.rect).adjusted(1, 2, -1, -2), ROW_RADIUS, ROW_RADIUS)
        painter.restore()
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_Selected & ~QStyle.StateFlag.State_MouseOver & ~QStyle.StateFlag.State_HasFocus
        if swatch:
            opt.rect = option.rect.adjusted(SWATCH_TEXT_INSET, 0, 0, 0)
        if selected and not swatch:
            opt.palette.setColor(QPalette.ColorRole.Text, QColor(colors.select_fg if self.pick else colors.accent_fg))
        super().paint(painter, opt, index)


class HexView(QPlainTextEdit):
    hovered = pyqtSignal(int)
    left = pyqtSignal()
    per_row_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(fonts.qfont(fonts.MONO, RAW_FONT_SIZE))
        self.viewport().setMouseTracking(True)
        self.prefix = self.length = 0
        self.per_row = BYTES_PER_ROW
        self.regions, self.region_starts, self.selected_ranges, self.groups = [], [], [], []

    def gap_after(self, per_row=None):
        per_row = per_row or self.per_row
        return HEX_GAP_AFTER if per_row > HEX_GAP_AFTER else per_row

    def hex_area(self, per_row=None):
        per_row = per_row or self.per_row
        return per_row * 3 + (per_row > HEX_GAP_AFTER)

    @property
    def row_len(self):
        return self.prefix + self.hex_area() + 1 + self.per_row + 1

    def choose_per_row(self):
        char_width = QFontMetricsF(self.font()).horizontalAdvance("0")
        room = self.width() - 2 * self.frameWidth() - self.verticalScrollBar().sizeHint().width() - 2 * self.document().documentMargin()
        for per_row in RAW_ROW_SIZES:
            if (self.prefix + self.hex_area(per_row) + 1 + per_row) * char_width + 2 * BYTE_PAD_X <= room:
                return per_row
        return RAW_ROW_SIZES[-1]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.length and self.choose_per_row() != self.per_row:
            self.per_row_changed.emit()

    def set_groups(self, groups):
        self.groups = groups
        self.viewport().update()

    def set_regions(self, regions):
        self.regions, self.region_starts = regions, [r[0] for r in regions]
        self.viewport().update()

    def set_selected(self, ranges):
        self.selected_ranges = ranges
        self.viewport().update()

    def hex_start(self, row, i):
        return row * self.row_len + self.prefix + i * 3 + (i >= self.gap_after())

    def ascii_start(self, row, i):
        return row * self.row_len + self.prefix + self.hex_area() + 1 + i

    def spans(self, start, end, with_ascii=True):
        end = min(end, self.length)
        for row in range(start // self.per_row, (end - 1) // self.per_row + 1):
            first, last = max(start - row * self.per_row, 0), min(end - 1 - row * self.per_row, self.per_row - 1)
            yield self.hex_start(row, first), self.hex_start(row, last) + 2, False
            if with_ascii:
                yield self.ascii_start(row, first), self.ascii_start(row, last) + 1, True

    def row_boxes(self, lo, hi):
        i = max(bisect.bisect_right(self.region_starts, lo) - 1, 0)
        for start, end, color in self.regions[i:]:
            if start >= hi:
                break
            if end > lo:
                yield start, end, color, False
        for start, end in self.selected_ranges:
            if start < hi and end > lo:
                yield start, end, QColor(colors.select_bg), True

    def box(self, left, geometry, c0, c1, char_width, pad=BYTE_PAD_X):
        return QRectF(left + c0 * char_width - pad, geometry.top() + BYTE_PAD_Y, (c1 - c0) * char_width + 2 * pad, geometry.height() - 2 * BYTE_PAD_Y)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.length:
            first = self.cursorForPosition(QPoint(0, event.rect().top())).blockNumber()
            last = min(self.cursorForPosition(QPoint(0, event.rect().bottom())).blockNumber(), (self.length - 1) // self.per_row)
            char_width = QFontMetricsF(self.font()).horizontalAdvance("0")
            left = self.contentOffset().x() + self.document().documentMargin()
            gap, area = self.gap_after(), self.hex_area()
            for row in range(first, last + 1):
                geometry = self.blockBoundingGeometry(self.document().findBlockByNumber(row)).translated(self.contentOffset())
                lo, hi = row * self.per_row, min(row * self.per_row + self.per_row, self.length)
                for start, end, color in self.groups:
                    if start < hi and end > lo:
                        a, b = max(start, lo) - lo, min(end, hi) - lo - 1
                        rect = self.box(left, geometry, self.prefix + a * 3 + (a >= gap), self.prefix + b * 3 + (b >= gap) + 2, char_width).adjusted(0, -BYTE_PAD_Y, 0, BYTE_PAD_Y)
                        painter.setBrush(color.darker(GROUP_DARKEN))
                        painter.drawRoundedRect(rect, GROUP_RADIUS, GROUP_RADIUS)
                for start, end, color, selected in self.row_boxes(lo, hi):
                    a, b = max(start, lo) - lo, min(end, hi) - lo - 1
                    hex_cols = (self.prefix + a * 3 + (a >= gap), self.prefix + b * 3 + (b >= gap) + 2)
                    ascii_cols = (self.prefix + area + 1 + a, self.prefix + area + 2 + b)
                    painter.setBrush(color)
                    radius = SELECT_RADIUS if selected else BYTE_RADIUS
                    inset = GROUP_INNER_INSET if not selected and any(low <= start and end <= high for low, high, _ in self.groups) else 0
                    painter.drawRoundedRect(self.box(left, geometry, *hex_cols, char_width, BYTE_PAD_X - inset), radius, radius)
                    if selected:
                        painter.drawRoundedRect(self.box(left, geometry, *ascii_cols, char_width, ASCII_PAD_X), radius, radius)
        painter.end()
        super().paintEvent(event)

    def byte_at(self, point):
        if not self.length:
            return -1
        row, col = divmod(self.cursorForPosition(point).position(), self.row_len)
        rel = col - self.prefix
        area = self.hex_area()
        i = (rel - (rel > self.gap_after() * 3)) // 3 if 0 <= rel < area else rel - area - 1
        index = row * self.per_row + i
        return index if 0 <= i < self.per_row and index < self.length else -1

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.hovered.emit(self.byte_at(event.position().toPoint()))

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Leave:
            self.left.emit()
        return super().viewportEvent(event)


class RawPage(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("rawCard")
        self.sources = []
        self.obj = None
        self.kind = ""
        self.selected = ()
        self.items = []
        self.starts = []
        self.source_box = ChevronCombo()
        self.note = QLabel()
        self.hex = HexView()
        self.legend = QWidget()
        self.legend_layout = FlowLayout(self.legend)
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.table = HoverTree()
        self.table.setHeaderLabels(["Offset", "Length", "Field", "Value"])
        self.table.setRootIsDecorated(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setItemDelegate(RowDelegate(self.table, True))
        self.restyle()
        top = QHBoxLayout()
        top.addWidget(self.source_box, 1)
        top.addWidget(self.note)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GUI_MARGIN, GUI_MARGIN, GUI_MARGIN, GUI_MARGIN)
        layout.addLayout(top)
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.addWidget(self.legend)
        lower_layout.addWidget(self.info)
        lower_layout.addWidget(self.table, 1)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.hex)
        self.splitter.addWidget(lower)
        self.splitter.setStretchFactor(0, RAW_SPLIT_STRETCH[0])
        self.splitter.setStretchFactor(1, RAW_SPLIT_STRETCH[1])
        layout.addWidget(self.splitter, 1)
        self.placeholder = QLabel(EMPTY_RAW_TEXT)
        self.placeholder.setWordWrap(True)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder, 1)
        self.parts = (self.source_box, self.note, self.splitter)
        self.set_empty(True)
        self.source_box.currentIndexChanged.connect(self.load)
        self.hex.hovered.connect(self.on_hover)
        self.hex.left.connect(self.clear_highlight)
        self.hex.per_row_changed.connect(self.reflow)
        self.table.hovered.connect(lambda item: self.clear_highlight() if item is None else self.highlight([item.data(0, Qt.ItemDataRole.UserRole)], True))
        self.table.left.connect(self.clear_highlight)
        self.table.currentItemChanged.connect(lambda item, _previous: item is not None and self.highlight([item.data(0, Qt.ItemDataRole.UserRole)], True))

    def restyle(self):
        own_row_painting(self.table, colors.base, colors.text)

    def set_empty(self, empty):
        for part in self.parts:
            part.setVisible(not empty)
        self.placeholder.setVisible(empty)

    def set_sources(self, sources):
        keep = self.kind
        self.sources = sources
        self.source_box.blockSignals(True)
        self.source_box.clear()
        self.source_box.addItems([f"{label} - {os.path.basename(obj.path)}" for label, obj, _ in sources])
        index = next((i for i, (_, _, kind) in enumerate(sources) if kind == keep), 0)
        self.source_box.setCurrentIndex(index)
        self.source_box.blockSignals(False)
        self.load(index)

    def set_legend(self, kinds, groups=()):
        while self.legend_layout.count():
            widget = self.legend_layout.takeAt(0).widget()
            widget.setParent(None)
            widget.deleteLater()
        for text, color in [KIND_COLORS[kind] for kind in kinds] + list(groups):
            chip = QLabel(text)
            chip.setStyleSheet(CHIP_STYLE.format(color))
            self.legend_layout.addWidget(chip)
        self.legend.updateGeometry()

    def clear(self):
        self.obj, self.selected, self.items, self.starts = None, (), [], []
        self.hex.clear()
        self.hex.length = 0
        self.hex.set_regions([])
        self.hex.set_selected([])
        self.table.clear()
        self.set_legend([])
        self.note.setText("")
        self.set_empty(True)

    def load(self, i):
        if not 0 <= i < len(self.sources):
            self.clear()
            return
        self.set_empty(False)
        self.obj, self.kind =self.sources[i][1], self.sources[i][2]
        width = 8 if len(self.obj.raw) > 0xFFFF else 4
        self.hex.prefix, self.hex.length = width + 2, min(len(self.obj.raw), MAX_RAW_BYTES)
        self.hex.per_row = self.hex.choose_per_row()
        self.render_hex()
        self.note.setText(f"first {MAX_RAW_BYTES // 1024} KiB of {len(self.obj.raw)} bytes" if len(self.obj.raw) > MAX_RAW_BYTES else f"{len(self.obj.raw)} bytes")
        self.hex.set_regions([(f.start, f.end, QColor(KIND_COLORS[f.kind][1])) for f in self.obj.fields if f.end > f.start and f.start < self.hex.length])
        grouped = {}
        for f in self.obj.fields:
            if f.group and f.start < self.hex.length:
                low, high, kind = grouped.get(f.group, (f.start, f.end, f.kind))
                grouped[f.group] = (min(low, f.start), max(high, f.end), kind)
        self.hex.set_groups([(low, high, QColor(KIND_COLORS[kind][1])) for low, high, kind in grouped.values()])
        self.set_legend(list(dict.fromkeys(f.kind for f in self.obj.fields)), [(name, QColor(KIND_COLORS[kind][1]).darker(GROUP_DARKEN).name()) for name, (_, _, kind) in grouped.items()])
        self.starts = [f.start for f in self.obj.fields]
        self.table.clear()
        self.items = []
        for index, f in enumerate(self.obj.fields):
            item = QTreeWidgetItem([f"0x{f.start:0{width}X}", str(f.end - f.start), f.name, f.value])
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            item.setData(2, SWATCH_ROLE, KIND_COLORS[f.kind][1])
            item.setForeground(2, QColor(BYTE_FG))
            item.setToolTip(3, f.value)
            self.table.addTopLevelItem(item)
            self.items.append(item)
        for column in (0, 1, 2):
            self.table.resizeColumnToContents(column)
        self.selected = ()
        self.hex.setExtraSelections([])
        self.hex.set_selected([])
        self.info.setText(HOVER_HINT)

    def render_hex(self):
        hex_view = self.hex
        shown = self.obj.raw[:hex_view.length]
        per_row, gap, width = hex_view.per_row, hex_view.gap_after(), hex_view.prefix - 2
        hex_view.setPlainText("\n".join(
            f"{r:0{width}x}  " + "".join(f"{b:02x} " + (" " if k == gap - 1 and gap < per_row else "") for k, b in enumerate(shown[r:r + per_row])).ljust(hex_view.hex_area()) + " " + "".join(chr(b) if 32 <= b < 127 else "." for b in shown[r:r + per_row])
            for r in range(0, len(shown), per_row)))
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(BYTE_FG))
        cursor = QTextCursor(hex_view.document())
        cursor.beginEditBlock()
        for f in self.obj.fields:
            if f.end > f.start and f.start < hex_view.length:
                for a, b, _ in hex_view.spans(f.start, f.end, False):
                    cursor.setPosition(a)
                    cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
                    cursor.mergeCharFormat(fmt)
        dim = QTextCharFormat()
        dim.setForeground(QColor(colors.muted))
        for row in range(len(shown) // per_row + (len(shown) % per_row > 0)):
            cursor.setPosition(row * hex_view.row_len)
            cursor.setPosition(row * hex_view.row_len + width, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(dim)
        cursor.endEditBlock()

    def reflow(self):
        hex_view = self.hex
        top = hex_view.cursorForPosition(QPoint(0, 0)).blockNumber() * hex_view.per_row
        hex_view.per_row = hex_view.choose_per_row()
        self.render_hex()
        hex_view.verticalScrollBar().setValue(top // hex_view.per_row)
        if self.selected:
            indices, self.selected = self.selected, ()
            self.highlight(list(indices), False)
        hex_view.viewport().update()

    def show_source(self, kind):
        for i, (_, obj, source_kind) in enumerate(self.sources):
            if source_kind == kind:
                if self.obj is not obj:
                    self.source_box.setCurrentIndex(i)
                return i
        return -1

    def show_fields(self, kind, names):
        if self.show_source(kind) >= 0:
            indices = [j for j, f in enumerate(self.obj.fields) if f.name.startswith(names)]
            if indices:
                self.highlight(indices, True)

    def on_hover(self, byte):
        index = bisect.bisect_right(self.starts, byte) - 1
        if byte < 0 or index < 0 or byte >= self.obj.fields[index].end:
            self.clear_highlight()
        elif (index,) != self.selected:
            self.highlight([index], False)

    def clear_highlight(self):
        if self.obj is None or not self.selected:
            return
        self.selected = ()
        self.hex.setExtraSelections([])
        self.hex.set_selected([])
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setCurrentItem(None)
        self.table.blockSignals(False)
        self.table.viewport().update()
        self.info.setText(HOVER_HINT)

    def highlight(self, indices, scroll_hex):
        key = tuple(indices)
        if key == self.selected and not scroll_hex:
            return
        self.selected = key
        selections = []
        ranges = []
        for index in indices:
            f = self.obj.fields[index]
            if f.end > f.start and f.start < self.hex.length:
                ranges.append((f.start, f.end))
                for a, b, _ in self.hex.spans(f.start, f.end):
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = QTextCursor(self.hex.document())
                    selection.cursor.setPosition(a)
                    selection.cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
                    selection.format.setForeground(QColor(colors.select_fg))
                    selections.append(selection)
        self.hex.setExtraSelections(selections)
        self.hex.set_selected(ranges)
        first = self.obj.fields[indices[0]]
        self.table.blockSignals(True)
        self.table.setCurrentItem(self.items[indices[0]])
        self.table.blockSignals(False)
        self.table.scrollToItem(self.items[indices[0]])
        self.info.setText((f"{first.name} - bytes {first.start} to {first.end - 1} ({first.end - first.start}): {first.value}" if first.end > first.start else f"{first.name} - empty at byte {first.start}") + (f"  (+{len(indices) - 1} more)" if len(indices) > 1 else ""))
        if scroll_hex and selections:
            cursor = QTextCursor(self.hex.document())
            cursor.setPosition(selections[0].cursor.selectionStart())
            self.hex.setTextCursor(cursor)
            self.hex.ensureCursorVisible()
