import datetime
import hashlib
import json
import ntpath
import os
import platform
import re
import struct
import sys
import uuid
import zlib
from dataclasses import dataclass, field

from . import hive

EPOCH_DIFF_100NS = 116444736000000000
ENCODINGS = {1: ("ANSI", "cp1252"), 2: ("UTF-16 LE", "utf-16-le"), 3: ("UTF-16 BE", "utf-16-be"), 4: ("UTF-8 with BOM", "utf-8-sig"), 5: ("UTF-8", "utf-8")}
EOLS = {1: ("Windows (CRLF)", "\r\n"), 2: ("Macintosh (CR)", "\r"), 3: ("Unix (LF)", "\n")}
FORMATTING_TYPES = {1: "Unformatted", 2: "Markdown", 3: "MarkdownSyntax"}
GUID_FILE_RE = re.compile(r"^([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})(?:\.([01]))?(?: \(\d+\))?\.bin$", re.I)
STATE_DIR_RE = re.compile(r"(tab|window)[-_ ]?state", re.I)
IS_WINDOWS = sys.platform == "win32"
LIVE_UNAVAILABLE = f"Reading a live system is only supported on Windows (this computer runs {platform.system() or sys.platform}). Open copied state files or folders instead."
LIVE_STATE_PARTS = ("AppData", "Local", "Packages", "Microsoft.WindowsNotepad_8wekyb3d8bbwe", "LocalState")
PROFILE_LIST_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
USER_SID_PREFIXES = ("S-1-5-21-", "S-1-12-1-")
SKIPPED_PROFILES = {"public", "default", "default user", "all users"}
CONFIG_GROUP = "Config block"
SKIPPED_KIND = "skipped"
SETTINGS_KIND = "app-settings"
SCAN_KIND_LABELS = {"tab-main": "Tab file", "tab-delta": "State record", "window-state": "Window file", SETTINGS_KIND: "App settings", SKIPPED_KIND: "Skipped"}
SETTINGS_DIR = "Settings"
SETTINGS_FILE = "settings.dat"
SETTINGS_LABEL = "App settings"
SETTINGS_UNREAD_LABEL = "App settings (not read)"
SETTINGS_LOCKED_NOTE = "Locked by another process, or access denied"
SETTINGS_LOCKED_HINTS = (("Likely cause", "Notepad has it open (live systems)"), ("To read it", "Close Notepad and reload, or open a copy of the Settings folder"))
SETTINGS_PARSE_NOTE = "Not a readable registry hive: "
SETTINGS_SEARCH_LEVELS = 3
SETTINGS_KEY = "LocalState"
SETTINGS_LOG_SUFFIXES = (".LOG1", ".LOG2")
STAMP_BYTES = 8
UWP_TYPES = {0x5F5E104: "Int32", 0x5F5E105: "UInt32", 0x5F5E10B: "Boolean", 0x5F5E10C: "String"}
REG_TYPES = {1: "REG_SZ", 2: "REG_EXPAND_SZ", 3: "REG_BINARY", 4: "REG_DWORD", 7: "REG_MULTI_SZ", 11: "REG_QWORD"}
RECENT_FILES_NAME = "RecentFiles"
SPELL_CHECK_NAME = "SpellCheckState"
SPELL_OVERRIDES_KEY = "FileExtensionsOverrides"
LIST_NOTE = "{} {} - double-click to list them"
POSITION_PREFIX = "WindowPosition"
POSITION_NAMES = ("Left", "Top", "Right", "Bottom", "Width", "Height")
HIVE_GROUPS = ("Hive file", "Setting values", "Recent files", "Cross-check")
TITLE_MAX_CHARS = 40
MAX_EDITS_LISTED = 200
NO_TAB_TEXT = "(tab file not available)"
NO_TEXT_TEXT = "(state record only - it contains no text)"
FROM_PATH_NOTE = "No text is stored: saved to a path with no unsaved changes, so Notepad reloads it from the path"


@dataclass
class Field:
    name: str
    start: int
    end: int
    kind: str
    value: str = ""
    group: str = ""


@dataclass
class Config:
    word_wrap: bool
    rtl: bool
    show_unicode: bool
    version: int
    unknown0: bytes
    formatting_type: int | None
    unknown0_offset: int = 0


@dataclass
class Edit:
    offset: int
    cursor: int
    deletion: int
    addition: int
    chars: bytes
    crc_stored: int
    crc_calc: int

    @property
    def crc_ok(self):
        return self.crc_stored == self.crc_calc


@dataclass
class TabFile:
    path: str
    guid: str
    size: int
    header_byte: int
    has_path: bool
    file_path: str = ""
    file_size: int | None = None
    encoding: int | None = None
    eol: int | None = None
    timestamp: int | None = None
    stored_hash: bytes | None = None
    hash_trailer: int | None = None
    flag: int = 0
    sel: tuple = (0, 0)
    config: Config | None = None
    base_content: bytes = b""
    unsaved: int = 0
    crc_stored: int = 0
    crc_calc: int = 0
    crc_ok: bool = False
    edits: list = field(default_factory=list)
    content: bytes = b""
    trailing: bytes = b""
    mtime: int = 0
    raw: bytes = b""
    fields: list = field(default_factory=list)

    def text(self):
        return self.content.decode("utf-16-le", errors="replace")


@dataclass
class Delta:
    path: str
    guid: str
    size: int
    seq: int
    crc_stored: int
    crc_calc: int
    base_size: int
    sel: tuple
    config: Config
    mtime: int = 0
    raw: bytes = b""
    fields: list = field(default_factory=list)

    @property
    def crc_ok(self):
        return self.crc_stored == self.crc_calc


