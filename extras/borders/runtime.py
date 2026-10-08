#!/usr/bin/env python3
"""Apply independent, explicitly installed focus and border enhancements."""

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from gtk import GtkTheme


ERRORS = (OSError, ValueError, RuntimeError, subprocess.CalledProcessError)
PACKAGES = ("pixman-1", "libdrm", "hyprland", "pangocairo",
            "libinput", "libudev", "wayland-server", "xkbcommon")
BORDER_LUA = """hl.config({
  general = { border_size = 1 },
  plugin = { borders_plus_plus = {
    add_borders = 2, active_only = true, natural_rounding = false,
    border_size_1 = 1, border_size_2 = 1,
    col = { border_1 = "rgb(0000aa)", border_2 = "rgb(ffffff)" },
  }},
})
"""
BORDER_CONF = """general:border_size = 1
plugin:borders-plus-plus:add_borders = 2
plugin:borders-plus-plus:active_only = true
plugin:borders-plus-plus:natural_rounding = false
plugin:borders-plus-plus:border_size_1 = 1
plugin:borders-plus-plus:border_size_2 = 1
plugin:borders-plus-plus:col.border_1 = rgb(0000aa)
plugin:borders-plus-plus:col.border_2 = rgb(ffffff)
"""


def run(*args):
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.stdout.strip()


