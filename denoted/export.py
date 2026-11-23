import base64
import csv
import datetime
import html
import io
import json
import os

from . import fonts
from . import format as dnf

REPORT_TITLE = "Denoted: Notepad state files report"
HTML_THEMES = {"html": "", "html-light": "light", "html-dark": "dark"}
FORMATS = {"html": ("HTML report (follows system theme)", "html"), "html-light": ("HTML report (light)", "html"), "html-dark": ("HTML report (dark)", "html"), "json": ("JSON (full detail)", "json"), "csv": ("CSV (one row per tab)", "csv"), "text": ("Plain text report", "txt")}
TEXT_RULE = "=" * 78
qt_app = None
TITLE_WITHHELD = "(unsaved tab - title withheld)"
TEXT_WITHHELD = "Tab text was not included in this export."
NO_TAB_FILE = "Tab file not available."
CSV_COLUMNS = [
    "window", "window_guid", "window_file_path", "tab_position", "active_tab", "tab_guid", "title", "tab_file_path", "tab_file_size", "tab_file_modified_utc",
    "saved_to_path", "file_path", "recorded_file_size", "file_last_write_utc", "file_last_write_ticks", "line_ending", "encoding", "line_ending_encoding_source",
    "characters", "selection_start", "selection_end", "unsaved_flag", "edit_records", "edit_records_crc_valid", "tab_crc_valid",
    "stored_sha256", "hash_check", "state_record_path", "state_record_seq", "state_record_crc_valid", "state_record_applied",
    "word_wrap", "rtl", "show_unicode", "config_version", "formatting_type", "text",
    "record_type", "scan_folder", "scan_file", "scan_file_kind", "scan_note",
    "setting_file", "setting_name", "setting_type", "setting_value", "setting_set_utc",
]
CSV_TAB, CSV_FOLDER, CSV_FILE, CSV_SETTING = "tab", "scanned folder", "scanned file", "app setting"
HTML_STYLE = """
:root { color-scheme: light dark; --page: #f4f5f7; --card: #ffffff; --soft: #f1f3f5; --line: #e3e6ea; --text: #1c1f23; --muted: #667085;
  --accent: #2459d6; --accent-bg: #e4ecfd; --ok: #1a6b3a; --ok-bg: #e0f3e8; --warn: #8a5a00; --warn-bg: #fbefd2; --pro: #5b3fb0; --pro-bg: #ebe6fa; --note: #4b5563; --note-bg: #eceef1; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { DARK_VARS } }
:root[data-theme="light"] { color-scheme: light; }
:root[data-theme="dark"] { color-scheme: dark; DARK_VARS }
* { box-sizing: border-box; }
body { font: 14px/1.5 UI_STACK; background: var(--page); color: var(--text); margin: 0 auto; max-width: 1180px; padding: 24px 16px 48px; }
header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
h1 { font-size: 22px; font-weight: 600; margin: 0; } h2 { font-size: 17px; font-weight: 600; margin: 0 0 10px; }
.meta { color: var(--muted); font-size: 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 0 0 14px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; color: var(--muted); font-size: 12px; }
.tile b { display: block; font-size: 26px; font-weight: 600; line-height: 1.2; color: var(--text); }
.tile.warn b { color: var(--warn); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin: 0 0 14px; }
.card > h2 { padding-bottom: 8px; border-bottom: 1px solid var(--line); }
details { border: 1px solid var(--line); border-radius: 12px; background: var(--card); padding: 2px 14px; margin: 10px 0; }
details > summary { cursor: pointer; padding: 10px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-weight: 600; list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "\\25B8"; color: var(--muted); font-size: 12px; transition: transform .15s; }
details[open] > summary::before { transform: rotate(90deg); }
details[open] > summary { border-bottom: 1px solid var(--line); margin-bottom: 8px; }
.pos { background: var(--soft); border-radius: 6px; padding: 0 8px; font-size: 12px; color: var(--muted); }
.ttl { margin-right: 4px; word-break: break-word; }
.pill { display: inline-block; font-size: 11px; font-weight: 500; padding: 1px 9px; border-radius: 99px; background: var(--note-bg); color: var(--note); white-space: nowrap; }
.pill.ok { background: var(--ok-bg); color: var(--ok); } .pill.warn { background: var(--warn-bg); color: var(--warn); }
.pill.accent { background: var(--accent-bg); color: var(--accent); } .pill.pro { background: var(--pro-bg); color: var(--pro); }
.groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 10px; margin: 8px 0 12px; }
.group { border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px; min-width: 0; }
h4 { margin: 0 0 4px; font-size: 12px; font-weight: 600; color: var(--muted); }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 4px 0; border-top: 1px solid var(--line); word-break: break-word; }
tr:first-child th, tr:first-child td { border-top: 0; }
th { width: 42%; padding-right: 12px; font-weight: 400; color: var(--muted); }
td.name { font: 12px MONO_STACK; }
pre { background: var(--soft); border-radius: 10px; padding: 10px 12px; overflow-x: auto; white-space: pre-wrap; font: 13px MONO_STACK; margin: 4px 0 10px; }
img { max-width: 100%; border: 1px solid var(--line); border-radius: 10px; margin: 10px 0; }
p.note { color: var(--muted); font-style: italic; }
.files th { width: auto; font: 12px MONO_STACK; color: var(--text); } .files td { text-align: right; width: 1%; white-space: nowrap; }
@media print { body { background: #fff; } details > summary::before { display: none; } }
"""
HTML_STYLE = HTML_STYLE.replace("UI_STACK", fonts.CSS_STACKS[fonts.UI]).replace("MONO_STACK", fonts.CSS_STACKS[fonts.MONO]).replace("DARK_VARS", "--page: #14161a; --card: #1c1f25; --soft: #23272e; --line: #2e333b; --text: #e7e9ec; --muted: #98a1ad; --accent: #8fb0ff; --accent-bg: #23325a; --ok: #7fd6a1; --ok-bg: #1d3a2b; --warn: #f0c36a; --warn-bg: #3d3216; --pro: #b9a6f5; --pro-bg: #2f2850; --note: #b4bcc8; --note-bg: #2a2f37;")
KIND_PILLS = {"Tab file": "accent", "State record": "", "Window file": "pro", "App settings": "pro", "Skipped": "warn"}