@dataclass
class Window:
    path: str
    guid: str
    size: int
    seq: int
    crc_stored: int
    crc_calc: int
    tabs: list
    selected: int
    geometry: tuple
    trailing: bytes
    mtime: int = 0
    raw: bytes = b""
    fields: list = field(default_factory=list)

    @property
    def crc_ok(self):
        return self.crc_stored == self.crc_calc


@dataclass
class Entry:
    guid: str
    tab: TabFile | None = None
    delta: Delta | None = None


@dataclass
class SettingValue:
    key: tuple
    name: str
    type_name: str
    value: object
    stamp: int | None

    @property
    def text(self):
        return str(self.value)


@dataclass
class AppSettings:
    path: str
    hive_name: str
    seq1: int
    seq2: int
    stamp: int
    version: str
    checksum_ok: bool
    keys: int
    values: list
    logs: list
    mtime: int = 0
    raw: bytes = b""
    fields: list = field(default_factory=list)
    recent_files: list = field(default_factory=list)
    problem: str = ""

    @property
    def clean(self):
        return self.seq1 == self.seq2

    def get(self, name):
        return next((v for v in self.values if v.name == name), None)


@dataclass
class WindowView:
    label: str
    window: Window | None
    entries: list
    settings: AppSettings | None = None

    @property
    def is_settings(self):
        return self.window is None and not self.entries and self.settings is not None


@dataclass
class ScannedFile:
    folder: str
    name: str
    kind: str


@dataclass
class Directory:
    root: str
    folders: list
    views: list
    skipped: list
    files: list = field(default_factory=list)


@dataclass
class LiveUser:
    name: str
    profile: str
    state: str
    files: int
    problem: str


def uleb(b, o):
    v = s = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return v, o


