import argparse
import os
import sys

from . import export
from . import format as dnf


def parse_args(argv):
    p = argparse.ArgumentParser(prog="Denoted", description="Denoted: dump Windows Notepad TabState and WindowState files.")
    p.add_argument("paths", nargs="*", help="state files and/or folders; each path is loaded on its own")
    p.add_argument("-r", "--recursive", action="store_true", help="scan subfolders of folder paths")
    p.add_argument("--live", nargs="*", metavar="USER", help="Windows only: read this computer's Notepad data for the named users, or for every user that has data when no name is given (list any paths before --live)")
    p.add_argument("--list-users", action="store_true", help="Windows only: list the user profiles on this computer and whether they have Notepad data, then exit")
    p.add_argument("-f", "--format", choices=list(export.FORMATS), default="text", help="output format (default: text)")
    p.add_argument("-o", "--output", help="write to this file instead of the console (required for html)")
    p.add_argument("--no-text", action="store_true", help="leave out tab text, edit-record text, unsaved-tab titles and the rendered window picture")
    args = p.parse_args(argv)
    if not (args.paths or args.live is not None or args.list_users):
        p.error("give at least one path, or --live, or --list-users")
    return args


def list_users():
    users = dnf.find_live_users()
    width = max((len(u.name) for u in users), default=0)
    for u in users:
        print(f"{u.name.ljust(width)}  {f'{u.files} .bin file(s)' if u.files else u.problem}  {u.profile}")


def pick_users(names):
    found = dnf.find_live_users()
    if not names:
        return [u for u in found if u.files]
    by_name = {u.name.lower(): u for u in found}
    unknown = [n for n in names if n.lower() not in by_name]
    if unknown:
        sys.exit(f"Unknown user(s): {', '.join(unknown)}. Profiles found: {', '.join(u.name for u in found) or 'none'}")
    users = [by_name[n.lower()] for n in dict.fromkeys(names)]
    unusable = [f"{u.name}: {u.problem}" for u in users if not u.files]
    if unusable:
        sys.exit("No Notepad data to read - " + "; ".join(unusable))
    return users


def main(argv=None):
    args = parse_args(argv)
    if (args.list_users or args.live is not None) and not dnf.IS_WINDOWS:
        sys.exit(dnf.LIVE_UNAVAILABLE)
    if args.list_users:
        list_users()
        return
    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        sys.exit("Not found: " + ", ".join(missing))
    if args.format in export.HTML_THEMES and not args.output:
        sys.exit("The html formats need -o OUTPUT.")
    directory = dnf.load_paths(args.paths, args.recursive) if args.paths else dnf.Directory("", [], [], [])
    if args.live is not None:
        users = pick_users(args.live)
        if not users:
            sys.exit("No user on this computer has Notepad data (use --list-users).")
        live = dnf.load_live(users)
        directory = dnf.Directory("; ".join(filter(None, (directory.root, live.root))), directory.folders + live.folders, directory.views + live.views, directory.skipped + live.skipped, directory.files + live.files)
    if not directory.views:
        sys.exit("No tab or window state files found." + "".join(f"\n  skipped {s}" for s in directory.skipped))
    if args.output:
        export.export(directory, args.output, args.format, not args.no_text)
        print(f"Wrote {os.path.abspath(args.output)}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(export.render(directory, args.format, not args.no_text).encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
