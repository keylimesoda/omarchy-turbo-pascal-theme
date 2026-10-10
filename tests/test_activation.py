"""Lifecycle coverage for trusted theme setup, migration, and local edits."""
import fcntl
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import test_installer
ROOT = test_installer.ROOT
installer = test_installer.installer

sys.path.insert(0, str(ROOT / "extras"))
spec = importlib.util.spec_from_file_location("activation", ROOT / "extras/activate.py")
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)
activation.Installer = installer.Installer


class ActivationTests(unittest.TestCase):
    setUp = test_installer.InstallerTests.setUp
    tearDown = test_installer.InstallerTests.tearDown

    def stage(self):
        (self.instance.current / "theme.name").write_text("turbo-pascal")
        theme = self.instance.current / "theme"
        theme.mkdir(exist_ok=True)
        (theme / "hyprland.lua").write_text((ROOT / "hyprland.lua").read_text())

    def reconcile(self, **options):
        def command(args, **kwargs):
            self.desktop.run(*args)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(activation.subprocess, "run", command):
            return activation.reconcile(self.home, package=ROOT, **options)

    def state(self):
        return installer.read_json(self.instance.state_file)

    def test_theme_hook_waits_for_bootstrap_instead_of_dropping_effects(self):
        self.stage()
        self.reconcile()
        lock = self.home / ".local/state/omarchy/turbo-pascal-extras.lock"
        finished = threading.Event()
        errors = []
        def worker():
            try:
                self.reconcile(hook=True)
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertFalse(finished.wait(0.05))
            fcntl.flock(handle, fcntl.LOCK_UN)
        thread.join(5)
        self.assertTrue(finished.is_set())
        self.assertEqual(errors, [])
        self.assertEqual(self.desktop.calls[-1],
                         ("bash", str(self.instance.data / "apply-borders")))

    def test_cli_uses_installed_sources_instead_of_generated_theme(self):
        self.stage()
        with patch.object(activation.Path, "home", return_value=self.home), \
             patch.object(activation, "reconcile", return_value=0) as reconcile, \
             patch.object(sys, "argv", ["activate.py"]):
            self.assertEqual(activation.main(), 0)
        self.assertEqual(reconcile.call_args.kwargs["package"], self.instance.theme)

    def test_git_theme_cannot_start_companion_setup(self):
        self.stage()
        (self.instance.theme / ".git").mkdir()
        self.reconcile()
        self.assertFalse(self.instance.state_file.exists())
        with self.assertRaisesRegex(RuntimeError, "Remove"):
            self.reconcile(enable=True)

    def test_reload_is_idempotent_and_hook_reapplies(self):
        self.stage()
        self.reconcile()
        before = self.instance.state_file.read_bytes()
        calls = len(self.desktop.calls)
        self.reconcile()
        self.assertEqual(len(self.desktop.calls), calls)
        self.assertEqual(self.instance.state_file.read_bytes(), before)
        self.reconcile(hook=True)
        self.assertEqual(self.desktop.calls[-1], ("bash", str(self.instance.data / "apply-borders")))
        self.assertFalse(installer.read_json(self.instance.data / "features.json")["focus"])
        self.assertFalse(any(call[:3] == ("omarchy", "theme", "set") for call in self.desktop.calls))

    def test_previous_install_migrates_preserving_widget_options(self):
        self.instance.install()
        self.stage()
        self.reconcile()
        self.assertIn("automatic_source", self.state())
        config = installer.read_json(self.instance.shell)
        self.assertEqual(config["bar"]["layout"]["center"],
                         [{"id": "turbo-pascal.clock", "format": "HH:mm"}])
        self.assertEqual(config["idle"], {"lock": 300})

    def test_changed_source_updates_owned_installation(self):
        self.stage()
        self.reconcile()
        state = self.state()
        state["automatic_source"] = "older-source"
        installer.write_json(self.instance.state_file, state)
        self.reconcile()
        self.assertEqual(self.state()["automatic_source"], activation.source_digest(ROOT))
        self.assertTrue(list(self.instance.state_dir.parent.glob("turbo-pascal-install-backup-*")))

    def test_edited_managed_files_block_update_before_removal(self):
        self.stage()
        self.reconcile()
        state = self.state()
        state["automatic_source"] = "older-source"
        installer.write_json(self.instance.state_file, state)
        edited = self.instance.config / "plugins/turbo-pascal.clock/Panel.qml"
        edited.write_text("my local edits")
        with self.assertRaisesRegex(RuntimeError, "Local edits"):
            self.reconcile()
        self.assertEqual(edited.read_text(), "my local edits")
        # Further reloads do not loop on the same failed source.
        self.reconcile()
        self.assertEqual(self.state()["status"], "installed")

    def test_disable_removes_extras_and_prevents_reinstallation(self):
        self.stage()
        self.reconcile()
        self.reconcile(disable=True)
        self.assertFalse(self.instance.data.exists())
        self.assertEqual(self.state()["status"], "uninstalled")
        self.reconcile()
        self.assertFalse(self.instance.data.exists())
        self.reconcile(enable=True)
        self.assertEqual(self.state()["status"], "installed")

    def test_custom_widget_is_preserved_without_prompt(self):
        target = self.instance.config / "plugins/custom.clock"
        target.mkdir(parents=True)
        installer.write_json(target / "manifest.json", {
            "id": "custom.clock", "omarchy": {"clonedFrom": "omarchy.clock"}})
        config = installer.read_json(self.instance.shell)
        config["bar"]["layout"]["center"][0]["id"] = "custom.clock"
        installer.write_json(self.instance.shell, config)
        self.stage()
        self.reconcile()
        self.assertNotIn("turbo-pascal.clock", self.state()["enabled"])
        self.assertTrue(target.exists())

    def test_untrusted_reapplication_restores_runtime(self):
        self.stage()
        self.reconcile()
        (self.instance.theme / ".git").mkdir()
        self.reconcile(hook=True)
        self.assertEqual(self.desktop.calls[-1],
                         ("bash", str(self.instance.data / "apply-borders"), "--unload"))