def crc32(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def guid_of(path):
    name = os.path.basename(path)
    m = GUID_FILE_RE.match(name)
    return m.group(1).lower() if m else os.path.splitext(name)[0]


def filetime_text(ts):
    try:
        utc = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=ts // 10)
    except OverflowError:
        return f"invalid ({ts})"
    text = f"{utc:%Y-%m-%d %H:%M:%S}.{ts % 10_000_000:07d} UTC"
    try:
        return f"{text}  ({utc.astimezone():%H:%M:%S %Z} local)"
    except (OverflowError, OSError, ValueError):
        return text


def filetime_short(ts):
    try:
        return f"{datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ts // 10):%Y-%m-%d %H:%M:%S} UTC"
    except OverflowError:
        return f"invalid ({ts})"


def classify(d):
    if not d:
        return "empty"
    if d[:2] != b"NP" or len(d) < 8:
        return "unknown"
    if d[3] in (0, 1):
        return "tab-main"
    try:
        plen, o = uleb(d, 3)
        if o + plen + 4 > len(d) or crc32(d[2:o + plen]) != int.from_bytes(d[o + plen:o + plen + 4], "big"):
            return "unknown"
        count, q = uleb(d, o + 1)
    except IndexError:
        return "unknown"
    return "window-state" if d[o] == 0 and o + plen == q + 16 * count + 26 else "tab-delta"


def mark(fields, name, start, end, kind, value="", group=""):
    fields.append(Field(name, start, end, kind, value, group))


def parse_config(b, o, base=0, fields=None):
    fields = [] if fields is None else fields
    wrap, rtl, uni = b[o:o + 3]
    for k, (name, value) in enumerate((("Word wrap", wrap), ("Right-to-left", rtl), ("Show Unicode control characters", uni))):
        mark(fields, name, base + o + k, base + o + k + 1, "config", str(value), CONFIG_GROUP)
    version, after = uleb(b, o + 3)
    mark(fields, "Config version", base + o + 3, base + after, "config", str(version), CONFIG_GROUP)
    o = after
    unknown0 = b[o:o + 2] if version >= 2 else b""
    offset = base + o
    if unknown0:
        mark(fields, f"Unidentified bytes @{offset}", offset, offset + len(unknown0), "unidentified", unknown0.hex(" "), CONFIG_GROUP)
    o += len(unknown0)
    fmt = None
    if version > 2:
        fmt = b[o]
        mark(fields, "Formatting type", base + o, base + o + 1, "config", FORMATTING_TYPES.get(fmt, "unknown"), CONFIG_GROUP)
        o += 1
    return Config(bool(wrap), bool(rtl), bool(uni), version, unknown0, fmt, offset), o


def parse_edit(d, o):
    start = o
    cur, o = uleb(d, o)
    dele, o = uleb(d, o)
    add, o = uleb(d, o)
    if o + 2 * add + 4 > len(d):
        raise ValueError("truncated edit record")
    chars = d[o:o + 2 * add]
    o += 2 * add
    return Edit(start, cur, dele, add, chars, int.from_bytes(d[o:o + 4], "big"), crc32(d[start:o])), o + 4


def parse_tab_main(d, path):
    t = TabFile(path, guid_of(path), len(d), d[2], bool(d[3]))
    f = t.fields
    mark(f, "Signature", 0, 2, "signature", "NP")
    mark(f, "Header byte", 2, 3, "header", f"{d[2]:#04x}")
    mark(f, "Saved-to-path flag", 3, 4, "header", str(d[3]))
    o = 4
    if t.has_path:
        n, after = uleb(d, o)
        mark(f, "Path length (characters)", o, after, "path", str(n))
        o = after
        t.file_path = d[o:o + 2 * n].decode("utf-16-le", errors="replace")
        mark(f, "Path (UTF-16 LE)", o, o + 2 * n, "path", t.file_path)
        o += 2 * n
        t.file_size, after = uleb(d, o)
        mark(f, "Recorded file size", o, after, "size", str(t.file_size))
        o = after
        t.encoding, t.eol = d[o], d[o + 1]
        mark(f, "Encoding", o, o + 1, "format", ENCODINGS.get(t.encoding, ("unknown",))[0])
        mark(f, "Line endings", o + 1, o + 2, "format", EOLS.get(t.eol, ("unknown",))[0])
        o += 2
        t.timestamp, after = uleb(d, o)
        mark(f, "File last-write time (ULEB128 FILETIME)", o, after, "timestamp", filetime_text(t.timestamp))
        o = after
        t.stored_hash = d[o:o + 32]
        t.hash_trailer = d[o + 32]
        mark(f, "SHA-256 of the file", o, o + 32, "hash", t.stored_hash.hex())
        mark(f, "Byte after hash", o + 32, o + 33, "unidentified", f"{t.hash_trailer:#04x}")
        o += 33
    t.flag = d[o]
    mark(f, "Flag before selection", o, o + 1, "unidentified", f"{t.flag:#04x}")
    s0, after = uleb(d, o + 1)
    mark(f, "Selection start", o + 1, after, "selection", str(s0))
    s1, o = uleb(d, after)
    mark(f, "Selection end", after, o, "selection", str(s1))
    t.sel = (s0, s1)
    t.config, o = parse_config(d, o, 0, f)
    n, after = uleb(d, o)
    mark(f, "Content length (characters)", o, after, "content", str(n))
    o = after
    t.base_content = d[o:o + 2 * n]
    mark(f, "Text content (UTF-16 LE)", o, o + 2 * n, "content", f"{n} characters")
    o += 2 * n
    t.unsaved = d[o]
    mark(f, "Unsaved flag", o, o + 1, "header", str(t.unsaved))
    o += 1
    if o + 4 > len(d):
        raise ValueError("truncated file")
    t.crc_stored = int.from_bytes(d[o:o + 4], "big")
    t.crc_calc = crc32(d[3:o])
    t.crc_ok = t.crc_calc == t.crc_stored
    mark(f, "CRC32 (big-endian)", o, o + 4, "crc", f"{t.crc_stored:08x} " + ("valid" if t.crc_ok else f"invalid (computed {t.crc_calc:08x})"))
    o += 4
    t.content = t.base_content
    while o < len(d):
        try:
            e, end = parse_edit(d, o)
        except (IndexError, ValueError):
            t.trailing = d[o:]
            mark(f, "Unparsed trailing bytes", o, len(d), "other", f"{len(t.trailing)} bytes")
            break
        k = len(t.edits) + 1
        mark(f, f"Edit #{k} position, delete, add", o, end - 4 - len(e.chars), "edit", f"position {e.cursor}, delete {e.deletion}, add {e.addition}")
        mark(f, f"Edit #{k} added text", end - 4 - len(e.chars), end - 4, "edit", e.chars.decode("utf-16-le", errors="replace"))
        mark(f, f"Edit #{k} CRC32", end - 4, end, "crc", f"{e.crc_stored:08x} " + ("valid" if e.crc_ok else f"invalid (computed {e.crc_calc:08x})"))
        o = end
        t.edits.append(e)
        t.content = t.content[:2 * e.cursor] + e.chars + t.content[2 * (e.cursor + e.deletion):]
    return t


def parse_delta(d, path):
    plen, o = uleb(d, 3)
    payload = d[o:o + plen]
    if payload[0] != 0:
        raise ValueError(f"unrecognized record type {payload[0]:#04x}")
    f = record_header(d, o, plen)
    base, q = uleb(payload, 1)
    mark(f, "Base file size", o + 1, o + q, "size", str(base))
    s0, after = uleb(payload, q)
    mark(f, "Selection start", o + q, o + after, "selection", str(s0))
    s1, q = uleb(payload, after)
    mark(f, "Selection end", o + after, o + q, "selection", str(s1))
    cfg, q = parse_config(payload, q, o, f)
    crc_stored = int.from_bytes(d[o + plen:o + plen + 4], "big")
    mark(f, "CRC32 (big-endian)", o + plen, o + plen + 4, "crc", f"{crc_stored:08x}")
    return Delta(path, guid_of(path), len(d), d[2], crc_stored, crc32(d[2:o + plen]), base, (s0, s1), cfg, fields=f)


def record_header(d, o, plen):
    f = []
    mark(f, "Signature", 0, 2, "signature", "NP")
    mark(f, "Sequence number", 2, 3, "header", str(d[2]))
    mark(f, "Payload length (ULEB128)", 3, o, "size", str(plen))
    mark(f, "Record type", o, o + 1, "header", f"{d[o]:#04x}")
    return f


def parse_window(d, path):
    plen, o = uleb(d, 3)
    end = o + plen
    f = record_header(d, o, plen)
    count, q = uleb(d, o + 1)
    mark(f, "Tab count", o + 1, q, "window", str(count))
    tabs = []
    for k in range(count):
        tabs.append(str(uuid.UUID(bytes_le=d[q:q + 16])))
        mark(f, f"Tab {k + 1} GUID (mixed-endian)", q, q + 16, "window", tabs[-1])
        q += 16
    selected, after = uleb(d, q)
    mark(f, "Selected tab index", q, after, "window", str(selected))
    q = after
    for k, name in enumerate(("Left", "Top", "Right", "Bottom", "Width", "Height")):
        mark(f, f"Window {name.lower()} (uint32 LE)", q + 4 * k, q + 4 * k + 4, "geometry", str(struct.unpack_from("<I", d, q + 4 * k)[0]))
    if end > q + 24:
        mark(f, "Trailing bytes", q + 24, end, "unidentified", d[q + 24:end].hex(" "))
    crc_stored = int.from_bytes(d[end:end + 4], "big")
    mark(f, "CRC32 (big-endian)", end, end + 4, "crc", f"{crc_stored:08x}")
    return Window(path, guid_of(path), len(d), d[2], crc_stored, crc32(d[2:end]), tabs, selected, struct.unpack_from("<6I", d, q), d[q + 24:end], fields=f)


def parse_file(path):
    d = open(path, "rb").read()
    kind = classify(d)
    parsers = {"tab-main": parse_tab_main, "tab-delta": parse_delta, "window-state": parse_window}
    if kind not in parsers:
        raise ValueError("empty file" if kind == "empty" else "not a recognised Notepad state file")
    try:
        obj = parsers[kind](d, path)
    except (IndexError, struct.error) as e:
        raise ValueError(f"truncated or malformed {kind} file ({e})") from e
    obj.mtime = os.stat(path).st_mtime_ns
    obj.raw = d
    return kind, obj


def decode_setting(vtype, data):
    name = UWP_TYPES.get(vtype)
    try:
        if name is not None and len(data) >= STAMP_BYTES:
            payload, stamp = data[:-STAMP_BYTES], struct.unpack("<Q", data[-STAMP_BYTES:])[0]
            if name == "String":
                return name, payload.decode("utf-16-le", errors="replace").rstrip("\x00"), stamp, len(payload)
            if name == "Boolean" and len(payload) == 1:
                return name, bool(payload[0]), stamp, 1
            if name in ("Int32", "UInt32") and len(payload) == 4:
                return name, struct.unpack("<i" if name == "Int32" else "<I", payload)[0], stamp, 4
            return f"{name} (unexpected size)", payload.hex(" "), stamp, len(payload)
        if vtype in (1, 2):
            return REG_TYPES[vtype], data.decode("utf-16-le", errors="replace").rstrip("\x00"), None, None
        if vtype == 4 and len(data) == 4:
            return REG_TYPES[vtype], struct.unpack("<I", data)[0], None, None
        if vtype == 11 and len(data) == 8:
            return REG_TYPES[vtype], struct.unpack("<Q", data)[0], None, None
        if vtype == 7:
            return REG_TYPES[vtype], "; ".join(s for s in data.decode("utf-16-le", errors="replace").split("\x00") if s), None, None
    except (struct.error, IndexError):
        pass
    return REG_TYPES.get(vtype, f"unrecognized ({vtype:#x})"), data.hex(" "), None, None


def settings_label(key, name):
    rel = key[1:]
    return name if rel == (SETTINGS_KEY,) else "\\".join(rel + (name,))


def settings_fields(h):
    f = []
    mark(f, "Signature", 0, 4, "signature", "regf")
    mark(f, "Sequence number 1", 4, 8, "header", str(h.seq1))
    mark(f, "Sequence number 2", 8, 12, "header", str(h.seq2))
    mark(f, "Last written (hive header)", 12, 20, "timestamp", filetime_text(h.stamp))
    mark(f, "Hive version", 20, 28, "header", f"{h.major}.{h.minor}")
    mark(f, "Root cell offset", 36, 40, "size", f"{h.root:#x}")
    mark(f, "Hive bins size", 40, 44, "size", str(h.bins_size))
    mark(f, "Hive name (UTF-16 LE)", 48, 112, "path", h.name)
    mark(f, "Header checksum", hive.CHECKSUM_OFFSET, hive.CHECKSUM_OFFSET + 4, "crc", f"{h.checksum_stored:08x} " + ("valid" if h.checksum_ok else f"invalid (computed {h.checksum_calc:08x})"))
    return f


def parse_settings(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        h = hive.Hive(raw)
        f, values, keys = settings_fields(h), [], 0
        for key, key_values in h.walk():
            keys += 1
            where = "\\".join(key.path[1:]) or "(root)"
            mark(f, f"Key {where}", key.start, key.start + 8, "hive-key", "record header")
            mark(f, f"Key {where} - last write", key.start + 8, key.start + 16, "timestamp", filetime_text(key.stamp))
            mark(f, f"Key {where} - links and name", key.start + 16, key.end, "hive-key", key.path[-1])
            for v in key_values:
                type_name, value, stamp, size = decode_setting(v.type, v.data)
                label = settings_label(key.path, v.name)
                values.append(SettingValue(key.path, v.name, type_name, value, stamp))
                mark(f, f"Value {label} (record)", v.start, v.end, "hive-value", type_name)
                if v.data_start is not None:
                    end = v.data_start + (len(v.data) if size is None else size)
                    mark(f, f"Value {label} (data)", v.data_start, end, "hive-data", str(value))
                    if stamp is not None:
                        mark(f, f"Value {label} (set time)", end, end + STAMP_BYTES, "timestamp", filetime_text(stamp))
    except (struct.error, IndexError) as e:
        raise ValueError(f"malformed registry hive ({e})") from e
    f.sort(key=lambda x: x.start)
    logs = [(os.path.basename(path) + s, os.path.getsize(path + s)) for s in SETTINGS_LOG_SUFFIXES if os.path.isfile(path + s)]
    recent = next((v for v in values if v.name == RECENT_FILES_NAME and v.type_name == "String"), None)
    files = []
    if recent is not None:
        try:
            parsed = json.loads(recent.value)
            files = [str(p) for p in parsed] if isinstance(parsed, list) else []
        except ValueError:
            pass
    return AppSettings(path, h.name, h.seq1, h.seq2, h.stamp, f"{h.major}.{h.minor}", h.checksum_ok, keys, values, logs, os.stat(path).st_mtime_ns, raw, f, files)


def find_settings(folders):
    found = {}
    for folder in folders:
        here = os.path.abspath(folder)
        for _ in range(SETTINGS_SEARCH_LEVELS):
            options = [os.path.join(here, SETTINGS_DIR, SETTINGS_FILE)] + ([os.path.join(here, SETTINGS_FILE)] if os.path.basename(here).lower() == SETTINGS_DIR.lower() else [])
            path = next((p for p in options if os.path.isfile(p)), None)
            if path is not None:
                found.setdefault(os.path.normcase(path), path)
                break
            here = os.path.dirname(here)
    return list(found.values())


def load_settings(folders, skipped, files):
    loaded = []
    for path in find_settings(folders):
        folder, name = os.path.split(path)
        try:
            loaded.append(parse_settings(path))
        except (OSError, ValueError) as e:
            skipped.append(f"{path}: {e}")
            files.append(ScannedFile(folder, name, SKIPPED_KIND))
            loaded.append(AppSettings(path, "", 0, 0, 0, "", True, 0, [], [], problem=SETTINGS_LOCKED_NOTE if isinstance(e, PermissionError) else SETTINGS_PARSE_NOTE + str(e)))
            continue
        files.append(ScannedFile(folder, name, SETTINGS_KIND))
    return loaded


def extra_folders(folders, files):
    return folders + [d for d in dict.fromkeys(f.folder for f in files) if d not in folders]


def state_dirs(root):
    found = [root] + [p for p in (os.path.join(root, n) for n in sorted(os.listdir(root))) if os.path.isdir(p) and STATE_DIR_RE.search(os.path.basename(p))]
    if STATE_DIR_RE.search(os.path.basename(root)):
        parent = os.path.dirname(root)
        found += [p for p in (os.path.join(parent, n) for n in sorted(os.listdir(parent))) if p != root and os.path.isdir(p) and STATE_DIR_RE.search(os.path.basename(p))]
    return found


def state_groups(root):
    groups = {}
    for folder, _, names in os.walk(root):
        if any(n.lower().endswith(".bin") for n in names):
            key = os.path.dirname(folder) if folder != root and STATE_DIR_RE.search(os.path.basename(folder)) else folder
            groups.setdefault(key, []).append(folder)
    return groups


def load_folders(folders):
    tabs, deltas, windows, skipped, files = {}, {}, {}, [], []
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not (os.path.isfile(path) and name.lower().endswith(".bin")):
                continue
            try:
                if os.path.getsize(path):
                    with open(path, "rb") as f:
                        if f.read(2) != b"NP":
                            skipped.append(f"{os.path.abspath(path)}: does not start with the NP signature")
                            files.append(ScannedFile(folder, name, SKIPPED_KIND))
                            continue
                kind, obj = parse_file(path)
            except (ValueError, OSError) as e:
                skipped.append(f"{os.path.abspath(path)}: {e}")
                files.append(ScannedFile(folder, name, SKIPPED_KIND))
                continue
            files.append(ScannedFile(folder, name, kind))
            if kind == "tab-main" and (obj.guid not in tabs or obj.mtime >= tabs[obj.guid].mtime):
                tabs[obj.guid] = obj
            elif kind == "tab-delta" and (obj.guid not in deltas or (obj.seq, obj.mtime) >= (deltas[obj.guid].seq, deltas[obj.guid].mtime)):
                deltas[obj.guid] = obj
            elif kind == "window-state" and (obj.guid not in windows or (obj.seq, obj.mtime) >= (windows[obj.guid].seq, windows[obj.guid].mtime)):
                windows[obj.guid] = obj
    views = []
    placed = set()
    for wguid, w in sorted(windows.items()):
        views.append(WindowView(f"Window {wguid[:8]} (seq {w.seq})", w, [Entry(g, tabs.get(g), deltas.get(g)) for g in w.tabs]))
        placed.update(w.tabs)
    rest = sorted((g for g in tabs if g not in placed), key=lambda g: tabs[g].mtime)
    if rest:
        views.append(WindowView("Tab files not in any window" if windows else "No WindowState file found (tab order unknown)", None, [Entry(g, tabs[g], deltas.get(g)) for g in rest]))
    settings = load_settings(folders, skipped, files)
    for v in views:
        v.settings = settings[0] if settings else None
    return views + [WindowView(SETTINGS_UNREAD_LABEL if s.problem else SETTINGS_LABEL, None, [], s) for s in settings], skipped, files


def file_view(path):
    with open(path, "rb") as fh:
        if fh.read(len(hive.SIGNATURE)) == hive.SIGNATURE:
            return SETTINGS_KIND, WindowView(SETTINGS_LABEL, None, [], parse_settings(path))
    kind, obj = parse_file(path)
    name = os.path.basename(path)
    if kind == "tab-main":
        return kind, WindowView(name, None, [Entry(obj.guid, tab=obj)])
    if kind == "tab-delta":
        return kind, WindowView(name, None, [Entry(obj.guid, delta=obj)])
    return kind, WindowView(name, obj, [Entry(g) for g in obj.tabs])


def load_paths(paths, recursive=False):
    views, skipped, folders, files = [], [], [], []
    for path in paths:
        if os.path.isdir(path):
            found = load_directory(path, recursive)
            new, skipped, folders, files = found.views, skipped + found.skipped, folders + found.folders, files + found.files
        else:
            try:
                kind, view = file_view(path)
            except ValueError as e:
                skipped.append(f"{os.path.abspath(path)}: {e}")
                files.append(ScannedFile(os.path.dirname(os.path.abspath(path)), os.path.basename(path), SKIPPED_KIND))
                continue
            new = [view]
            folders.append(os.path.dirname(os.path.abspath(path)))
            files.append(ScannedFile(folders[-1], os.path.basename(path), kind))
        prefix = f"{os.path.basename(os.path.abspath(path))}: " if len(paths) > 1 and os.path.isdir(path) else ""
        views += [WindowView(prefix + v.label, v.window, v.entries, v.settings) for v in new]
    return Directory("; ".join(os.path.abspath(p) for p in paths), list(dict.fromkeys(folders)), views, skipped, files)


def load_directory(root, recursive=False):
    root = os.path.abspath(root)
    if not recursive:
        folders = state_dirs(root)
        views, skipped, files = load_folders(folders)
        return Directory(root, extra_folders(folders, files), views, skipped, files)
    views, skipped, folders, files = [], [], [], []
    for key, group in sorted(state_groups(root).items()):
        group_views, group_skipped, group_files = load_folders(group)
        prefix = os.path.relpath(key, root)
        views += [WindowView(v.label if prefix == "." else f"{prefix}: {v.label}", v.window, v.entries, v.settings) for v in group_views]
        skipped += group_skipped
        files += group_files
        folders += extra_folders(group, group_files)
    return Directory(root, folders, views, skipped, files)


def require_windows():
    if not IS_WINDOWS:
        raise OSError(LIVE_UNAVAILABLE)


def profile_paths():
    require_windows()
    paths = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PROFILE_LIST_KEY) as key:
            for sid in (winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])):
                if sid.startswith(USER_SID_PREFIXES):
                    try:
                        with winreg.OpenKey(key, sid) as sub:
                            paths.append(os.path.expandvars(winreg.QueryValueEx(sub, "ProfileImagePath")[0]))
                    except OSError:
                        continue
    except (ImportError, OSError):
        pass
    users_dir = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Users")
    try:
        paths += [os.path.join(users_dir, n) for n in os.listdir(users_dir) if n.lower() not in SKIPPED_PROFILES and os.path.isdir(os.path.join(users_dir, n))]
    except OSError:
        pass
    return list({os.path.normcase(os.path.normpath(p)): os.path.normpath(p) for p in paths}.values())