class Runtime:
    def __init__(self, home=None):
        self.home = home or Path.home()
        self.data = self.home / ".local/share/omarchy-turbo-pascal"
        self.current = self.home / ".local/state/omarchy/current"
        self.source = self.data / "hyprland-plugins/borders-plus-plus"
        self.plugin = self.source / "borders-plus-plus.so"
        self.marker = self.data / "plugin-session"
        self.session = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not self.session:
            raise RuntimeError("Run inside your Hyprland desktop session.")

    def loaded(self):
        return any(item["name"] == "borders-plus-plus"
                   for item in json.loads(run("hyprctl", "plugins", "list", "-j")))

    def owned(self):
        return self.marker.is_file() and self.marker.read_text().strip() == self.session

    def build(self):
        version = json.loads(run("hyprctl", "version", "-j"))
        flags = shlex.split(run("pkg-config", "--cflags", *PACKAGES))
        run("g++", "-std=c++2b", *flags, str(self.data / "client-hash.cpp"),
            "-o", str(self.data / "client-hash"))
        header_hash = run(str(self.data / "client-hash"))
        if not version.get("commit") or header_hash.split("_", 1)[0] != version["commit"]:
            raise RuntimeError("Headers do not match the running compositor commit; borders skipped.")
        if version.get("abiHash") and header_hash != version["abiHash"]:
            raise RuntimeError("Headers/dependencies do not match the compositor ABI; borders skipped.")
        if version.get("abiHash"):
            dependencies = run("pkg-config", "--modversion", "aquamarine", "hyprutils",
                               "hyprgraphics", "hyprcursor", "hyprlang").splitlines()
            if len(dependencies) != 5:
                raise RuntimeError("Could not identify installed dependency versions.")
            installed_hash = version["commit"] + "".join(
                f"_{name}_{value.rsplit('.', 1)[0]}"
                for name, value in zip(("aq", "hu", "hg", "hc", "hlg"), dependencies))
            if installed_hash != version["abiHash"]:
                raise RuntimeError("Installed dependency versions do not match the compositor ABI.")
        run("make", "-s", "-C", str(self.source))
        (self.data / "build-hash").write_text(header_hash + "\n")

    def load(self):
        if self.loaded():
            if not self.owned():
                raise RuntimeError("Another borders-plus-plus is loaded; preserving it.")
            return
        version = json.loads(run("hyprctl", "version", "-j"))
        built = self.data / "build-hash"
        abi = built.read_text().strip() if built.is_file() else ""
        if (not self.plugin.is_file() or not abi
                or abi.split("_", 1)[0] != version.get("commit")
                or version.get("abiHash", abi) != abi):
            self.build()
        # Record ownership before loading so an interrupted install can unload it.
        self.marker.write_text(self.session + "\n")
        reply = run("hyprctl", "plugin", "load", str(self.plugin))
        if not self.loaded():
            raise RuntimeError(f"The border plugin did not load: {reply}")

    def unload(self):
        if self.owned() and self.loaded():
            reply = run("hyprctl", "plugin", "unload", str(self.plugin))
            if self.loaded():
                raise RuntimeError(f"The border plugin did not unload: {reply}")
        self.marker.unlink(missing_ok=True)

    @staticmethod
    def strip(text):
        return re.sub(r"\n(?:--|#) BEGIN TURBO PASCAL EXTRAS\n.*?"
                      r"(?:--|#) END TURBO PASCAL EXTRAS\n", "", text, flags=re.S)

    def reload(self):
        reply = run("hyprctl", "reload")
        if reply and reply.lower() != "ok":
            raise RuntimeError(f"Reload failed: {reply}")
        errors = run("hyprctl", "configerrors")
        if errors:
            raise RuntimeError(errors)

    def write(self, path, base, content):
        prefix = "--" if path.suffix == ".lua" else "#"
        path.write_text(base + (
            f"\n{prefix} BEGIN TURBO PASCAL EXTRAS\n{content}"
            f"\n{prefix} END TURBO PASCAL EXTRAS\n" if content else ""))
        self.reload()

    def remove(self):
        gtk_error = None
        try:
            GtkTheme(self.home).remove()
        except ERRORS as error:
            gtk_error = error
        for name in ("hyprland.lua", "hyprland.conf"):
            path = self.current / "theme" / name
            if path.is_file():
                original = path.read_text()
                base = self.strip(original)
                if base != original:
                    path.write_text(base)
                    self.reload()
        self.unload()
        if gtk_error:
            raise gtk_error

    def apply(self):
        status = {"active": [], "skipped": []}
        features = json.loads((self.data / "features.json").read_text())
        if features.get("gtk") and (
                self.current / "theme.name").read_text().strip() == "turbo-pascal":
            try:
                GtkTheme(self.home).apply()
                status["active"].append("GTK3 styling")
            except ERRORS as error:
                try:
                    GtkTheme(self.home).remove()
                except ERRORS as restore_error:
                    self.warn(status, "GTK3 restoration", restore_error)
                self.warn(status, "GTK3 styling", error)
        if (self.current / "theme.name").read_text().strip() != "turbo-pascal":
            self.remove()
            status["dormant"] = True
        elif features["focus"] or features["borders"]:
            path = next((self.current / "theme" / name
                         for name in ("hyprland.lua", "hyprland.conf")
                         if (self.current / "theme" / name).is_file()), None)
            if path is None:
                self.warn(status, "native effects", "No generated Hyprland theme file was found.")
            else:
                base, content = self.strip(path.read_text()), ""
                if features["focus"]:
                    try:
                        content = (self.data / ("hyprland.lua" if path.suffix == ".lua"
                                                else "focus.conf")).read_text()
                        if path.suffix == ".conf":
                            version = json.loads(run("hyprctl", "version", "-j"))["version"]
                            match = re.match(r"v?(\d+)\.(\d+)\.", version)
                            if not match:
                                raise RuntimeError(f"Unknown rule syntax for {version}")
                            if (int(match[1]), int(match[2])) < (0, 53):
                                for name, rule in (
                                    ("inactive-opacity", "opacity 0.97 override,"
                                     "tag:default-opacity,focus:0,fullscreen:0"),
                                    ("pop-square", "rounding 0,tag:pop"),
                                ):
                                    content = re.sub(
                                        rf"windowrule \{{\s*name = turbo-pascal-{name}\b.*?\}}",
                                        f"windowrulev2 = {rule}", content, flags=re.S)
                        self.write(path, base, content)
                        status["active"].append("focus effects")
                    except ERRORS as error:
                        content = ""
                        self.write(path, base, content)
                        self.warn(status, "focus effects", error)
                if features["borders"]:
                    try:
                        self.load()
                        self.write(path, base, content + "\n" +
                                   (BORDER_LUA if path.suffix == ".lua" else BORDER_CONF))
                        status["active"].append("double borders")
                    except ERRORS as error:
                        self.write(path, base, content)
                        self.unload()
                        self.warn(status, "double borders", error)
        (self.data / "runtime-status.json").write_text(json.dumps(status, indent=2) + "\n")
        if status["skipped"]:
            try:
                run("omarchy-notification-send", "Turbo Pascal: some extras skipped",
                    "See ~/.local/share/omarchy-turbo-pascal/runtime-status.json")
            except (OSError, subprocess.CalledProcessError) as error:
                print(f"Could not send notification: {error}", file=sys.stderr)

    @staticmethod
    def warn(status, feature, error):
        message = f"{feature}: {error}"
        status["skipped"].append(message)
        print(f"Skipped {message}", file=sys.stderr)


def main():
    try:
        runtime = Runtime()
        if sys.argv[1:] == ["--build"]:
            runtime.build()
        elif sys.argv[1:] == ["--unload"]:
            runtime.remove()
        else:
            runtime.apply()
    except ERRORS as error:
        print(f"Turbo Pascal extras: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
