#!/usr/bin/env python3
"""Install optional shell and compositor enhancements after the base Omarchy theme."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parent / "gtk"))
from gtk import THEME as GTK_THEME, SCHEMA as GTK_SCHEMA


PACKAGE = Path(__file__).resolve().parent.parent
UPSTREAM = "https://github.com/hyprwm/hyprland-plugins.git"
UPSTREAM_TAG = "v0.56.0"
UPSTREAM_COMMIT = "7644cecdb947060682891a0db2a0cdc5c0b9e704"
MODULES = (
    "menu", "monitor", "audio", "bluetooth", "network",
    "power", "clock", "agents", "weather", "tray",
)


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, indent=2)
        handle.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def fingerprint(path, runtime=False):
    if not path.exists():
        return None
    if path.is_symlink():
        raise RuntimeError(f"Refusing a symlink at {path}")
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        digest.update(str(path.stat().st_mode & 0o777).encode())
        return digest.hexdigest()
    for entry in sorted(path.rglob("*")):
        relative = entry.relative_to(path)
        if runtime and (
            relative.parts[:2] == ("hyprland-plugins", ".git")
            or relative.parts[0] == "__pycache__"
            or relative.as_posix() in (
                "plugin-session",
                "runtime-status.json",
                "build-hash",
                "client-hash",
                "gtk-previous.json",
                "hyprland-plugins/borders-plus-plus/borders-plus-plus.so",
            )
        ):
            continue
        digest.update(relative.as_posix().encode())
        if entry.is_symlink():
            raise RuntimeError(f"Refusing a symlink at {entry}")
        if entry.is_file():
            digest.update(entry.read_bytes())
            digest.update(str(entry.stat().st_mode & 0o777).encode())
    return digest.hexdigest()


def layout_ids(config):
    layout = config.get("bar", {}).get("layout", {})
    return {
        entry if isinstance(entry, str) else entry["id"]
        for section in ("left", "center", "right")
        for entry in layout.get(section, [])
    }

def active_ids(config):
    return layout_ids(config) | {
        entry if isinstance(entry, str) else entry["id"]
        for entry in config.get("plugins", [])
    } | {config.get("bar", {}).get("id", "omarchy.bar")}


def wait_shell():
    for _ in range(40):
        try:
            if run("omarchy-shell", "shell", "ping", capture=True) == "ok":
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(0.1)
    raise RuntimeError("The Omarchy shell did not respond after restarting.")


class Installer:
    def __init__(self, home=None, package=PACKAGE, allow_untested=False,
                 skip_widgets=False, skip_borders=False, skip_focus=False, skip_gtk=False, confirm=None):
        self.home = (home or Path.home()).resolve()
        self.package = package
        self.config = self.home / ".config/omarchy"
        self.shell = self.config / "shell.json"
        self.theme = self.config / "themes/turbo-pascal"
        self.data = self.home / ".local/share/omarchy-turbo-pascal"
        self.state_dir = self.home / ".local/state/omarchy/turbo-pascal-install"
        self.state_file = self.state_dir / "state.json"
        self.current = self.home / ".local/state/omarchy/current"
        self.state = None
        self.allow_untested = allow_untested
        self.skip_widgets = skip_widgets
        self.skip_borders = skip_borders
        self.skip_focus = skip_focus
        self.skip_gtk = skip_gtk
        self.gtk_theme = self.home / ".local/share/themes" / GTK_THEME
        self.confirm = confirm or confirm_replacement
        self.modules = {}
        self.skipped = []

    def skip(self, feature, reason):
        message = f"{feature}: {reason}"
        self.skipped.append(message)
        print(f"Skipped {message}", file=sys.stderr)

    def safe_path(self, path):
        path = Path(path)
        if not path.is_relative_to(self.home) or path == self.home:
            raise RuntimeError(f"Not an installation path: {path}")
        if path.is_symlink() or not path.resolve().is_relative_to(self.home):
            raise RuntimeError(f"Refusing a symlinked installation path: {path}")
        return path

    def save(self):
        write_json(self.state_file, self.state)

    def snapshot(self, path, runtime=False):
        self.safe_path(path)
        before = fingerprint(path, runtime)
        record = {"path": str(path.relative_to(self.home)), "before": before,
                  "installed": None, "runtime": runtime}
        if before is not None:
            backup = self.state_dir / "backup" / str(len(self.state["records"]))
            backup.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, backup)
            else:
                shutil.copy2(path, backup)
            record["backup"] = str(backup.relative_to(self.state_dir))
        self.state["records"].append(record)
        self.save()
        return record

    def finish_record(self, record):
        path = self.home / record["path"]
        record["installed"] = fingerprint(path, record["runtime"])
        self.save()

    def preflight(self, check=False):
        self.modules = {}
        self.skipped = []
        if os.geteuid() == 0:
            raise RuntimeError("Run as your desktop user, not with sudo.")
        if not (self.theme / "colors.toml").is_file():
            raise RuntimeError(
                "Install the base theme first:\n"
                "omarchy theme install https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git")
        for command in ("omarchy", "hyprctl", "bash"):
            if not shutil.which(command):
                raise RuntimeError(f"Missing dependency: {command}")
        version = run("omarchy", "version", capture=True)
        self.compositor = read_json_text(run("hyprctl", "version", "-j", capture=True))
        match = re.match(r"v?(\d+)\.(\d+)\.", self.compositor["version"])
        known = (version.startswith("4.") and match
                 and (0, 52) <= (int(match[1]), int(match[2])) <= (0, 56))
        if not known and not self.allow_untested:
            raise RuntimeError(
                f"Untested Omarchy/Hyprland: {version}/{self.compositor['version']}. "
                "Use --allow-untested to try compatible extras, or use the base theme alone.")
        if not known:
            print("Trying an untested version; incompatible extras will be skipped.", file=sys.stderr)
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            raise RuntimeError("Run inside your Hyprland desktop session.")
        self.focus = not self.skip_focus
        self.borders = not self.skip_borders
        self.gtk = not self.skip_gtk
        if self.gtk:
            try:
                if not shutil.which("gsettings"):
                    raise RuntimeError("gsettings is unavailable")
                run("gsettings", "get", GTK_SCHEMA, "gtk-theme", capture=True)
                self.safe_path(self.gtk_theme)
                if self.gtk_theme.exists():
                    raise RuntimeError(f"an existing GTK theme would be overwritten: {self.gtk_theme}")
            except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                self.gtk = False
                self.skip("GTK3 styling", str(error))
        errors = run("hyprctl", "configerrors", capture=True)
        if errors:
            self.focus = self.borders = False
            self.skip("native effects", f"fix existing config errors first: {errors}")
        if self.borders:
            try:
                plugins = read_json_text(run("hyprctl", "plugins", "list", "-j", capture=True))
                if any(plugin["name"] == "borders-plus-plus" for plugin in plugins):
                    self.borders = False
                    self.skip("double borders", "another borders-plus-plus is already loaded")
                missing = [name for name in ("git", "make", "g++", "pkg-config")
                           if not shutil.which(name)]
                if missing:
                    raise RuntimeError(f"missing build tools: {', '.join(missing)}")
                run("pkg-config", "--exists", "pixman-1", "libdrm", "hyprland",
                    "pangocairo", "libinput", "libudev", "wayland-server", "xkbcommon")
            except (RuntimeError, ValueError, subprocess.CalledProcessError) as error:
                self.borders = False
                self.skip("double borders", str(error))
        if self.state_dir.exists() and not self.state_file.is_file():
            raise RuntimeError(f"Unrecognized installation state at {self.state_dir}.")
        if self.state_file.exists() and read_json(self.state_file)["status"] not in (
            "uninstalled", "rolled-back",
        ):
            raise RuntimeError("An installation already exists; uninstall it before reinstalling.")
        if self.data.exists():
            raise RuntimeError(f"Refusing to overwrite existing runtime files: {self.data}")
        if not (self.current / "theme.name").is_file():
            raise RuntimeError("No active Omarchy theme was found.")
        self.plan_widgets(check)
        for event in ("theme-set", "post-boot"):
            hook = self.config / "hooks" / f"{event}.d/turbo-pascal-borders"
            self.safe_path(hook)
            if hook.exists():
                raise RuntimeError(f"An existing border hook would be overwritten: {hook}")
        for path in (self.shell, self.data, self.state_dir):
            self.safe_path(path)
            fingerprint(path)

    def plan_widgets(self, check):
        if self.skip_widgets:
            return
        try:
            if not shutil.which("omarchy-shell"):
                raise RuntimeError("Omarchy shell plugin support is unavailable")
            wait_shell()
            config = self.effective_config()
            catalog = read_json_text(run("omarchy-shell", "shell", "listPlugins", capture=True))
            if not isinstance(catalog, list):
                raise RuntimeError("The shell plugin catalog is unavailable.")
        except (RuntimeError, ValueError, subprocess.CalledProcessError) as error:
            self.skip("widgets", str(error))
            return
        for module in MODULES:
            source = f"omarchy.{module}"
            if not any(item["id"] == source for item in catalog):
                self.skip(source, "this stock component is unavailable")
                continue
            custom = []
            for item in catalog:
                if item.get("clonedFrom") == source:
                    if (item["id"] in active_ids(config) or item.get("enabled")) and item["id"] not in custom:
                        custom.append(item["id"])
            if custom and (check or not self.confirm(
                    f"Replace {', '.join(custom)} with the styled stock-based {module}? "
                    "Its files stay, but custom behavior will not carry over.")):
                self.skip(source, "custom component kept")
                continue
            if module != "menu" and not (
                    source in active_ids(config) or custom):
                continue
            if module == "menu" and source in config.get("disabledPlugins", []) and not custom:
                continue
            target = self.config / "plugins" / f"turbo-pascal.{module}"
            self.safe_path(target)
            if target.exists() and (check or not self.confirm(f"Back up and replace {target}?")):
                self.skip(source, "existing plugin files kept")
                continue
            self.modules[module] = custom
        library = self.config / "plugins/turbo-pascal.bar"
        self.safe_path(library)
        if self.modules and library.exists():
            if check or not self.confirm(f"Back up and replace the shared widget library at {library}?"):
                self.modules = {}
                self.skip("widgets", "shared widget library could not be installed")

    def effective_config(self):
        config = read_json_text(run("omarchy-shell", "shell", "listShellConfig", capture=True))
        if not isinstance(config, dict) or config.get("version") != 1:
            raise RuntimeError("The shell's effective configuration is unsupported.")
        return config

    def build(self):
        source = self.data / "hyprland-plugins"
        match = re.match(r"v?(\d+)\.(\d+)\.", self.compositor["version"])
        if not match:
            raise RuntimeError("Cannot select a version-matched plugin source.")
        tag = f"v{match[1]}.{match[2]}.0"
        run("git", "clone", "--quiet", "--depth", "1", "--branch",
            tag, UPSTREAM, str(source))
        commit = run("git", "-C", str(source), "rev-parse", "HEAD", capture=True)
        if tag == UPSTREAM_TAG and commit != UPSTREAM_COMMIT:
            raise RuntimeError(f"Unexpected border source commit: {commit}")
        self.state["border_source"] = {"tag": tag, "commit": commit}
        self.save()
        run("git", "-C", str(source), "apply", "--check",
            str(self.package / "extras/borders/active-only.patch"))
        run("git", "-C", str(source), "apply",
            str(self.package / "extras/borders/active-only.patch"))
        run("bash", str(self.data / "apply-borders"), "--build")

    def install(self, check=False):
        self.preflight(check)
        if check:
            print(f"Available: {len(self.modules)} widget enhancements; "
                  f"focus effects={self.focus}; border build candidate={self.borders}; "
                  f"GTK3 styling={self.gtk}. Nothing changed.")
            return
        if self.state_dir.exists():
            archive = self.state_dir.with_name(f"{self.state_dir.name}-backup-{time.time_ns()}")
            self.state_dir.rename(archive)
        self.state_dir.mkdir(parents=True)
        self.state = {
            "version": 2, "status": "installing", "records": [],
            "previous_theme": (self.current / "theme.name").read_text().strip(),
            "enabled": [], "replacements": {}, "skipped": self.skipped,
        }
        self.save()
        try:
            data_record = self.snapshot(self.data, runtime=True)
            self.data.mkdir(parents=True)
            shutil.copy2(self.package / "extras/borders/apply-borders", self.data)
            shutil.copy2(self.package / "hyprland.lua", self.data)
            for name in ("runtime.py", "focus.conf", "client-hash.cpp"):
                shutil.copy2(self.package / "extras/borders" / name, self.data)
            shutil.copy2(self.package / "extras/gtk/gtk.py", self.data)
            write_json(self.data / "features.json", {
                "focus": self.focus, "borders": self.borders, "gtk": self.gtk})
            self.finish_record(data_record)
            if self.borders:
                try:
                    self.build()
                except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                    self.borders = False
                    self.skip("double borders", f"build unavailable or incompatible: {error}")
                finally:
                    write_json(self.data / "features.json", {
                        "focus": self.focus, "borders": self.borders, "gtk": self.gtk})
                    self.finish_record(data_record)
            if self.gtk:
                record = self.snapshot(self.gtk_theme)
                target = self.gtk_theme / "gtk-3.0"
                target.mkdir(parents=True)
                for name in ("gtk.css", "gtk-dark.css"):
                    shutil.copy2(self.package / "extras/gtk/gtk.css", target / name)
                self.finish_record(record)
            # Keep the existing import path, but install no replacement-bar manifest or engine.
            copied = (["bar"] + list(self.modules)) if self.modules else []
            for module in copied:
                name = f"turbo-pascal.{module}"
                target = self.config / "plugins" / name
                record = self.snapshot(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)
                if module == "bar":
                    shutil.copytree(self.package / "extras/plugins" / name / "DosUi",
                                    target / "DosUi")
                else:
                    shutil.copytree(self.package / "extras/plugins" / name, target)
                self.finish_record(record)
            if self.modules:
                shell_record = self.snapshot(self.shell)
                before = self.effective_config()
                run("omarchy-shell", "shell", "rescanPlugins")
                for module, custom in self.modules.items():
                    name = f"turbo-pascal.{module}"
                    original = self.shell.read_bytes() if self.shell.is_file() else None
                    try:
                        for old in custom:
                            run("omarchy", "plugin", "disable", old)
                        run("omarchy", "plugin", "enable", name)
                    except subprocess.CalledProcessError as error:
                        if original is None:
                            self.shell.unlink(missing_ok=True)
                        else:
                            self.shell.write_bytes(original)
                        self.skip(name, f"could not activate; previous settings restored: {error}")
                        self.finish_record(shell_record)
                        continue
                    self.state["enabled"].append(name)
                    self.state["replacements"][name] = custom
                    config = self.effective_config()
                    old_ids = custom or [f"omarchy.{module}"]
                    if before.get("bar", {}).get("centerAnchor") in old_ids:
                        config["bar"]["centerAnchor"] = name
                    if module == "menu" and not any(old in layout_ids(before) for old in old_ids):
                        for entries in config["bar"]["layout"].values():
                            entries[:] = [entry for entry in entries if (
                                entry if isinstance(entry, str) else entry["id"]) != name]
                        if name not in active_ids(config):
                            config.setdefault("plugins", []).append({"id": name})
                    write_json(self.shell, config)
                    self.finish_record(shell_record)
            for event in ("theme-set", "post-boot"):
                target = self.config / "hooks" / f"{event}.d/turbo-pascal-borders"
                record = self.snapshot(target)
                run("omarchy", "hook", "install", event,
                    str(self.package / "extras/borders/turbo-pascal-borders"))
                if not target.is_file():
                    raise RuntimeError(f"The hook was not installed: {target}")
                self.finish_record(record)
            if (self.current / "theme.name").read_text().strip() != "turbo-pascal":
                run("omarchy", "theme", "set", "turbo-pascal")
                if (self.current / "theme.name").read_text().strip() != "turbo-pascal":
                    raise RuntimeError("Omarchy did not activate Turbo Pascal; restoring the previous settings.")
            run("bash", str(self.data / "apply-borders"))
            if self.modules:
                run("omarchy", "restart", "shell")
                wait_shell()
            self.state["runtime"] = read_json(self.data / "runtime-status.json")
            self.state["status"] = "installed"
            self.save()
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, KeyboardInterrupt):
            print(f"Installation interrupted or failed. Restoring backups from {self.state_dir}.",
                  file=sys.stderr)
            for record in self.state["records"]:
                if record["installed"] is None:
                    self.finish_record(record)
            self.rollback()
            raise
        print(f"Extras installed: {len(self.state['enabled'])} widget enhancements.")
        print(f"Native effects: {self.state['runtime']}")
        print(f"Backups: {self.state_dir}")

    def restore_record(self, record):
        if record.get("restored"):
            return
        path = self.safe_path(self.home / record["path"])
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        if "backup" in record:
            backup = self.state_dir / record["backup"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if backup.is_dir():
                shutil.copytree(backup, path)
            else:
                shutil.copy2(backup, path)
        record["restored"] = True
        self.save()

    def rollback(self):
        self.state["status"] = "rolling-back"
        self.save()
        unload_error = None
        self.prepare_gtk_restore()
        if (self.data / "apply-borders").is_file():
            try:
                run("bash", str(self.data / "apply-borders"), "--unload")
            except (OSError, subprocess.CalledProcessError) as error:
                unload_error = error
                print(f"Could not unload borders: {error}. Runtime retained for retry.", file=sys.stderr)
        for record in reversed(self.state["records"]):
            if not (unload_error and record["runtime"]):
                self.restore_record(record)
        self.refresh_theme_for_cleanup(self.state["previous_theme"])
        self.finish_gtk_restore()
        if self.modules:
            run("omarchy", "restart", "shell")
            wait_shell()
        if unload_error:
            raise RuntimeError("Independent files restored; retry ./uninstall.sh to finish cleanup.")
        self.state["status"] = "rolled-back"
        self.save()

    def uninstall(self):
        if not self.state_file.is_file():
            raise RuntimeError("No companion installation was found.")
        self.state = read_json(self.state_file)
        if self.state["status"] in ("rolled-back", "uninstalled"):
            print(f"Already removed. Backups retained at {self.state_dir}.")
            return
        rolling_back = self.state["status"] in ("installing", "rolling-back")
        resuming = self.state["status"] in ("uninstalling", "rolling-back")
        for record in self.state["records"]:
            if record.get("restored") or record["path"] == str(self.shell.relative_to(self.home)):
                continue
            actual = fingerprint(self.home / record["path"], record["runtime"])
            if actual != record["installed"] and not (resuming and actual is None):
                raise RuntimeError(
                    f"Local edits detected: {record['path']}. Back them up and restore "
                    "the installed version before uninstalling; no more files were removed.")
        self.state["status"] = "rolling-back" if rolling_back else "uninstalling"
        self.save()
        self.prepare_gtk_restore()
        if (self.data / "apply-borders").is_file():
            run("bash", str(self.data / "apply-borders"), "--unload")
        current_theme = (self.current / "theme.name").read_text().strip()
        shell_record = next((record for record in self.state["records"]
                             if record["path"] == str(self.shell.relative_to(self.home))), None)
        if shell_record is None or shell_record.get("restored"):
            pass
        elif fingerprint(self.shell) == shell_record["installed"]:
            self.restore_record(shell_record)
        else:
            if "pending_restore" not in shell_record:
                active = active_ids(self.effective_config())
                shell_record["pending_restore"] = [
                    plugin for plugin in self.state.get("enabled", []) if plugin in active]
                self.save()
            for plugin in list(shell_record["pending_restore"]):
                originals = (self.state.get("replacements", {}).get(plugin) or
                             [plugin.replace("turbo-pascal.", "omarchy.", 1)])
                if plugin == "turbo-pascal.bar":
                    if plugin in active_ids(self.effective_config()):
                        run("omarchy", "plugin", "enable", originals[0])
                elif plugin in active_ids(self.effective_config()):
                    run("omarchy", "plugin", "disable", plugin)
                for old in self.state.get("replacements", {}).get(plugin, []):
                    if old not in active_ids(self.effective_config()):
                        run("omarchy", "plugin", "enable", old)
                shell_record["pending_restore"].remove(plugin)
                self.save()
            config = self.effective_config()
            anchor = config.get("bar", {}).get("centerAnchor")
            if anchor in self.state.get("enabled", []):
                config["bar"]["centerAnchor"] = (
                    self.state.get("replacements", {}).get(anchor) or
                    [anchor.replace("turbo-pascal.", "omarchy.", 1)])[0]
                write_json(self.shell, config)
            shell_record["restored"] = True
            self.save()
        for record in reversed(self.state["records"]):
            if record is not shell_record:
                self.restore_record(record)
        if current_theme == "turbo-pascal" and not self.state.get("theme_refreshed"):
            theme = ("turbo-pascal" if self.state.get("version") == 2 and not rolling_back
                     else self.state["previous_theme"])
            self.refresh_theme_for_cleanup(theme)
            self.state["theme_refreshed"] = True
            self.save()
        if current_theme == "turbo-pascal" or rolling_back:
            self.finish_gtk_restore()
        if shell_record:
            run("omarchy", "restart", "shell")
            wait_shell()
        self.state["status"] = "rolled-back" if rolling_back else "uninstalled"
        self.save()
        print(f"Companion customizations removed. Backups retained at {self.state_dir}.")

    def prepare_gtk_restore(self):
        previous = self.data / "gtk-previous.json"
        if "gtk_last_selection" in self.state:
            selected = run("gsettings", "get", GTK_SCHEMA, "gtk-theme", capture=True)
            if selected != self.state["gtk_last_selection"]:
                self.state["gtk_restore"] = selected
                self.state["gtk_restored"] = False
                self.save()
        elif previous.is_file() and "gtk_restore" not in self.state:
            selected = run("gsettings", "get", GTK_SCHEMA, "gtk-theme", capture=True)
            self.state["gtk_restore"] = (
                read_json(previous)["theme"] if selected == repr(GTK_THEME) else selected)
            self.save()

    def refresh_theme_for_cleanup(self, theme):
        try:
            run("omarchy", "theme", "set", theme)
        finally:
            if "gtk_restore" in self.state:
                self.state["gtk_last_selection"] = run(
                    "gsettings", "get", GTK_SCHEMA, "gtk-theme", capture=True)
                self.save()

    def finish_gtk_restore(self):
        if "gtk_restore" in self.state and not self.state.get("gtk_restored"):
            run("gsettings", "set", GTK_SCHEMA, "gtk-theme", self.state["gtk_restore"])
            if run("gsettings", "get", GTK_SCHEMA, "gtk-theme", capture=True) != self.state["gtk_restore"]:
                raise RuntimeError("Previous GTK theme selection was not restored; retry uninstall.")
            self.state["gtk_restored"] = True
            self.state["gtk_last_selection"] = self.state["gtk_restore"]
            self.save()


def read_json_text(text):
    return json.loads(text)


def confirm_replacement(message):
    if not sys.stdin.isatty():
        print(f"{message} Non-interactive run: keeping it.", file=sys.stderr)
        return False
    return input(f"{message}\nReplace? [y/N] ").strip().lower() in ("y", "yes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--check", action="store_true", help="Check installation prerequisites only")
    parser.add_argument("--allow-untested", action="store_true", help="Try extras on an untested version; ABI checks stay enabled")
    parser.add_argument("--skip-widgets", action="store_true", help="Keep existing widgets")
    parser.add_argument("--skip-borders", action="store_true", help="Do not build the window-border plugin")
    parser.add_argument("--skip-focus", action="store_true", help="Keep existing opacity, dimming and animations")
    parser.add_argument("--skip-gtk", action="store_true", help="Keep existing GTK3 application and browser styling")
    args = parser.parse_args()
    try:
        installer = Installer(allow_untested=args.allow_untested, skip_widgets=args.skip_widgets,
                              skip_borders=args.skip_borders, skip_focus=args.skip_focus,
                              skip_gtk=args.skip_gtk)
        if args.action == "install":
            installer.install(args.check)
        elif args.check:
            parser.error("--check is only supported for install")
        else:
            installer.uninstall()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        print(f"Turbo Pascal: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