def probe_live_user(profile):
    name, state = os.path.basename(profile), os.path.join(profile, *LIVE_STATE_PARTS)
    try:
        files = sum(n.lower().endswith(".bin") for folder in state_dirs(state) for n in os.listdir(folder))
    except FileNotFoundError:
        return LiveUser(name, profile, state, 0, "No Notepad data" if os.path.exists(profile) else "Stale profile (folder no longer exists)")
    except PermissionError:
        return LiveUser(name, profile, state, 0, "Access denied (run as administrator)")
    except OSError as e:
        return LiveUser(name, profile, state, 0, str(e))
    return LiveUser(name, profile, state, files, "" if files else "LocalState has no .bin files")


def find_live_users(profiles=None):
    require_windows()
    return sorted((probe_live_user(p) for p in (profile_paths() if profiles is None else profiles)), key=lambda u: u.name.lower())


def load_live(users):
    require_windows()
    views, skipped, folders, files = [], [], [], []
    for user in users:
        try:
            found = load_directory(user.state)
        except OSError as e:
            skipped.append(f"{user.state}: {e}")
            continue
        views += [WindowView(f"{user.name}: {v.label}", v.window, v.entries, v.settings) for v in found.views]
        skipped += found.skipped
        folders += found.folders
        files += found.files
    return Directory(f"Live system {platform.node()} - users: {', '.join(u.name for u in users)}", folders, views, skipped, files)


