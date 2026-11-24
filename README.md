# Denoted

Viewer and parser for the TabState and WindowState `.bin` files that Windows 11 Notepad keeps for its open tabs and windows. It shows what each file holds, including unsaved tab text, and allows you to inspect the raw bytes behind every value.

## Features

- Opens a single state file, a folder of state files (optionally recursive), or the running computer's live Notepad data for one or more user profiles.
- Shows each window and tab as a Notepad-style mock-up, with a details panel for the values parsed from the file.
- Raw view: a hex dump with a colour legend and an offset table, so every parsed value can be traced to its bytes.
- Scan details: which folders and files were scanned, and which were skipped and why.
- Exports to HTML (system, light or dark theme), JSON, CSV and plain text. Every export includes the list of scanned files.
- Themes!

## Requirements

- Windows, Linux or macOS. Opening state files and folders works everywhere, including files copied off a Windows machine.
- Live-system mode (`File > Open Live System`, `--live`, `--list-users`) is Windows only. It is disabled elsewhere.
- Python 3.10 or later
- PyQt6

To install it as a package, use `pip install .`, which will add the `denoted` (GUI) and `denoted-cli` commands.
`pip` package coming soon!

## Command line

```
denoted-cli C:\path\to\TabState
denoted-cli --live -f html -o report.html
denoted-cli --list-users
```

| Option | Meaning |
|---|---|
| `paths` | State files and/or folders. Each path is loaded on its own. |
| `-r`, `--recursive` | Scan subfolders of folder paths. |
| `--live [USER ...]` | Windows only. Read this computer's Notepad data for the named users, or for every user that has data. |
| `--list-users` | Windows only. List the user profiles and whether they have Notepad data. |
| `-f`, `--format` | `text` (default), `json`, `csv`, `html`, `html-light` or `html-dark`. |
| `-o`, `--output` | Write to a file instead of the console. Required for the HTML formats. |
| `--no-text` | Leave out tab text, edit-record text, unsaved-tab titles and the rendered window picture. |

## Notes

State files can contain whatever was typed into a tab, so treat them, and any export made from them, as sensitive. Use `--no-text` (or leave tab text out in the export dialog) when you want a report without the content.

My inspiration to develop this tool came after reading the research of AbdulRhman Alfaifi (https://u0041.co/posts/articals/exploring-windows-artifacts-notepad-files/).
