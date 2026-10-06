#!/usr/bin/env python3
"""Install the opt-in shell and compositor customizations as the desktop user."""

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


PACKAGE = Path(__file__).resolve().parent.parent
UPSTREAM = "https://github.com/hyprwm/hyprland-plugins.git"
UPSTREAM_TAG = "v0.56.0"
UPSTREAM_COMMIT = "7644cecdb947060682891a0db2a0cdc5c0b9e704"
MODULES = (
    "bar", "menu", "monitor", "audio", "bluetooth", "network",
    "power", "clock", "agents", "weather", "tray",
)
THEME_FILES = (
    "colors.toml", "icons.theme", "hyprland.lua", "shell.bar.toml",
    "shell.controls.toml", "shell.launcher.toml", "shell.menu.toml",
    "shell.popups.toml", "artwork", "backgrounds",
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
            or relative.as_posix() in (
                "plugin-session",
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
    def __init__(self, home=None, package=PACKAGE):
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

    def preflight(self):
        if os.geteuid() == 0:
            raise RuntimeError("Run as your desktop user, not with sudo.")
        for command in (
            "omarchy", "omarchy-shell", "hyprctl", "git", "make", "g++",
            "pkg-config", "jq", "bash", "install",
        ):
            if not shutil.which(command):
                raise RuntimeError(f"Missing dependency: {command}")
        version = run("omarchy", "version", capture=True)
        if not re.fullmatch(r"4\.0\.4(?:-\d+)?", version):
            raise RuntimeError(f"Supported Omarchy: 4.0.4; found {version}")
        version = read_json_text(run("hyprctl", "version", "-j", capture=True))["version"]
        headers = run("pkg-config", "--modversion", "hyprland", capture=True)
        if version != "0.56.2" or headers != version:
            raise RuntimeError(
                f"Need Hyprland 0.56.2 and matching headers; found {version}/{headers}")
        run("pkg-config", "--exists", "pixman-1", "libdrm", "hyprland",
            "pangocairo", "libinput", "libudev", "wayland-server", "xkbcommon")
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            raise RuntimeError("Run inside your Hyprland desktop session.")
        if not (self.home / ".config/hypr/hyprland.lua").is_file():
            raise RuntimeError("This installer requires Omarchy's Lua Hyprland configuration.")
        if run("omarchy-shell", "shell", "ping", capture=True) != "ok":
            raise RuntimeError("The Omarchy shell did not respond.")
        if run("hyprctl", "configerrors", capture=True):
            raise RuntimeError("Fix existing Hyprland config errors before installing.")
        plugins = read_json_text(run("hyprctl", "plugins", "list", "-j", capture=True))
        if any(plugin["name"] == "borders-plus-plus" for plugin in plugins):
            raise RuntimeError("Another borders-plus-plus plugin is already loaded.")
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
        config = self.effective_config()
        if config.get("bar", {}).get("id", "omarchy.bar") != "omarchy.bar":
            raise RuntimeError("A custom bar is active; refusing to replace it.")
        for module in MODULES:
            source = f"omarchy.{module}"
            for manifest in (self.config / "plugins").glob("*/manifest.json"):
                item = read_json(manifest)
                if item.get("omarchy", {}).get("clonedFrom") == source:
                    if item["id"] in active_ids(config):
                        raise RuntimeError(f"A custom clone of {source} is active: {item['id']}")
            target = self.config / "plugins" / f"turbo-pascal.{module}"
            self.safe_path(target)
            if target.exists():
                raise RuntimeError(f"Refusing to overwrite an existing plugin: {target}")
        for event in ("theme-set", "post-boot"):
            hook = self.config / "hooks" / f"{event}.d/turbo-pascal-borders"
            self.safe_path(hook)
            if hook.exists():
                raise RuntimeError(f"An existing border hook would be overwritten: {hook}")
        for path in (self.shell, self.theme, self.data, self.state_dir):
            self.safe_path(path)
            fingerprint(path)

    def effective_config(self):
        if self.shell.is_file():
            return read_json(self.shell)
        root = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
        return read_json(root / "config/omarchy/shell.json")

    def build(self):
        source = self.data / "hyprland-plugins"
        run("git", "clone", "--quiet", "--depth", "1", "--branch",
            UPSTREAM_TAG, UPSTREAM, str(source))
        commit = run("git", "-C", str(source), "rev-parse", "HEAD", capture=True)
        if commit != UPSTREAM_COMMIT:
            raise RuntimeError(f"Unexpected border source commit: {commit}")
        run("git", "-C", str(source), "apply", "--check",
            str(self.package / "extras/borders/active-only.patch"))
        run("git", "-C", str(source), "apply",
            str(self.package / "extras/borders/active-only.patch"))
        run("bash", str(self.data / "apply-borders"), "--build")

    def install(self, check=False):
        self.preflight()
        if check:
            print("Compatibility and prerequisites OK; nothing changed.")
            return
        if self.state_dir.exists():
            archive = self.state_dir.with_name(f"{self.state_dir.name}-backup-{time.time_ns()}")
            self.state_dir.rename(archive)
        self.state_dir.mkdir(parents=True)
        self.state = {
            "version": 1, "status": "installing", "records": [],
            "previous_theme": (self.current / "theme.name").read_text().strip(),
        }
        self.save()
        try:
            data_record = self.snapshot(self.data, runtime=True)
            self.data.mkdir(parents=True)
            shutil.copy2(self.package / "extras/borders/apply-borders", self.data)
            shutil.copy2(self.package / "hyprland.lua", self.data)
            self.build()
            self.finish_record(data_record)
            theme_record = self.snapshot(self.theme)
            self.theme.mkdir(parents=True, exist_ok=True)
            for name in THEME_FILES:
                source, target = self.package / name, self.theme / name
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, target)
            self.finish_record(theme_record)
            for module in MODULES:
                name = f"turbo-pascal.{module}"
                target = self.config / "plugins" / name
                record = self.snapshot(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(self.package / "extras/plugins" / name, target)
                self.finish_record(record)
            shell_record = self.snapshot(self.shell)
            before = self.effective_config()
            enabled = []
            run("omarchy-shell", "shell", "rescanPlugins")
            for module in MODULES:
                if module == "bar" or f"omarchy.{module}" in layout_ids(before):
                    run("omarchy", "plugin", "enable", f"turbo-pascal.{module}")
                    enabled.append(f"turbo-pascal.{module}")
            self.state["enabled"] = enabled
            self.finish_record(shell_record)
            for event in ("theme-set", "post-boot"):
                target = self.config / "hooks" / f"{event}.d/turbo-pascal-borders"
                record = self.snapshot(target)
                run("omarchy", "hook", "install", event,
                    str(self.package / "extras/borders/turbo-pascal-borders"))
                if not target.is_file():
                    raise RuntimeError(f"The hook was not installed: {target}")
                self.finish_record(record)
            run("omarchy", "theme", "set", "turbo-pascal")
            run("bash", str(self.data / "apply-borders"))
            run("omarchy", "restart", "shell")
            wait_shell()
            self.state["status"] = "installed"
            self.save()
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
            print(f"Installation failed. Restoring backups from {self.state_dir}.",
                  file=sys.stderr)
            self.rollback()
            raise
        print("Turbo Pascal installed, including double-white window and widget borders.")
        print(f"Backups: {self.state_dir}")

    def restore_record(self, record):
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

    def rollback(self):
        if (self.data / "apply-borders").is_file():
            run("bash", str(self.data / "apply-borders"), "--unload")
        for record in reversed(self.state["records"]):
            self.restore_record(record)
        run("omarchy", "theme", "set", self.state["previous_theme"])
        run("omarchy", "restart", "shell")
        wait_shell()
        self.state["status"] = "rolled-back"
        self.save()

    def uninstall(self):
        if not self.state_file.is_file():
            raise RuntimeError("No companion installation was found.")
        self.state = read_json(self.state_file)
        if self.state["status"] in ("rolled-back", "uninstalled"):
            print(f"Already removed. Backups retained at {self.state_dir}.")
            return
        for record in self.state["records"]:
            if record["path"] == str(self.shell.relative_to(self.home)):
                continue
            actual = fingerprint(self.home / record["path"], record["runtime"])
            if actual != record["installed"]:
                raise RuntimeError(
                    f"Local edits detected: {record['path']}. Back them up and restore "
                    "the installed version before uninstalling; nothing was removed.")
        run("bash", str(self.data / "apply-borders"), "--unload")
        current_theme = (self.current / "theme.name").read_text().strip()
        shell_record = next(record for record in self.state["records"]
                            if record["path"] == str(self.shell.relative_to(self.home)))
        if fingerprint(self.shell) == shell_record["installed"]:
            self.restore_record(shell_record)
        else:
            config = self.effective_config()
            active = active_ids(config)
            for plugin in self.state.get("enabled", []):
                if plugin in active:
                    run("omarchy", "plugin", "disable", plugin)
        for record in reversed(self.state["records"]):
            if record is not shell_record:
                self.restore_record(record)
        if current_theme == "turbo-pascal":
            run("omarchy", "theme", "set", self.state["previous_theme"])
        run("omarchy", "restart", "shell")
        wait_shell()
        self.state["status"] = "uninstalled"
        self.save()
        print(f"Companion customizations removed. Backups retained at {self.state_dir}.")


def read_json_text(text):
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--check", action="store_true", help="Check installation prerequisites only")
    args = parser.parse_args()
    try:
        installer = Installer()
        if args.action == "install":
            installer.install(args.check)
        elif args.check:
            parser.error("--check is only supported for install")
        else:
            installer.uninstall()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Turbo Pascal: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