def effective(entry):
    t, d = entry.tab, entry.delta
    if d is not None and d.crc_ok and (t is None or d.base_size == t.size):
        return d.config, d.sel, f"state record, seq {d.seq}"
    if t is not None and t.edits:
        caret = t.edits[-1].cursor + t.edits[-1].addition
        return t.config, (caret, caret), "tab file; caret from last edit record"
    if t is not None:
        return t.config, t.sel, "tab file"
    return None, (0, 0), "n/a"


def entry_title(entry):
    t = entry.tab
    if t is None:
        return entry.guid[:8] + "…"
    if t.has_path:
        return ntpath.basename(t.file_path) or t.file_path
    line = t.text().replace("\r\n", "\r").split("\r")[0].strip()
    if not line:
        return "Untitled"
    return line if len(line) <= TITLE_MAX_CHARS else line[:TITLE_MAX_CHARS] + "…"


def entry_modified(entry):
    return entry.tab is not None and bool(entry.tab.unsaved or entry.tab.edits)


def reloads_from_path(entry):
    t = entry.tab
    return t is not None and t.has_path and not entry_modified(entry) and not t.content


def entry_badges(entry, view, index):
    t, d, w = entry.tab, entry.delta, view.window
    out = []
    if t is not None:
        out.append(("CRC valid", "ok") if t.crc_ok else ("CRC invalid", "warn"))
        status = hash_status(t)
        if status == "matches stored hash":
            out.append(("Hash matches", "ok"))
        elif status == "does not match stored hash":
            out.append(("Hash mismatch", "warn"))
        elif t.has_path:
            out.append(("Hash not checked", "note"))
        if t.edits:
            valid = sum(e.crc_ok for e in t.edits)
            out.append((f"{len(t.edits)} edit record(s)" if valid == len(t.edits) else f"{valid} of {len(t.edits)} edit records valid", "ok" if valid == len(t.edits) else "warn"))
        if entry_modified(entry):
            out.append(("Unsaved changes", "note"))
        if reloads_from_path(entry):
            out.append(("Loads from path", "note"))
    if d is not None:
        out.append((f"State record seq {d.seq}", "ok" if d.crc_ok else "warn"))
    if w is not None:
        out += ([("Active tab", "note")] if w.selected == index else []) + [(f"Window seq {w.seq}", "ok" if w.crc_ok else "warn")]
    return out


