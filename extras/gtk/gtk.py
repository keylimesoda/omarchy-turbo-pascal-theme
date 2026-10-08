"""Manage the optional GTK theme selection and reversible GTK4 CSS import."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


THEME = "omarchy-turbo-pascal"
SCHEMA = "org.gnome.desktop.interface"


def run(*args):
    result = subprocess.run(args, check=True, text=True, capture_output=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.stdout.strip()


def current_theme():
    return run("gsettings", "get", SCHEMA, "gtk-theme")


def select_theme(value):
    run("gsettings", "set", SCHEMA, "gtk-theme", value)
    if current_theme() != value:
        raise RuntimeError("GTK theme selection did not take effect.")


class GtkTheme:
    def __init__(self, home=None):
        self.home = home or Path.home()
        self.previous = self.home / ".local/share/omarchy-turbo-pascal/gtk-previous.json"

    def apply(self):
        if not (self.home / ".local/share/themes" / THEME / "gtk-3.0/gtk.css").is_file():
            raise RuntimeError("The optional GTK3 theme is missing.")
        current = current_theme()
        if current == repr(THEME):
            if not self.previous.is_file():
                raise RuntimeError("GTK theme is already selected without a restoration record.")
            return
        self.previous.write_text(json.dumps({"theme": current}) + "\n")
        select_theme(repr(THEME))

    def remove(self):
        if not self.previous.is_file():
            return
        if current_theme() == repr(THEME):
            select_theme(json.loads(self.previous.read_text())["theme"])
        self.previous.unlink()


class Gtk4Theme:
    BEGIN = "/* BEGIN TURBO PASCAL GTK4 */"

    def __init__(self, home=None, data=None):
        self.home = home or Path.home()
        self.data = data or self.home / ".local/share/omarchy-turbo-pascal"
        self.styles = self.home / ".config/gtk-4.0/gtk.css"
        self.source = self.data / "gtk4.css"
        self.previous = self.data / "gtk4-previous.json"
        self.block = (
            f'\n{self.BEGIN}\n@import url("{self.source.as_uri()}");\n'
            "/* END TURBO PASCAL GTK4 */\n"
        )

    def check(self):
        for path in (self.styles, *self.styles.parents):
            if path == self.home.parent:
                break
            if path.is_symlink():
                raise RuntimeError(f"Refusing a symlinked GTK4 stylesheet path: {path}")
        if self.styles.exists() and not self.styles.is_file():
            raise RuntimeError(f"Not a GTK4 stylesheet file: {self.styles}")
        contents = self.styles.read_bytes().decode("utf-8") if self.styles.exists() else ""
        owned = self.BEGIN in contents or self.source.as_uri() in contents
        if owned and (not self.previous.is_file() or contents.count(self.block) != 1):
            raise RuntimeError("GTK4 import is unrecognized or edited; existing CSS was preserved.")
        return contents

    def write_styles(self, contents):
        mode = stat.S_IMODE(self.styles.stat().st_mode) if self.styles.exists() else 0o644
        self.styles.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=self.styles.parent, delete=False
            ) as output:
                temporary = Path(output.name)
                output.write(contents)
            temporary.chmod(mode)
            os.replace(temporary, self.styles)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def record(self):
        record = json.loads(self.previous.read_text())
        if not isinstance(record, dict) or any(
            type(record.get(key)) is not kind
            for key, kind in (("existed", bool), ("directory_created", bool), ("css", str))
        ):
            raise RuntimeError("Invalid GTK4 restoration record; existing CSS was preserved.")
        return record

    def apply(self):
        if not self.source.is_file():
            raise RuntimeError("The optional GTK4 stylesheet is missing.")
        contents = self.check()
        if self.previous.is_file():
            self.record()
            if self.block in contents:
                return
            self.remove()
        self.previous.write_text(json.dumps({
            "existed": self.styles.exists(),
            "directory_created": not self.styles.parent.exists(),
            "css": contents,
        }) + "\n")
        self.write_styles(contents + self.block)

    def remove(self):
        if not self.previous.is_file():
            return
        contents = self.check()
        record = self.record()
        if self.block in contents:
            remaining = contents.replace(self.block, "", 1)
            if not record["existed"] and not remaining:
                self.styles.unlink()
            else:
                self.write_styles(remaining)
        if (record["directory_created"] and self.styles.parent.is_dir()
                and not any(self.styles.parent.iterdir())):
            self.styles.parent.rmdir()
        self.previous.unlink()


if __name__ == "__main__":
    try:
        theme = Gtk4Theme(data=Path(__file__).resolve().parent)
        active = (theme.home / ".local/state/omarchy/current/theme.name").read_text().strip()
        if active == "turbo-pascal":
            theme.apply()
        else:
            theme.remove()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Turbo Pascal GTK4: {error}", file=sys.stderr)
        sys.exit(1)