def title(entry, include_text):
    t = entry.tab
    return TITLE_WITHHELD if t is not None and not t.has_path and not include_text else dnf.entry_title(entry)


def rows_of(rows):
    return [{"field": str(k), "value": v if isinstance(v, int) else str(v)} for k, v in rows]


def iso(ticks):
    return (datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ticks // 10)).isoformat(timespec="microseconds") + "Z"


def tab_groups(entry, view, index, include_text):
    t = entry.tab
    groups = [(name, rows) for name, rows in dnf.describe_entry(entry, view, index) if name not in ("Window", "Edit records")]
    if t is None:
        return groups
    if not include_text and not t.has_path:
        groups = [(name, [(k, TITLE_WITHHELD if k == "Title" else v) for k, v in rows]) for name, rows in groups]
    if t.edits:
        groups.append(("Edit records", [(f"#{i + 1} @{e.offset}", f"position {e.cursor}, delete {e.deletion}, add {e.addition}" + (f" {e.chars.decode('utf-16-le', errors='replace')!r}" if include_text and e.addition else "") + f"  crc {e.crc_stored:08x}" + ("" if e.crc_ok else f" (computed {e.crc_calc:08x})")) for i, e in enumerate(t.edits)]))
    return groups


def build(directory, include_text):
    windows = []
    for view in window_views(directory):
        w = view.window
        windows.append({
            "label": view.label,
            "window": None if w is None else {"file": os.path.abspath(w.path), "rows": rows_of(dnf.describe_window(w, None, view.settings)[1])},
            "tabs": [{
                "position": i + 1,
                "guid": e.guid,
                "tab_file": None if e.tab is None else os.path.abspath(e.tab.path),
                "state_record_file": None if e.delta is None else os.path.abspath(e.delta.path),
                "title": title(e, include_text),
                "modified": dnf.entry_modified(e),
                "badges": [{"text": text, "kind": kind} for text, kind in dnf.entry_badges(e, view, i)],
                "active": w is not None and i == w.selected,
                "groups": [{"name": name, "rows": rows_of(rows)} for name, rows in tab_groups(e, view, i, include_text)],
                "text": dnf.entry_text(e) if include_text and e.tab is not None else None,
            } for i, e in enumerate(view.entries)],
        })
    return {
        "report": REPORT_TITLE,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tab_text_included": include_text,
        "folder": directory.root,
        "scanned_folders": [os.path.abspath(f) for f in directory.folders],
        "scanned_files": [{"folder": os.path.abspath(f.folder), "name": f.name, "path": os.path.abspath(os.path.join(f.folder, f.name)), "kind": dnf.SCAN_KIND_LABELS[f.kind]} for f in directory.files],
        "skipped_files": directory.skipped,
        "windows": windows,
        "app_settings": [{
            "label": view.label,
            "file": os.path.abspath(view.settings.path),
            "badges": [{"text": text, "kind": kind} for text, kind in dnf.settings_badges(view.settings)],
            "groups": [{"name": name, "rows": rows_of(rows)} for name, rows in dnf.describe_settings(view.settings, [v for v in window_views(directory) if v.settings is view.settings])],
            "values": [{"key": "\\".join(v.key[1:]), "name": v.name, "type": v.type_name, "value": v.value, "set_utc": None if v.stamp is None else iso(v.stamp)} for v in view.settings.values],
        } for view in directory.views if view.is_settings],
    }


def window_views(directory):
    return [v for v in directory.views if not v.is_settings]


def csv_rows(directory, include_text):
    for view in window_views(directory):
        w = view.window
        for i, e in enumerate(view.entries):
            t, d = e.tab, e.delta
            cfg, sel, _ = dnf.effective(e)
            eol, enc = dnf.entry_format(e)
            row = dict.fromkeys(CSV_COLUMNS, "")
            row.update(record_type=CSV_TAB, window=view.label, window_guid="" if w is None else w.guid, window_file_path="" if w is None else os.path.abspath(w.path), tab_position=i + 1, active_tab=dnf.yes_no(w is not None and i == w.selected), tab_guid=e.guid, title=title(e, include_text),
                       selection_start=sel[0], selection_end=sel[1])
            if t is not None:
                row.update(tab_file_path=os.path.abspath(t.path), tab_file_size=t.size, tab_file_modified_utc=iso(t.mtime // 100 + dnf.EPOCH_DIFF_100NS), saved_to_path=dnf.yes_no(t.has_path),
                           line_ending=eol, encoding=enc, line_ending_encoding_source="stored" if t.has_path else "assumed default (not stored)", characters=len(t.content) // 2,
                           unsaved_flag=t.unsaved, edit_records=len(t.edits), edit_records_crc_valid=sum(x.crc_ok for x in t.edits), tab_crc_valid=dnf.yes_no(t.crc_ok),
                           text=dnf.entry_text(e) if include_text else "")
            if t is not None and t.has_path:
                row.update(file_path=t.file_path, recorded_file_size=t.file_size, file_last_write_utc=iso(t.timestamp), file_last_write_ticks=t.timestamp, stored_sha256=t.stored_hash.hex(), hash_check=dnf.hash_status(t))
            if d is not None:
                row.update(state_record_path=os.path.abspath(d.path), state_record_seq=d.seq, state_record_crc_valid=dnf.yes_no(d.crc_ok), state_record_applied=dnf.yes_no(dnf.effective(e)[2].startswith("state record")))
            if cfg is not None:
                row.update(word_wrap=dnf.yes_no(cfg.word_wrap), rtl=dnf.yes_no(cfg.rtl), show_unicode=dnf.yes_no(cfg.show_unicode), config_version=cfg.version, formatting_type=dnf.formatting_name(cfg))
            yield row
    for view in directory.views:
        if view.is_settings:
            for v in view.settings.values:
                yield dict.fromkeys(CSV_COLUMNS, "") | {"record_type": CSV_SETTING, "window": view.label, "setting_file": os.path.abspath(view.settings.path), "setting_name": dnf.settings_label(v.key, v.name), "setting_type": v.type_name, "setting_value": v.text, "setting_set_utc": "" if v.stamp is None else iso(v.stamp)}
    for folder in directory.folders:
        yield dict.fromkeys(CSV_COLUMNS, "") | {"record_type": CSV_FOLDER, "scan_folder": os.path.abspath(folder)}
        for f in (f for f in directory.files if f.folder == folder):
            path = os.path.join(folder, f.name)
            note = next((s[len(path) + 2:] for s in directory.skipped if s.startswith(path + ": ")), "")
            yield dict.fromkeys(CSV_COLUMNS, "") | {"record_type": CSV_FILE, "scan_folder": os.path.abspath(folder), "scan_file": f.name, "scan_file_kind": dnf.SCAN_KIND_LABELS[f.kind], "scan_note": note}


def screenshots(views):
    global qt_app
    from PyQt6.QtCore import QBuffer, QIODevice
    from PyQt6.QtGui import QGuiApplication
    from . import mockup
    if QGuiApplication.instance() is None:
        qt_app = QGuiApplication([])
    shots = []
    for v in views:
        if v.window is None or not v.entries:
            shots.append(None)
            continue
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        mockup.render(v).save(buf, "PNG")
        shots.append(base64.b64encode(bytes(buf.data())).decode())
    return shots


def table(rows, css=""):
    return f'<table class="{css}">' + "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows) + "</table>"


def pill(text, kind=""):
    return f'<span class="pill {kind}">{html.escape(text)}</span>'


def tile(number, label, css=""):
    return f'<div class="tile {css}"><b>{number}</b>{label}</div>'


def file_table(files):
    return '<table class="files">' + "".join(f"<tr><th>{html.escape(f['name'])}</th><td>{pill(f['kind'], KIND_PILLS.get(f['kind'], ''))}</td></tr>" for f in files) + "</table>"


def scan_html(data):
    e = html.escape
    parts = [f'<section class="card"><h2>Scan details</h2><p class="meta">{e(data["folder"])}</p>']
    for folder in data["scanned_folders"]:
        files = [f for f in data["scanned_files"] if f["folder"] == folder]
        parts.append(f"<details open><summary>{e(folder)} {pill(f'{len(files)} file(s)')}</summary>" + (file_table(files) if files else '<p class="note">No .bin files.</p>') + "</details>")
    if data["skipped_files"]:
        parts.append(f"<details open><summary>Files skipped {pill(str(len(data['skipped_files'])), 'warn')}</summary>" + table(("Skipped", s) for s in data["skipped_files"]) + "</details>")
    return "".join(parts) + "</section>"


def to_html(data, shots, theme=""):
    e = html.escape
    tabs = sum(len(w["tabs"]) for w in data["windows"])
    parts = [
        f'<!doctype html><html lang="en"{f" data-theme={theme}" if theme else ""}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{REPORT_TITLE}</title><style>{HTML_STYLE}</style></head><body>',
        f'<header><h1>{REPORT_TITLE}</h1><span class="meta">Generated {e(data["generated_utc"].replace("T", " ").replace("+00:00", ""))} UTC · tab text {"included" if data["tab_text_included"] else "not included"}</span></header>',
        '<div class="tiles">' + tile(len(data["windows"]), "windows") + tile(tabs, "tabs") + tile(len(data["scanned_files"]), "files scanned") + tile(len(data["skipped_files"]), "files skipped", "warn" if data["skipped_files"] else "") + "</div>",
        scan_html(data),
    ]
    for win, shot in zip(data["windows"], shots):
        parts.append(f"<section class=\"card\"><h2>{e(win['label'])}</h2>")
        if win["window"] is not None:
            parts.append(table(((r["field"], r["value"]) for r in win["window"]["rows"])))
        if shot is not None:
            parts.append(f'<img alt="Rendered Notepad window" src="data:image/png;base64,{shot}">')
        elif win["window"] is not None and not data["tab_text_included"]:
            parts.append('<p class="note">Rendered window omitted because it would show tab text.</p>')
        for tab in win["tabs"]:
            pills = "".join(pill(b["text"], b["kind"]) for b in tab["badges"])
            parts.append(f'<details open><summary><span class="pos">{tab["position"]}</span><span class="ttl">{e(tab["title"])}</span>{pills}</summary><div class="groups">')
            parts += [f'<div class="group"><h4>{e(group["name"])}</h4>' + table((r["field"], r["value"]) for r in group["rows"]) + "</div>" for group in tab["groups"]]
            parts.append("</div>")
            if tab["text"] is not None:
                parts.append(f"<h4>Text</h4><pre>{e(tab['text'])}</pre>")
            else:
                parts.append(f'<p class="note">{TEXT_WITHHELD if any(g["name"] == "Document" for g in tab["groups"]) else NO_TAB_FILE}</p>')
            parts.append("</details>")
        parts.append("</section>")
    for s in data["app_settings"]:
        parts.append(f'<section class="card"><h2>{e(s["label"])}</h2><p class="meta">{e(s["file"])}</p><p>{"".join(pill(b["text"], b["kind"]) for b in s["badges"])}</p><div class="groups">')
        parts += [f'<div class="group"><h4>{e(g["name"])}</h4>' + table((r["field"], r["value"]) for r in g["rows"]) + "</div>" for g in s["groups"]]
        parts.append("</div></section>")
    return "".join(parts) + "</body></html>"


def text_block(name, rows):
    width = max((len(r["field"]) for r in rows), default=0)
    return [f"[{name}]"] + [f"  {r['field'].ljust(width)}  {r['value']}" for r in rows]


def to_text(data):
    lines = [REPORT_TITLE, "", f"Folder: {data['folder']}", f"Generated (UTC): {data['generated_utc']}", f"Tab text included: {dnf.yes_no(data['tab_text_included'])}", "", f"Folders scanned ({len(data['scanned_folders'])}), files scanned ({len(data['scanned_files'])}):"]
    for folder in data["scanned_folders"]:
        lines += [f"  {folder}"] + [f"    {f['name']}  -  {f['kind']}" for f in data["scanned_files"] if f["folder"] == folder]
    lines += ["", f"Files skipped ({len(data['skipped_files'])}):"] + [f"  {s}" for s in data["skipped_files"]]
    for win in data["windows"]:
        lines += ["", TEXT_RULE, win["label"], TEXT_RULE]
        if win["window"] is not None:
            lines += text_block("Window", win["window"]["rows"])
        for tab in win["tabs"]:
            lines += ["", f"--- {tab['position']}. {tab['title']}{' *' if tab['modified'] else ''}{' (active tab)' if tab['active'] else ''} ---"]
            for group in tab["groups"]:
                lines += text_block(group["name"], group["rows"])
            if tab["text"] is not None:
                lines += ["[Text]"] + [f"  {line}" for line in tab["text"].split("\n")]
            else:
                lines.append(f"[Text] {TEXT_WITHHELD if any(g['name'] == 'Document' for g in tab['groups']) else NO_TAB_FILE}")
    for s in data["app_settings"]:
        lines += ["", TEXT_RULE, f"{s['label']}: {s['file']}", TEXT_RULE]
        for group in s["groups"]:
            lines += text_block(group["name"], group["rows"]) + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def render(directory, kind, include_text):
    if kind == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows(directory, include_text))
        return buf.getvalue()
    data = build(directory, include_text)
    if kind == "json":
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if kind in HTML_THEMES:
        views = window_views(directory)
        return to_html(data, screenshots(views) if include_text else [None] * len(views), HTML_THEMES[kind])
    return to_text(data)


def export(directory, path, kind, include_text):
    with open(path, "w", encoding="utf-8-sig" if kind == "csv" else "utf-8", newline="" if kind == "csv" else "\n") as f:
        f.write(render(directory, kind, include_text))