def entry_text(entry):
    if entry.tab is None:
        return NO_TEXT_TEXT if entry.delta is not None else NO_TAB_TEXT
    return entry.tab.text().replace("\r\n", "\n").replace("\r", "\n")


def entry_format(entry):
    t = entry.tab
    if t is None:
        return "n/a", "n/a"
    if not t.has_path:
        return EOLS[1][0], ENCODINGS[5][0]
    return EOLS.get(t.eol, (f"unknown ({t.eol})",))[0], ENCODINGS.get(t.encoding, (f"unknown ({t.encoding})",))[0]


def formatting_name(cfg):
    return "Plain text" if cfg is None or cfg.formatting_type in (None, 1) else "Markdown"


def yes_no(v):
    return "Yes" if v else "No"


def hash_status(t):
    if not t.has_path:
        return "n/a (no path)"
    if t.stored_hash == bytes(32):
        return "stored hash is all zeros"
    if t.encoding not in ENCODINGS or t.eol not in EOLS:
        return "cannot check (unknown encoding or line ending)"
    data = t.text().replace("\r", EOLS[t.eol][1]).encode(ENCODINGS[t.encoding][1], errors="replace")
    return "matches stored hash" if hashlib.sha256(data).digest() == t.stored_hash else "does not match stored hash"


