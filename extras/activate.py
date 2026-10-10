#!/usr/bin/env python3
"""Prepare full theme styling after Omarchy stages the trusted Lua entry point."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

from installer import Installer, fingerprint, read_json, write_json

MARKER = "-- TURBO PASCAL AUTOMATIC EXTRAS"
PACKAGE = Path(__file__).resolve().parent.parent
ERRORS = (OSError, ValueError, RuntimeError, subprocess.CalledProcessError)


def source_digest(package):
    digest = hashlib.sha256()
    files = [package / "hyprland.lua", package / "VERSION"]
    files += sorted((package / "extras").rglob("*"))
    for path in files:
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            if path.is_symlink():
                raise RuntimeError(f"Refusing a symlinked companion source: {path}")
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def trusted(home):
    source = home / ".config/omarchy/themes/turbo-pascal"
    current = home / ".local/state/omarchy/current"
    lua = current / "theme/hyprland.lua"
    return ((current / "theme.name").read_text().strip() == "turbo-pascal"
            and not (source / ".git").is_dir()
            and lua.is_file() and MARKER in lua.read_text())


def reconcile(home, package=PACKAGE, hook=False, disable=False, enable=False):
    """Serialize reloads, preserve edited files, and migrate older installations."""
    state_root = home / ".local/state/omarchy"
    state_root.mkdir(parents=True, exist_ok=True)
    disabled = state_root / "turbo-pascal-disabled"
    failed = state_root / "turbo-pascal-extras-failed.json"
    lock = state_root / "turbo-pascal-extras.lock"
    with lock.open("a") as handle:
        try:
            # Theme hooks and explicit requests must run after a concurrent
            # bootstrap; dropping a hook could leave GTK/borders dormant.
            mode = fcntl.LOCK_EX if hook or disable or enable else fcntl.LOCK_EX | fcntl.LOCK_NB
            fcntl.flock(handle, mode)
        except BlockingIOError:
            return 0
        instance = Installer(home, package=package, automatic=True,
                             skip_focus=True, confirm=lambda message: False)
        if disable:
            # Suppress Lua bootstrap before any cleanup can reload the compositor.
            disabled.touch()
            if instance.state_file.exists():
                instance.uninstall()
            subprocess.run(["hyprctl", "reload"], check=True)
            return 0
        if enable:
            if not trusted(home):
                raise RuntimeError("Remove the installed theme's .git directory and reapply Turbo Pascal first.")
            disabled.unlink(missing_ok=True)
            failed.unlink(missing_ok=True)
        if disabled.exists() or not trusted(home):
            if (instance.data / "apply-borders").is_file():
                subprocess.run(["bash", str(instance.data / "apply-borders"), "--unload"], check=True)
            return 0
        signature = source_digest(package)
        if failed.exists() and read_json(failed).get("source") == signature:
            return 0
        try:
            state = read_json(instance.state_file) if instance.state_file.exists() else None
            if state and state["status"] == "installed" and state.get("automatic_source") == signature and not enable:
                # Bootstrap runs on every compositor reload; only hooks reapply effects.
                # Refuse edited runtime code instead of executing it from an automatic hook.
                runtime_record = next(record for record in state["records"] if record["runtime"])
                if fingerprint(instance.data, True) != runtime_record["installed"]:
                    raise RuntimeError("Local runtime edits detected; back them up before updating extras.")
                if hook or enable:
                    subprocess.run(["bash", str(instance.data / "apply-borders")], check=True)
                if enable:
                    subprocess.run(["hyprctl", "reload"], check=True)
                return 0
            if state and state["status"] not in ("uninstalled", "rolled-back"):
                # Handles the previous install.sh state and changed companion sources.
                # Uninstall checks fingerprints before changing any owned files.
                instance.uninstall()
            # Theme switching replaces current/theme. Work from a private snapshot
            # so a switch during compilation cannot remove our setup sources.
            with tempfile.TemporaryDirectory(prefix="turbo-pascal-source-", dir=state_root) as temporary:
                snapshot = Path(temporary)
                shutil.copytree(package / "extras", snapshot / "extras", symlinks=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for name in ("hyprland.lua", "VERSION"):
                    shutil.copy2(package / name, snapshot / name)
                if source_digest(snapshot) != signature:
                    raise RuntimeError("Theme sources changed during setup; reapply to retry.")
                instance.package = snapshot
                instance.install()
            instance.state["automatic_source"] = signature
            instance.state["automatic_version"] = (package / "VERSION").read_text().strip()
            instance.save()
            if not trusted(home):
                subprocess.run(["bash", str(instance.data / "apply-borders"), "--unload"], check=True)
            elif enable:
                subprocess.run(["hyprctl", "reload"], check=True)
            failed.unlink(missing_ok=True)
        except ERRORS as error:
            # A failed build/setup must not retrigger indefinitely on config reload.
            write_json(failed, {"source": signature, "error": str(error)})
            raise
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--hook", action="store_true", help="Reapply extras after a theme change")
    action.add_argument("--disable", action="store_true", help="Remove extras and keep automatic setup disabled")
    action.add_argument("--enable", action="store_true", help="Enable extras or retry a failed setup")
    args = parser.parse_args()
    try:
        home = Path.home()
        # current/theme is generated and may contain the runtime's border overlay.
        # Compare the stable installed sources, never that generated output.
        package = home / ".config/omarchy/themes/turbo-pascal"
        return reconcile(home, package=package, hook=args.hook,
                         disable=args.disable, enable=args.enable)
    except ERRORS as error:
        print(f"Turbo Pascal extras: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
