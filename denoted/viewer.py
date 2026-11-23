import os
import sys

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QStackedWidget, QStyle, QTabBar, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import export, fonts, mockup, widgets
from . import format as dnf
from .scheme import available_schemes, build_palette, colors_for, save_scheme_name, saved_scheme
from .widgets import GUI_MARGIN, ChevronCombo, HoverTree, RawPage, RowDelegate, build_style, group_source, own_row_painting, pill, row_fields

APP_TITLE = "Denoted"
INSPECTOR_STYLE = "QTreeWidget { border: none; background: transparent; padding: 4px; }"
STRIP_BUTTON_PAD = 4
TEXT_FONT_SIZE = 11
WINDOW_SIZE = (1440, 900)
SPLITTER_SIZES = (240, 560, 600)
RIGHT_SPLITTER_SIZES = (330, 500)
KEY_COLUMN_GAP = 14
COPY_HINT ="Double-click a value to copy it"
NO_ITEM = -1
FILE_FILTER = "Notepad state files (*.bin);;All files (*)"
MODIFIED_MARK = " ●"
ACTIVE_MARK = " (Active)"
NAV_LEGEND = "Bold, (Active): active tab\n●: unsaved changes"
TIP_ACTIVE = "Active tab: the tab that was selected in this Notepad window when its state was saved."
TIP_MODIFIED = "Unsaved changes: the tab has unsaved text or edit records."
TIP_WINDOW = "A Notepad window (from its WindowState file). Its tabs are listed below."
TIP_NO_WINDOW = "Tab files with no WindowState file, so the window and tab order are unknown."
TIP_SETTINGS = "Notepad's settings.dat (a registry hive): saved settings with the time each was last written."
TIP_GROUP = "Folder these windows were loaded from."
TIP_GROUP_LIVE = "User profile on this computer these windows were loaded from."
PREVIEW_SIZE = (1200, 640)
MIDDLE_SPLITTER_SIZES = (560, 220)
SCAN_HINT = "Double-click a path to copy it."
LIVE_DIALOG_SIZE = (860, 360)
LIST_DIALOG_SIZE = (760, 340)
SCREENSHOT_FILTER = "PNG image (*.png)"
SCREENSHOT_NAME = "notepad_mockup.png"


def save_image(parent, image):
    path, _ = QFileDialog.getSaveFileName(parent, "Save screenshot", SCREENSHOT_NAME, SCREENSHOT_FILTER)
    if path and not image.save(os.path.normpath(path)):
        QMessageBox.warning(parent, APP_TITLE, f"Could not save:\n{os.path.normpath(path)}")


class PreviewDialog(QDialog):
    def __init__(self, parent, image, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(*PREVIEW_SIZE)
        self.image = image
        self.pixmap = QPixmap.fromImage(image)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.label)
        self.fit = QCheckBox("Fit to window")
        self.fit.setChecked(True)
        self.fit.toggled.connect(self.refresh)
        save = QPushButton("Save as PNG…")
        save.clicked.connect(lambda: save_image(self, self.image))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        for w in (self.fit, save):
            buttons.addWidget(w)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(buttons)

    def refresh(self):
        self.label.setPixmap(self.pixmap.scaled(self.scroll.viewport().size() - QSize(4, 4), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) if self.fit.isChecked() else self.pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()


class ListDialog(QDialog):
    def __init__(self, parent, title, lines):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(*LIST_DIALOG_SIZE)
        text = QPlainTextEdit("\n".join(lines))
        text.setReadOnly(True)
        text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        copy = QPushButton("Copy all")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(text.toPlainText()))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(copy)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(text, 1)
        layout.addLayout(buttons)