def disk_rows(t):
    if not t.has_path or not os.path.isfile(t.file_path):
        return []
    st = os.stat(t.file_path)
    ft = st.st_mtime_ns // 100 + EPOCH_DIFF_100NS
    sha = hashlib.sha256(open(t.file_path, "rb").read()).hexdigest()
    return [
        ("Last-write time", filetime_text(ft)),
        ("Equals recorded timestamp", yes_no(ft == t.timestamp)),
        ("Size", f"{st.st_size} bytes"),
        ("Equals recorded size", yes_no(st.st_size == t.file_size)),
        ("SHA256", sha),
        ("Equals stored hash", yes_no(t.stored_hash is not None and sha == t.stored_hash.hex())),
    ]


def config_rows(cfg):
    return [
        ("Word wrap", yes_no(cfg.word_wrap)),
        ("Right-to-left reading order", yes_no(cfg.rtl)),
        ("Show Unicode control characters", yes_no(cfg.show_unicode)),
        ("Config version", cfg.version),
        (f"Unidentified bytes @{cfg.unknown0_offset}" if cfg.unknown0 else "Unidentified bytes", cfg.unknown0.hex(" ") or "-"),
        ("Formatting type", "-" if cfg.formatting_type is None else f"{FORMATTING_TYPES.get(cfg.formatting_type, 'unknown')} ({cfg.formatting_type})"),
    ]


def position_check(settings, w):
    saved = [] if settings is None else [settings.get(POSITION_PREFIX + n) for n in POSITION_NAMES]
    if not saved or None in saved:
        return None
    values = tuple(v.value for v in saved)
    if values == tuple(w.geometry):
        return f"Same as the {POSITION_PREFIX}* values in settings.dat" + (f" (set {filetime_short(saved[0].stamp)})" if saved[0].stamp else "")
    return f"Different from the {POSITION_PREFIX}* values in settings.dat (left {values[0]}, top {values[1]}, right {values[2]}, bottom {values[3]}, width {values[4]}, height {values[5]})"


def describe_window(w, index=None, settings=None):
    left, top, right, bottom, width, height = w.geometry
    rows = [
        ("File (full path)", os.path.abspath(w.path)),
        ("Window GUID", w.guid),
        ("Sequence", w.seq),
        ("CRC32 stored", f"{w.crc_stored:08x}"),
        ("CRC32 computed", f"{w.crc_calc:08x}"),
        ("CRC32 valid", yes_no(w.crc_ok)),
        ("Tabs", len(w.tabs)),
        ("Selected tab", w.selected + 1),
        ("Window rectangle (desktop coords)", f"left {left}, top {top}, right {right}, bottom {bottom}"),
        ("Window size (incl. invisible frame)", f"{width} x {height}"),
        ("Trailing byte(s)", w.trailing.hex(" ") or "-"),
    ]
    if index is not None:
        rows.insert(5, ("This tab", f"{index + 1} of {len(w.tabs)}"))
    check = position_check(settings, w)
    if check is not None:
        rows.append(("Position vs settings.dat", check))
    return ("Window", rows)


