import struct
from dataclasses import dataclass

HEADER_SIZE = 0x1000
SIGNATURE = b"regf"
CHECKSUM_OFFSET = 508
CHECKSUM_FIELDS = CHECKSUM_OFFSET // 4
MAX_KEYS = 20000
MAX_DEPTH = 64
NK_NAME = 76
COMPRESSED_NAME = 0x20
VK_NAME = 20
ASCII_VALUE_NAME = 1
INLINE_DATA = 0x80000000
NO_OFFSET = 0xFFFFFFFF
DEFAULT_VALUE = "(default)"


@dataclass
class Key:
    path: tuple
    start: int
    end: int
    stamp: int
    name_start: int
    name_end: int


@dataclass
class Value:
    path: tuple
    name: str
    type: int
    data: bytes
    start: int
    end: int
    data_start: int | None


class Hive:
    def __init__(self, raw):
        if len(raw) < HEADER_SIZE + 32 or raw[:4] != SIGNATURE:
            raise ValueError("not a registry hive (no regf signature)")
        self.raw = raw
        self.seq1, self.seq2, self.stamp, self.major, self.minor = struct.unpack_from("<IIQII", raw, 4)
        self.root, self.bins_size = struct.unpack_from("<II", raw, 36)
        self.name = raw[48:112].decode("utf-16-le", errors="replace").split("\x00")[0]
        self.checksum_stored = struct.unpack_from("<I", raw, CHECKSUM_OFFSET)[0]
        self.checksum_calc = self.header_checksum()

    @property
    def clean(self):
        return self.seq1 == self.seq2

    @property
    def checksum_ok(self):
        return self.checksum_stored == self.checksum_calc

    def header_checksum(self):
        x = 0
        for v in struct.unpack_from(f"<{CHECKSUM_FIELDS}I", self.raw, 0):
            x ^= v
        return 1 if x == 0 else 0xFFFFFFFE if x == 0xFFFFFFFF else x

    def cell(self, off):
        start = HEADER_SIZE + off
        if off == NO_OFFSET or start + 4 > len(self.raw):
            raise ValueError(f"cell offset {off:#x} is outside the hive")
        size = abs(struct.unpack_from("<i", self.raw, start)[0])
        if size < 8 or start + size > len(self.raw):
            raise ValueError(f"cell at {off:#x} has an invalid size")
        return start, start + size

    def offsets(self, off):
        start, _ = self.cell(off)
        sig, count = struct.unpack_from("<2sH", self.raw, start + 4)
        if sig in (b"lf", b"lh"):
            return [struct.unpack_from("<I", self.raw, start + 8 + 8 * i)[0] for i in range(count)]
        if sig == b"li":
            return [struct.unpack_from("<I", self.raw, start + 8 + 4 * i)[0] for i in range(count)]
        if sig == b"ri":
            return [o for i in range(count) for o in self.offsets(struct.unpack_from("<I", self.raw, start + 8 + 4 * i)[0])]
        raise ValueError(f"unknown subkey list type {sig!r}")

    def key(self, off, parent):
        start, end = self.cell(off)
        c = start + 4
        if self.raw[c:c + 2] != b"nk":
            raise ValueError(f"cell at {off:#x} is not a key")
        flags, stamp = struct.unpack_from("<HQ", self.raw, c + 2)
        name_len = struct.unpack_from("<H", self.raw, c + 72)[0]
        name_start = c + NK_NAME
        name = self.raw[name_start:name_start + name_len].decode("latin-1" if flags & COMPRESSED_NAME else "utf-16-le", errors="replace")
        return Key(parent + (name,), start, end, stamp, name_start, name_start + name_len), c

    def values(self, key, c):
        count, list_off = struct.unpack_from("<II", self.raw, c + 36)
        if not count or list_off == NO_OFFSET:
            return []
        list_start, _ = self.cell(list_off)
        out = []
        for i in range(count):
            start, end = self.cell(struct.unpack_from("<I", self.raw, list_start + 4 + 4 * i)[0])
            v = start + 4
            name_len, data_len, data_off, vtype, flags = struct.unpack_from("<HIIIH", self.raw, v + 2)
            name = self.raw[v + VK_NAME:v + VK_NAME + name_len].decode("latin-1" if flags & ASCII_VALUE_NAME else "utf-16-le", errors="replace") or DEFAULT_VALUE
            if data_len & INLINE_DATA:
                data, data_start = struct.pack("<I", data_off)[:data_len & 0x7FFFFFFF], None
            else:
                data_start, data_end = self.cell(data_off)
                data_start += 4
                if data_start + data_len > data_end:
                    raise ValueError(f"value {name!r} data does not fit its cell")
                data = self.raw[data_start:data_start + data_len]
            out.append(Value(key.path, name, vtype, data, start, end, data_start))
        return out

    def walk(self):
        seen = set()
        stack = [(self.root, (), 0)]
        while stack:
            off, parent, depth = stack.pop()
            if off in seen or depth > MAX_DEPTH or len(seen) >= MAX_KEYS:
                continue
            seen.add(off)
            key, c = self.key(off, parent)
            yield key, self.values(key, c)
            count, list_off = struct.unpack_from("<I", self.raw, c + 20)[0], struct.unpack_from("<I", self.raw, c + 28)[0]
            if count and list_off != NO_OFFSET:
                stack += [(o, key.path, depth + 1) for o in reversed(self.offsets(list_off))]
