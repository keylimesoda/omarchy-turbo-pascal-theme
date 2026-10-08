"""Select the optional GTK3 theme without editing existing GTK configuration."""

import json
from pathlib import Path
import subprocess
import sys


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