class NotepadMock(QFrame):
    changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("mock")
        self.entries = []
        self.title = QLabel("Notepad")
        self.title.setObjectName("npTitleText")
        self.geometry_label = QLabel()
        self.geometry_label.setObjectName("npGeometry")
        self.geometry_label.hide()
        title_bar = QWidget()
        title_bar.setObjectName("npTitle")
        title_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(self.title, 1)
        title_row.addWidget(self.geometry_label)
        self.menu = QLabel("File      Edit      View")
        self.menu.setObjectName("npMenu")
        self.tabs = QTabWidget()
        self.tabs.setObjectName("npTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.status = QLabel()
        self.format_label = QLabel()
        self.zoom_label = QLabel()
        self.eol_label = QLabel()
        self.encoding_label = QLabel()
        status_bar = QWidget()
        status_bar.setObjectName("npStatus")
        status_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        status_row = QHBoxLayout(status_bar)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(16)
        status_row.addWidget(self.status)
        status_row.addWidget(self.format_label)
        status_row.addStretch(1)
        for w in (self.zoom_label, self.eol_label, self.encoding_label):
            status_row.addWidget(w)
        self.zoom_label.setToolTip("Zoom is not stored in the state files; 100% is assumed.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for w in (title_bar, self.menu, self.tabs, status_bar):
            layout.addWidget(w)
        self.tabs.currentChanged.connect(self.on_tab)

    def show_entries(self, entries, selected, window=None):
        self.geometry_label.setVisible(window is not None)
        if window is not None:
            left, top, right, bottom, width, height = window.geometry
            self.geometry_label.setText(f"{width} × {height}  at ({left}, {top})")
            self.geometry_label.setToolTip(f"Outer window rectangle in virtual-desktop pixels, including the invisible resize frame:\nleft {left}, top {top}, right {right}, bottom {bottom}\nwidth {width}, height {height}")
        self.tabs.blockSignals(True)
        self.tabs.clear()
        self.entries = entries
        for i, e in enumerate(entries):
            cfg, sel, _ = dnf.effective(e)
            edit = QPlainTextEdit()
            edit.setReadOnly(True)
            edit.setFont(fonts.qfont(fonts.MONO, TEXT_FONT_SIZE))
            edit.setPlainText(dnf.entry_text(e))
            if dnf.reloads_from_path(e):
                edit.setPlaceholderText(dnf.FROM_PATH_NOTE)
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if cfg and cfg.word_wrap else QPlainTextEdit.LineWrapMode.NoWrap)
            if cfg and cfg.rtl:
                edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            last = edit.document().characterCount() - 1
            cursor = edit.textCursor()
            cursor.setPosition(min(sel[0], last))
            cursor.setPosition(min(sel[1], last), QTextCursor.MoveMode.KeepAnchor)
            edit.setTextCursor(cursor)
            edit.cursorPositionChanged.connect(self.refresh)
            self.tabs.addTab(edit, dnf.entry_title(e) + (MODIFIED_MARK if dnf.entry_modified(e) else ""))
            self.tabs.setTabToolTip(i, e.tab.file_path if e.tab is not None and e.tab.has_path else e.guid)
        if entries:
            self.tabs.setCurrentIndex(min(max(selected, 0), len(entries) - 1))
        self.tabs.blockSignals(False)
        self.on_tab(self.tabs.currentIndex())

    def refresh(self):
        i = self.tabs.currentIndex()
        if not 0 <= i < len(self.entries):
            self.title.setText("Notepad")
            for w in (self.status, self.format_label, self.zoom_label, self.eol_label, self.encoding_label):
                w.setText("")
            return
        eol, enc = dnf.entry_format(self.entries[i])
        edit = self.tabs.widget(i)
        cursor = edit.textCursor()
        has_tab = self.entries[i].tab is not None
        self.title.setText(f"{dnf.entry_title(self.entries[i])} - Notepad")
        self.status.setText(f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}        {len(edit.toPlainText())} characters" if has_tab else "")
        self.format_label.setText(dnf.formatting_name(dnf.effective(self.entries[i])[0]) if has_tab else "")
        self.zoom_label.setText(mockup.ASSUMED_ZOOM if has_tab else "")
        self.eol_label.setText(eol if has_tab else "")
        self.encoding_label.setText(enc if has_tab else "")

    def on_tab(self, i):
        self.refresh()
        self.changed.emit(i if 0 <= i < len(self.entries) else -1)


class LiveDialog(QDialog):
    def __init__(self, parent, users):
        super().__init__(parent)
        self.setWindowTitle("Open live system")
        self.resize(*LIVE_DIALOG_SIZE)
        self.users = users
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["User", "Notepad data", "Profile folder"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        for user in users:
            item = QTreeWidgetItem([user.name, f"{user.files} .bin file(s)" if user.files else user.problem, user.profile])
            item.setToolTip(2, user.state)
            if user.files:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if os.path.normcase(user.profile) == os.path.normcase(os.path.expanduser("~")) else Qt.CheckState.Unchecked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(item)
        for column in (0, 1):
            self.tree.resizeColumnToContents(column)
        select_all, select_none = QPushButton("Select all"), QPushButton("Select none")
        select_all.clicked.connect(lambda: self.check_all(Qt.CheckState.Checked))
        select_none.clicked.connect(lambda: self.check_all(Qt.CheckState.Unchecked))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Load")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(select_all)
        row.addWidget(select_none)
        row.addStretch()
        row.addWidget(self.buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Notepad data found for {sum(1 for u in users if u.files)} of {len(users)} user profile(s) on this computer. Tick the users to load."))
        layout.addWidget(self.tree)
        if any(u.problem.startswith("Access denied") for u in users):
            layout.addWidget(QLabel("Profiles marked \"Access denied\" can only be read when this program is run as administrator."))
        layout.addLayout(row)
        self.tree.itemChanged.connect(self.update_load)
        self.update_load()

    def check_all(self, state):
        for i, user in enumerate(self.users):
            if user.files:
                self.tree.topLevelItem(i).setCheckState(0, state)

    def selected(self):
        return [u for i, u in enumerate(self.users) if u.files and self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked]

    def update_load(self):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self.selected()))


def strip_bar(object_name, widget):
    bar = QWidget()
    bar.setObjectName(object_name)
    bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    row = QHBoxLayout(bar)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(widget)
    if isinstance(widget, QPushButton):
        row.setContentsMargins(GUI_MARGIN, STRIP_BUTTON_PAD, GUI_MARGIN, STRIP_BUTTON_PAD)
        row.addStretch(1)
    return bar


class StripTabs(QWidget):
    currentChanged = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.bar = QTabBar()
        self.bar.setObjectName("stripTabs")
        self.bar.setDrawBase(False)
        self.bar.setExpanding(False)
        self.bar.setUsesScrollButtons(True)
        self.pages = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(strip_bar("npTitle", self.bar))
        layout.addWidget(self.pages, 1)
        self.bar.currentChanged.connect(self.pages.setCurrentIndex)
        self.bar.currentChanged.connect(self.currentChanged)

    def addTab(self, page, text):
        self.pages.addWidget(page)
        return self.bar.addTab(text)

    def removeTab(self, i):
        self.pages.removeWidget(self.pages.widget(i))
        self.bar.removeTab(i)

    def count(self):
        return self.bar.count()

    def widget(self, i):
        return self.pages.widget(i)

    def tabText(self, i):
        return self.bar.tabText(i)

    def currentIndex(self):
        return self.bar.currentIndex()

    def setCurrentIndex(self, i):
        self.bar.setCurrentIndex(i)

    def setTabToolTip(self, i, text):
        self.bar.setTabToolTip(i, text)


class TitledCard(QFrame):
    def __init__(self, title, body, footer):
        super().__init__()
        self.setObjectName("titledCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if title:
            heading = QLabel(title)
            heading.setObjectName("npTitleText")
            layout.addWidget(strip_bar("npTitle", heading))
        layout.addWidget(body, 1)
        if isinstance(footer, str):
            footer = QLabel(footer)
            footer.setWordWrap(True)
        layout.addWidget(strip_bar("npStatus", footer))


class ScanPanel(TitledCard):
    def __init__(self):
        self.tree = HoverTree()
        self.tree.setItemDelegate(RowDelegate(self.tree))
        own_row_painting(self.tree)
        self.tree.setHeaderHidden(True)
        self.tree.setWordWrap(True)
        self.tree.setStyleSheet(INSPECTOR_STYLE)
        self.tree.itemDoubleClicked.connect(lambda item: item.data(0, Qt.ItemDataRole.UserRole) and QApplication.clipboard().setText(item.data(0, Qt.ItemDataRole.UserRole)))
        super().__init__("Scan details", self.tree, SCAN_HINT)

    def add_items(self, parent, items):
        for text, copy, children in items:
            item = QTreeWidgetItem(parent, [text])
            item.setData(0, Qt.ItemDataRole.UserRole, copy)
            self.add_items(item, children)
            item.setExpanded(True)

    def show_scan(self, sections):
        self.tree.clear()
        for name, items in sections:
            top = QTreeWidgetItem([name])
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            self.tree.addTopLevelItem(top)
            self.add_items(top, items)
            top.setExpanded(True)


class ExportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Export entries")
        self.format_box = ChevronCombo()
        for key, (label, _) in export.FORMATS.items():
            self.format_box.addItem(label, key)
        self.text_box = QCheckBox("Include tab text")
        self.text_box.setChecked(True)
        self.text_box.setToolTip("Unchecked: leaves out the tab text, the text added by edit records, the first-line titles of unsaved tabs and the rendered window picture.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Exports everything loaded: every window, tab, state record\nand skipped file."))
        layout.addWidget(self.format_box)
        layout.addWidget(self.text_box)
        layout.addWidget(buttons)

    def kind(self):
        return self.format_box.currentData()

    def include_text(self):
        return self.text_box.isChecked()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setAcceptDrops(True)
        self.views = []
        self.directory = None
        self.live_users = []
        self.file_kind = ""
        self.opened = ""
        self.current = NO_ITEM
        self.items = {}
        self.groups = []
        self.mock = NotepadMock()
        self.nav = HoverTree()
        self.nav.setObjectName("nav")
        self.nav.setHeaderHidden(True)
        self.nav.setIndentation(14)
        self.nav.setItemDelegate(RowDelegate(self.nav))
        own_row_painting(self.nav)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(GUI_MARGIN, GUI_MARGIN, GUI_MARGIN, GUI_MARGIN)
        left_layout.addWidget(TitledCard("Sources", self.nav, NAV_LEGEND))
        self.badge_row = QHBoxLayout()
        self.badge_row.setSpacing(6)
        mock_area = QWidget()
        mock_layout = QVBoxLayout(mock_area)
        mock_layout.setContentsMargins(0, 0, 0, 0)
        mock_layout.addWidget(self.mock, 1)
        mock_layout.addLayout(self.badge_row)
        self.scan_panel = ScanPanel()
        middle_split = QSplitter(Qt.Orientation.Vertical)
        middle_split.addWidget(mock_area)
        middle_split.addWidget(self.scan_panel)
        middle_split.setSizes(list(MIDDLE_SPLITTER_SIZES))
        middle_split.setStretchFactor(0, 1)
        middle_split.setChildrenCollapsible(False)
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(GUI_MARGIN, GUI_MARGIN, GUI_MARGIN, GUI_MARGIN)
        middle_layout.addWidget(middle_split)
        self.inspector = StripTabs()
        self.inspector.currentChanged.connect(self.show_tab_source)
        self.copy_button = QPushButton("Copy all")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_all)
        self.raw = RawPage()
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(TitledCard(None, self.inspector, self.copy_button))
        right_split.addWidget(self.raw)
        right_split.setSizes(list(RIGHT_SPLITTER_SIZES))
        right_split.setChildrenCollapsible(False)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(GUI_MARGIN, GUI_MARGIN, GUI_MARGIN, GUI_MARGIN)
        right_layout.addWidget(right_split)
        split = QSplitter(Qt.Orientation.Horizontal)
        for pane in (left, middle, right):
            split.addWidget(pane)
        split.setSizes(list(SPLITTER_SIZES))
        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)
        self.setCentralWidget(split)
        file_menu = self.menuBar().addMenu("&File")
        file_menu.setToolTipsVisible(True)
        live_action = self.add_actions(file_menu, (("Open &File…", "Ctrl+O", self.choose_file), ("Open &Directory…", "Ctrl+Shift+O", self.choose_directory), ("Open &Live System…", "Ctrl+L", self.open_live)))[2]
        live_action.setEnabled(dnf.IS_WINDOWS)
        live_action.setToolTip("Read this computer's Notepad data" if dnf.IS_WINDOWS else dnf.LIVE_UNAVAILABLE)
        self.recursive_action = QAction("Scan &subfolders recursively", self)
        self.recursive_action.setCheckable(True)
        self.recursive_action.setToolTip("Also load .bin files from every folder below the one you open. Each folder is kept as its own set, so copies of the same tab in different folders are not merged.")
        self.recursive_action.toggled.connect(self.reload_directory)
        file_menu.addAction(self.recursive_action)
        file_menu.addSeparator()
        self.export_action = self.add_actions(file_menu, (("&Export…", "Ctrl+E", self.export_report), ("E&xit", "Ctrl+Q", self.close)))[0]
        self.export_action.setEnabled(False)
        view_menu = self.menuBar().addMenu("&View")
        self.screenshot_actions = self.add_actions(view_menu, (("&Rendered Notepad window…", "Ctrl+R", self.show_screenshot), ("&Save rendered window as PNG…", "Ctrl+S", self.save_screenshot)))
        view_menu.addSeparator()
        self.scan_action = QAction("Scan &details", self, checkable=True)
        self.scan_action.setShortcut(QKeySequence("Ctrl+D"))
        self.scan_action.setChecked(True)
        self.scan_action.toggled.connect(self.scan_panel.setVisible)
        view_menu.addAction(self.scan_action)
        for action in self.screenshot_actions:
            action.setEnabled(False)
        theme_menu = self.menuBar().addMenu("&Theme")
        theme_group = QActionGroup(self)
        for name, scheme in available_schemes().items():
            action = QAction(name, self, checkable=True)
            action.setChecked(scheme == saved_scheme())
            action.triggered.connect(lambda _=False, name=name: self.set_scheme(name))
            theme_group.addAction(action)
            theme_menu.addAction(action)
        self.nav.currentItemChanged.connect(self.on_nav)
        self.mock.changed.connect(self.show_entry)
        hint = QLabel(COPY_HINT)
        hint.setObjectName("statusHint")
        self.statusBar().addPermanentWidget(hint)
        self.statusBar().showMessage(f"Open a state file, a TabState/WindowState folder{', or a live system' if dnf.IS_WINDOWS else ''} (File menu, or drop a file or folder here).")

    def set_scheme(self, name):
        save_scheme_name(name)
        apply_scheme(QApplication.instance(), available_schemes()[name])
        self.raw.restyle()
        if self.current != NO_ITEM:
            self.show_badges(self.mock.tabs.currentIndex())

    def add_actions(self, menu, items):
        actions = []
        for text, key, slot in items:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            menu.addAction(action)
            actions.append(action)
        return actions

    def screenshot(self):
        return mockup.render(self.views[self.current], self.mock.tabs.currentIndex())

    def show_screenshot(self):
        PreviewDialog(self, self.screenshot(), f"Rendered Notepad window - {self.views[self.current].label}").exec()

    def save_screenshot(self):
        save_image(self, self.screenshot())

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open state file", "", FILE_FILTER)
        if path:
            self.open_path(os.path.normpath(path))

    def choose_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Open folder with state files")
        if path:
            self.open_path(os.path.normpath(path))

    def file_directory(self):
        folder = os.path.dirname(os.path.abspath(self.opened))
        return dnf.Directory(os.path.abspath(self.opened), [folder], self.views, [], [dnf.ScannedFile(folder, os.path.basename(self.opened), self.file_kind)])

    def update_scan(self):
        directory = self.directory or (self.file_directory() if self.views else None)
        if directory is None:
            self.scan_panel.show_scan([])
            return
        mode = "file" if self.directory is None else "live system" if self.live_users else "recursive" if self.recursive_action.isChecked() else "not recursive"
        folders = [(folder, folder, [(f"{f.name}  -  {dnf.SCAN_KIND_LABELS[f.kind]}", os.path.join(folder, f.name), []) for f in directory.files if f.folder == folder]) for folder in directory.folders]
        self.scan_panel.show_scan([
            (f"Opened ({mode})", [(directory.root, directory.root, [])]),
            (f"Folders scanned ({len(directory.folders)}) - {len(directory.files)} file(s)", folders),
            (f"Files skipped ({len(directory.skipped)})", [(s, s, []) for s in directory.skipped]),
        ])

    def reload_directory(self):
        if self.directory is not None and not self.live_users:
            self.open_directory(self.directory.root)

    def export_report(self):
        dialog = ExportDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        label, ext = export.FORMATS[dialog.kind()]
        path, _ = QFileDialog.getSaveFileName(self, "Export entries", f"notepad_report.{ext}", f"{label} (*.{ext})")
        if not path:
            return
        path = os.path.normpath(path)
        try:
            export.export(self.directory or self.file_directory(), path, dialog.kind(), dialog.include_text())
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, f"{path}\n\n{e}")
            return
        self.statusBar().showMessage(f"Exported: {path}", 8000)

    def open_path(self, path):
        path = os.path.normpath(path)
        self.opened = path
        (self.open_directory if os.path.isdir(path) else self.open_file)(path)

    def open_file(self, path):
        try:
            kind, view = dnf.file_view(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_TITLE, f"{path}\n\n{e}")
            return
        self.directory = None
        self.live_users = []
        self.file_kind = kind
        self.set_views([view])
        self.statusBar().showMessage(f"{path}  ({kind})")

    def open_directory(self, path):
        try:
            directory = dnf.load_directory(path, self.recursive_action.isChecked())
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, f"{path}\n\n{e}")
            return
        self.show_directory(directory, f"{path}{' (recursive)' if self.recursive_action.isChecked() else ''}", [])

    def open_live(self):
        dialog = LiveDialog(self, dnf.find_live_users())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            users = dialog.selected()
            self.show_directory(dnf.load_live(users), f"Live system: {', '.join(u.name for u in users)}", users)

    def show_directory(self, directory, source, live_users):
        if not directory.views:
            QMessageBox.information(self, APP_TITLE, "No tab or window state files found in:\n" + "\n".join(directory.folders) + ("\n\nSkipped:\n" + "\n".join(directory.skipped) if directory.skipped else ""))
            return
        self.directory = directory
        self.live_users = live_users
        self.set_views(directory.views)
        windows = [v for v in directory.views if not v.is_settings]
        self.statusBar().showMessage(f"{source}: {sum(len(v.entries) for v in windows)} tab(s) in {len(windows)} view(s) from {len(directory.folders)} folder(s), {sum(not v.settings.problem for v in directory.views if v.is_settings)} settings file(s), {len(directory.skipped)} file(s) skipped")

    def set_views(self, views):
        self.views = views
        self.export_action.setEnabled(bool(views))
        self.update_scan()
        self.current = NO_ITEM
        self.build_nav()
        self.nav.setCurrentItem(self.items[(0, NO_ITEM)])

    def nav_item(self, parent, text, view_index, tab_index, bold=False, icon=None, tip=""):
        item = QTreeWidgetItem(parent, [text])
        item.setToolTip(0, tip)
        item.setData(0, Qt.ItemDataRole.UserRole, view_index)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, tab_index)
        if bold:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        if icon is not None:
            item.setIcon(0, self.style().standardIcon(icon))
        self.items[(view_index, tab_index)] = item
        return item

    def build_nav(self):
        self.nav.blockSignals(True)
        self.nav.clear()
        self.items = {}
        folders = {}
        for vi, view in enumerate(self.views):
            group, _, label = view.label.rpartition(": ")
            parent = self.nav.invisibleRootItem()
            if group:
                if group not in folders:
                    folders[group] = QTreeWidgetItem(self.nav.invisibleRootItem(), [group])
                    folders[group].setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon if self.live_users else QStyle.StandardPixmap.SP_DirIcon))
                    font = folders[group].font(0)
                    font.setBold(True)
                    folders[group].setFont(0, font)
                    folders[group].setToolTip(0, TIP_GROUP_LIVE if self.live_users else TIP_GROUP)
                parent = folders[group]
            if view.is_settings:
                self.nav_item(parent, label, vi, NO_ITEM, icon=QStyle.StandardPixmap.SP_FileDialogDetailedView, tip=TIP_SETTINGS)
                continue
            window_item = self.nav_item(parent, label, vi, NO_ITEM, icon=QStyle.StandardPixmap.SP_DesktopIcon if view.window else QStyle.StandardPixmap.SP_FileIcon, tip=TIP_WINDOW if view.window else TIP_NO_WINDOW)
            for ti, e in enumerate(view.entries):
                active, modified = view.window is not None and view.window.selected == ti, dnf.entry_modified(e)
                self.nav_item(window_item, dnf.entry_title(e) + (ACTIVE_MARK if active else "") + (MODIFIED_MARK if modified else ""), vi, ti, bold=active, tip="\n".join(filter(None, (TIP_ACTIVE if active else "", TIP_MODIFIED if modified else ""))))
        self.nav.expandAll()
        self.nav.blockSignals(False)

    def on_nav(self, item, _previous=None):
        if item is None or item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        view_index, tab_index = item.data(0, Qt.ItemDataRole.UserRole), item.data(0, Qt.ItemDataRole.UserRole + 1)
        if view_index == self.current and tab_index != NO_ITEM:
            self.mock.tabs.setCurrentIndex(tab_index)
        else:
            self.show_view(view_index, None if tab_index == NO_ITEM else tab_index)

    def show_view(self, i, tab=None):
        self.current = i
        view = self.views[i]
        self.mock.show_entries(view.entries, view.window.selected if tab is None and view.window else tab or 0, view.window)
        for action in self.screenshot_actions:
            action.setEnabled(view.window is not None and bool(view.entries))

    def show_entry(self, i):
        item = self.items.get((self.current, i))
        if item is not None:
            self.nav.blockSignals(True)
            self.nav.setCurrentItem(item)
            self.nav.blockSignals(False)
        self.show_inspector(i)
        self.show_badges(i)

    def show_inspector(self, i):
        keep = self.inspector.tabText(self.inspector.currentIndex())
        self.inspector.blockSignals(True)
        while self.inspector.count():
            page = self.inspector.widget(0)
            self.inspector.removeTab(0)
            page.deleteLater()
        view = self.views[self.current]
        if view.is_settings:
            self.groups = dnf.describe_settings(view.settings, [v for v in self.views if v.settings is view.settings and not v.is_settings], compact=True)
        else:
            self.groups = dnf.describe_entry(view.entries[i], view, i) if i >= 0 else []
        self.copy_button.setEnabled(bool(self.groups))
        for name, rows in self.groups:
            page = HoverTree()
            page.setItemDelegate(RowDelegate(page))
            own_row_painting(page)
            page.hovered.connect(lambda item, group=name: self.link_row(group, item))
            page.left.connect(self.raw.clear_highlight)
            page.setHeaderHidden(True)
            page.setRootIsDecorated(False)
            page.setWordWrap(True)
            page.setTextElideMode(Qt.TextElideMode.ElideMiddle)
            page.setColumnCount(2)
            page.header().setStretchLastSection(True)
            page.setStyleSheet(INSPECTOR_STYLE)
            for key, value in rows:
                row = QTreeWidgetItem([str(key), str(value)])
                row.setToolTip(1, str(value))
                if view.is_settings and name == "Setting values":
                    lines = dnf.setting_list(view.settings, view.settings.get(key))[1]
                    if len(lines) > 1:
                        row.setData(1, Qt.ItemDataRole.UserRole, lines)
                page.addTopLevelItem(row)
            page.resizeColumnToContents(0)
            page.setColumnWidth(0, page.columnWidth(0) + KEY_COLUMN_GAP)
            page.itemDoubleClicked.connect(self.open_value)
            self.inspector.setTabToolTip(self.inspector.addTab(page, name.split(" (")[0]), name)
        entry = view.entries[i] if i >= 0 else None
        if view.is_settings:
            self.raw.set_sources([] if view.settings.problem else [("Settings hive", view.settings, widgets.HIVE_SOURCE)])
        else:
            self.raw.set_sources([] if entry is None else [(label, obj, kind) for label, obj, kind in (("Tab file", entry.tab, "tab"), ("State record", entry.delta, "delta"), ("Window file", view.window, "window")) if obj is not None])
        for k in range(self.inspector.count()):
            if self.inspector.tabText(k) == keep:
                self.inspector.setCurrentIndex(k)
        self.inspector.blockSignals(False)
        self.show_tab_source(self.inspector.currentIndex())

    def show_tab_source(self, k):
        if 0 <= k < len(self.groups):
            self.raw.show_source(group_source(self.groups[k][0]))

    def link_row(self, group, item):
        kind, names = row_fields(group, item.text(0), item.text(1)) if item is not None else ("", ())
        if names:
            self.raw.show_fields(kind, names)
        else:
            self.raw.clear_highlight()

    def show_badges(self, i):
        while self.badge_row.count():
            widget = self.badge_row.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        view = self.views[self.current]
        for text, kind in dnf.settings_badges(view.settings) if view.is_settings else dnf.entry_badges(view.entries[i], view, i) if i >= 0 else []:
            self.badge_row.addWidget(pill(text, kind))
        self.badge_row.addStretch(1)

    def open_value(self, item):
        lines = item.data(1, Qt.ItemDataRole.UserRole)
        if lines:
            ListDialog(self, f"{item.text(0)} ({len(lines)} entries)", lines).exec()
        else:
            self.copy_value(item)

    def copy_value(self, item):
        QApplication.clipboard().setText(item.text(1))
        self.statusBar().showMessage(f"Copied: {item.text(1)}", 3000)

    def copy_all(self):
        QApplication.clipboard().setText("\n\n".join(f"[{name}]\n" + "\n".join(f"{k}: {v}" for k, v in rows) for name, rows in self.groups))
        self.statusBar().showMessage("Copied all fields for this tab", 3000)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.open_path(os.path.normpath(urls[0].toLocalFile()))


def apply_scheme(app, scheme):
    app.setPalette(build_palette(scheme))
    widgets.set_colors(colors_for(scheme, app.palette()))
    app.setStyleSheet(build_style(widgets.colors))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_scheme(app, saved_scheme())
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "assets", "denoted.png")))
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        window.open_path(os.path.abspath(sys.argv[1]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