def describe_entry(entry, view=None, index=0):
    t, dl = entry.tab, entry.delta
    cfg, sel, source = effective(entry)
    groups = []
    if t is not None:
        groups.append(("Tab file", [
            ("File (full path)", os.path.abspath(t.path)),
            ("Tab GUID", entry.guid),
            ("Size", f"{t.size} bytes"),
            ("Modified on disk", filetime_text(t.mtime // 100 + EPOCH_DIFF_100NS)),
            ("Header byte 0x02", f"{t.header_byte:#04x}"),
        ]))
        doc = [("Title", entry_title(entry)), ("Saved to a path", yes_no(t.has_path))]
        if not t.has_path:
            doc += [
                ("Encoding", f"{entry_format(entry)[1]} (not stored; Notepad default)"),
                ("Line endings", f"{entry_format(entry)[0]} (not stored; Notepad default)"),
            ]
        else:
            doc += [
                ("Path", t.file_path),
                ("Recorded file size", f"{t.file_size} bytes"),
                ("Encoding", entry_format(entry)[1]),
                ("Line endings", entry_format(entry)[0]),
                ("File last-write time", filetime_text(t.timestamp)),
                ("File last-write ticks", t.timestamp),
            ]
        doc += [
            ("Characters in snapshot", len(t.base_content) // 2),
            ("Characters after edits", len(t.content) // 2),
            ("Selection", f"{sel[0]} - {sel[1]}"),
            ("Unsaved-data flag", yes_no(t.unsaved)),
            ("Appended edit records", f"{len(t.edits)} ({sum(e.crc_ok for e in t.edits)} with valid CRC)"),
        ]
        if reloads_from_path(entry):
            doc.append(("Text source", FROM_PATH_NOTE))
        if t.trailing:
            doc.append(("Unparsed trailing bytes", t.trailing.hex(" ")))
        groups.append(("Document", doc))
        groups.append((f"Settings (from {source})", config_rows(cfg)))
        integrity = [("CRC32 stored", f"{t.crc_stored:08x}"), ("CRC32 computed", f"{t.crc_calc:08x}"), ("CRC32 valid", yes_no(t.crc_ok))]
        if t.has_path:
            integrity = [("Stored SHA256", t.stored_hash.hex()), ("Hash vs current text", hash_status(t)), ("Byte after hash", f"{t.hash_trailer:#04x}")] + integrity
        groups.append(("Integrity", integrity))
        if disk_rows(t):
            groups.append(("File on disk", disk_rows(t)))
    else:
        groups.append(("Tab", [("Tab GUID", entry.guid), ("Tab file", "not available")]))
        if cfg is not None:
            groups.append((f"Settings (from {source})", config_rows(cfg)))
    if dl is not None:
        groups.append(("State record (.0/.1)", [
            ("File (full path)", os.path.abspath(dl.path)),
            ("Sequence", dl.seq),
            ("CRC32 stored", f"{dl.crc_stored:08x}"),
            ("CRC32 computed", f"{dl.crc_calc:08x}"),
            ("CRC32 valid", yes_no(dl.crc_ok)),
            ("Base size", f"{dl.base_size} bytes"),
            ("Matches tab file size", "n/a" if t is None else yes_no(dl.base_size == t.size)),
            ("Applied to display", yes_no(source.startswith("state record"))),
            ("Selection", f"{dl.sel[0]} - {dl.sel[1]}"),
        ]))
    if t is not None and t.edits:
        rows = [(f"#{i + 1} @{e.offset}", f"position {e.cursor}, delete {e.deletion}, add {e.addition}" + (f" {e.chars.decode('utf-16-le', errors='replace')!r}" if e.addition else "") + f"  crc {e.crc_stored:08x}" + ("" if e.crc_ok else f" (computed {e.crc_calc:08x})")) for i, e in enumerate(t.edits[:MAX_EDITS_LISTED])]
        if len(t.edits) > MAX_EDITS_LISTED:
            rows.append(("...", f"{len(t.edits) - MAX_EDITS_LISTED} more"))
        groups.append(("Edit records", rows))
    if view is not None and view.window is not None:
        groups.append(describe_window(view.window, index, view.settings))
    return groups


def settings_badges(s):
    if s.problem:
        return [("Not read", "warn")]
    out = [("Hive consistent", "ok") if s.clean else ("Hive dirty - logs not replayed", "warn")]
    if not s.checksum_ok:
        out.append(("Header checksum invalid", "warn"))
    return out + [(f"{len(s.values)} setting(s)", "note")]


def setting_list(s, v):
    if v is None:
        return "", [], ""
    if v is s.get(RECENT_FILES_NAME):
        return "", s.recent_files, "files"
    if v is s.get(SPELL_CHECK_NAME) and v.type_name == "String":
        try:
            state = json.loads(v.value)
            return f"Enabled: {state['Enabled']}; ", [f"{ext}: spell check {'on' if on else 'off'}" for ext, on in state[SPELL_OVERRIDES_KEY]], "file extension overrides"
        except (ValueError, KeyError, TypeError):
            pass
    return "", [], ""


def setting_text(s, v, compact):
    prefix, lines, noun = setting_list(s, v)
    if not compact or not lines:
        return v.text
    return prefix + (lines[0] if len(lines) == 1 else LIST_NOTE.format(len(lines), noun))


def describe_settings(s, views=(), compact=False):
    if s.problem:
        return [("Hive file", [("File (full path)", os.path.abspath(s.path)), ("Status", "Not read"), ("Reason", s.problem)] + list(SETTINGS_LOCKED_HINTS if s.problem == SETTINGS_LOCKED_NOTE else []))]
    open_paths = {ntpath.normcase(e.tab.file_path) for v in views for e in v.entries if e.tab is not None and e.tab.has_path}
    logs = "; ".join(f"{name} ({size} bytes)" for name, size in s.logs)
    groups = [("Hive file", [
        ("File (full path)", os.path.abspath(s.path)),
        ("Size", f"{len(s.raw)} bytes"),
        ("Modified on disk", filetime_text(s.mtime // 100 + EPOCH_DIFF_100NS)),
        ("Hive name (stored path)", s.hive_name),
        ("Hive version", s.version),
        ("Sequence numbers", f"{s.seq1} / {s.seq2}"),
        ("Hive state", "Consistent" if s.clean else "Dirty: newer data may be in the transaction logs, which are not replayed"),
        ("Header checksum valid", yes_no(s.checksum_ok)),
        ("Hive header time", filetime_text(s.stamp)),
        ("Keys / values", f"{s.keys} / {len(s.values)}"),
        ("Transaction logs", f"{logs} - not replayed" if logs else "None found next to the hive"),
    ]), ("Setting values", [(settings_label(v.key, v.name), setting_text(s, v, compact) + f"   ({v.type_name}" + (f"; set {filetime_short(v.stamp)}" if v.stamp else "") + ")") for v in s.values] or [("(none)", "The hive holds no values")])]
    if s.recent_files:
        groups.append(("Recent files", [(i + 1, p + ("   (open in a tab)" if ntpath.normcase(p) in open_paths else "")) for i, p in enumerate(s.recent_files)]))
    checks = [(f"Window {v.window.guid[:8]}", position_check(s, v.window)) for v in views if v.window is not None]
    if any(c for _, c in checks):
        groups.append(("Cross-check", [(name, c) for name, c in checks if c]))
    return groups
