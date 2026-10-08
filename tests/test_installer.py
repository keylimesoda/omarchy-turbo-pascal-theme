import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("installer", ROOT / "extras/installer.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

DEFAULT = {
    "version": 1,
    "idle": {"lock": 300},
    "bar": {
        "position": "bottom",
        "centerAnchor": "omarchy.clock",
        "layout": {
            "left": [{"id": "omarchy.menu"}, {"id": "omarchy.workspaces"}],
            "center": [{"id": "omarchy.clock", "format": "HH:mm"}],
            "right": [{"id": "omarchy.power"}, {"id": "custom.example", "option": 42}],
        },
    },
    "plugins": [{"id": "custom.service"}],
}


class DesktopFixture:
    def __init__(self, instance):
        self.instance = instance
        self.calls = []
        self.omarchy_version = "4.0.4-1"
        self.hyprland_version = "0.56.2"
        self.plugins = []
        self.fail_enable = False
        self.fail_build = False

    def config(self):
        if self.instance.shell.is_file():
            config = installer.read_json(self.instance.shell)
            if isinstance(config, dict) and config.get("version") == 1:
                return config
        return copy.deepcopy(DEFAULT)

    def run(self, *args, capture=False):
        self.calls.append(args)
        if args == ("omarchy", "version"):
            return self.omarchy_version
        if args == ("hyprctl", "version", "-j"):
            return json.dumps({"version": self.hyprland_version})
        if args == ("pkg-config", "--modversion", "hyprland"):
            return "0.56.2"
        if args == ("hyprctl", "plugins", "list", "-j"):
            return json.dumps(self.plugins)
        if args == ("hyprctl", "configerrors"):
            return ""
        if args == ("omarchy-shell", "shell", "ping"):
            return "ok"
        if args == ("omarchy-shell", "shell", "listShellConfig"):
            return json.dumps(self.config())
        if args == ("omarchy-shell", "shell", "listPlugins"):
            catalog = [{"id": f"omarchy.{module}"} for module in installer.MODULES]
            for path in (self.instance.config / "plugins").glob("*/manifest.json"):
                item = installer.read_json(path)
                catalog.append({"id": item["id"],
                                "clonedFrom": item.get("omarchy", {}).get("clonedFrom"),
                                "enabled": item["id"] in installer.active_ids(self.config())})
            return json.dumps(catalog)
        if args[0] == "bash" and "apply-borders" in args[1] and args[-1] not in ("--build", "--unload"):
            installer.write_json(self.instance.data / "runtime-status.json",
                                 {"active": ["focus effects"], "skipped": []})
        if args[:3] == ("omarchy", "plugin", "enable"):
            if self.fail_enable:
                raise subprocess.CalledProcessError(1, args)
            config = self.config()
            name = args[3]
            source = "omarchy." + name.split(".", 1)[1]
            if name.endswith(".bar"):
                config["bar"]["id"] = name
            for entries in config["bar"]["layout"].values():
                for entry in entries:
                    if entry["id"] == source:
                        entry["id"] = name
            if name == "turbo-pascal.menu":
                config.setdefault("disabledPlugins", []).append("omarchy.menu")
                config.setdefault("cloneSourceRestores", []).append(name)
            installer.write_json(self.instance.shell, config)
        elif args[:3] == ("omarchy", "plugin", "disable"):
            config = self.config()
            name = args[3]
            if name.endswith(".bar"):
                raise subprocess.CalledProcessError(1, args)
            source = "omarchy." + name.split(".", 1)[1]
            if config["bar"].get("id") == name:
                del config["bar"]["id"]
            for entries in config["bar"]["layout"].values():
                for entry in entries:
                    if entry["id"] == name:
                        entry["id"] = source
            config["plugins"] = [entry for entry in config.get("plugins", [])
                                 if entry["id"] != name]
            for key, value in (("disabledPlugins", source), ("cloneSourceRestores", name)):
                if value in config.get(key, []):
                    config[key].remove(value)
                    if not config[key]:
                        del config[key]
            installer.write_json(self.instance.shell, config)
        elif args[:3] == ("omarchy", "hook", "install"):
            source = Path(args[4])
            target = self.instance.config / "hooks" / f"{args[3]}.d" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            target.chmod(0o755)
        elif args[:3] == ("omarchy", "theme", "set"):
            (self.instance.current / "theme.name").write_text(args[3])
        elif args[:2] == ("git", "clone"):
            if self.fail_build:
                raise subprocess.CalledProcessError(1, args)
            source = Path(args[-1]) / "borders-plus-plus"
            source.mkdir(parents=True)
            (source / "main.cpp").write_text("fixture source")
            (source / "borders-plus-plus.so").write_bytes(b"fixture binary")
        elif args[0] == "git" and "rev-parse" in args:
            return installer.UPSTREAM_COMMIT
        return ""


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name) / "home"
        self.home.mkdir()
        self.instance = installer.Installer(self.home)
        self.instance.current.mkdir(parents=True)
        (self.instance.current / "theme.name").write_text("tokyo-night")
        hypr = self.home / ".config/hypr"
        hypr.mkdir(parents=True)
        (hypr / "hyprland.lua").write_text("-- fixture")
        installer.write_json(self.instance.shell, copy.deepcopy(DEFAULT))
        self.instance.theme.mkdir(parents=True)
        shutil.copy2(ROOT / "colors.toml", self.instance.theme)
        shutil.copy2(ROOT / "LICENSE", self.instance.theme)
        shutil.copytree(ROOT / "licenses", self.instance.theme / "licenses")
        self.desktop = DesktopFixture(self.instance)
        self.patches = [
            patch.object(installer, "run", self.desktop.run),
            patch.object(installer.shutil, "which", return_value="/bin/fixture"),
            patch.object(installer.os, "geteuid", return_value=1000),
            patch.dict(installer.os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "fixture"}),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_install_preserves_wallpaper_license_notices(self):
        self.instance.install()
        for name in ("runtime.py", "focus.conf", "client-hash.cpp", "apply-borders"):
            self.assertEqual((self.instance.data / name).read_bytes(),
                             (ROOT / "extras/borders" / name).read_bytes())
        self.assertEqual(
            (self.instance.theme / "licenses/scarecrow-bbs-NOTICE.txt").read_bytes(),
            (ROOT / "licenses/scarecrow-bbs-NOTICE.txt").read_bytes(),
        )
        self.assertEqual(
            (self.instance.theme / "LICENSE").read_bytes(),
            (ROOT / "LICENSE").read_bytes(),
        )

    def test_install_preserves_layout_options_and_unrelated_settings(self):
        self.instance.install()
        config = installer.read_json(self.instance.shell)
        self.assertEqual(config["idle"], DEFAULT["idle"])
        self.assertEqual(config["plugins"], DEFAULT["plugins"])
        self.assertEqual(config["bar"]["position"], "bottom")
        self.assertNotIn("id", config["bar"])
        self.assertEqual(config["bar"]["centerAnchor"], "turbo-pascal.clock")
        self.assertEqual(config["bar"]["layout"]["center"],
                         [{"id": "turbo-pascal.clock", "format": "HH:mm"}])
        self.assertEqual(config["bar"]["layout"]["right"][1],
                         {"id": "custom.example", "option": 42})
        self.assertNotIn("turbo-pascal.audio", installer.layout_ids(config))
        self.assertEqual(self.instance.state["status"], "installed")
        for event in ("theme-set", "post-boot"):
            self.assertTrue((self.instance.config / "hooks" /
                            f"{event}.d/turbo-pascal-borders").is_file())

    def test_uninstall_restores_shell_and_retains_base_theme(self):
        original = self.instance.shell.read_bytes()
        self.instance.install()
        self.instance.uninstall()
        self.assertEqual(self.instance.shell.read_bytes(), original)
        self.assertTrue(self.instance.theme.exists())
        self.assertFalse(self.instance.data.exists())
        self.assertEqual((self.instance.current / "theme.name").read_text(), "turbo-pascal")
        self.assertTrue(self.instance.state_file.is_file())
        self.instance.uninstall()

    def test_uninstall_preserves_later_layout_edits(self):
        self.instance.install()
        config = installer.read_json(self.instance.shell)
        config["bar"]["layout"]["right"].reverse()
        config["bar"]["layout"]["center"][0]["format"] = "dddd HH:mm"
        config["idle"]["lock"] = 999
        installer.write_json(self.instance.shell, config)
        self.instance.uninstall()
        result = installer.read_json(self.instance.shell)
        self.assertEqual(result["idle"]["lock"], 999)
        self.assertEqual(result["bar"]["layout"]["center"],
                         [{"id": "omarchy.clock", "format": "dddd HH:mm"}])
        self.assertEqual(result["bar"]["layout"]["right"][0]["id"], "custom.example")
        self.assertNotIn("disabledPlugins", result)

    def test_uninstall_leaves_later_selected_theme_alone(self):
        self.instance.install()
        (self.instance.current / "theme.name").write_text("catppuccin")
        self.instance.uninstall()
        self.assertEqual((self.instance.current / "theme.name").read_text(), "catppuccin")

    def test_existing_theme_is_not_overwritten(self):
        (self.instance.theme / "colors.toml").write_text("original palette")
        (self.instance.theme / "personal.txt").write_text("keep")
        self.instance.install()
        self.assertEqual((self.instance.theme / "colors.toml").read_text(), "original palette")
        self.instance.uninstall()
        self.assertEqual((self.instance.theme / "colors.toml").read_text(), "original palette")
        self.assertEqual((self.instance.theme / "personal.txt").read_text(), "keep")

    def test_missing_user_shell_config_restored_to_absence(self):
        self.instance.shell.unlink()
        defaults = self.home / "defaults/config/omarchy"
        defaults.mkdir(parents=True)
        installer.write_json(defaults / "shell.json", copy.deepcopy(DEFAULT))
        with patch.dict(installer.os.environ, {"OMARCHY_PATH": str(self.home / "defaults")}):
            self.instance.install()
            self.instance.uninstall()
        self.assertFalse(self.instance.shell.exists())

    def test_dry_check_changes_nothing(self):
        self.instance.install(check=True)
        self.assertFalse(self.instance.data.exists())
        self.assertFalse(self.instance.state_dir.exists())
        self.assertEqual(installer.read_json(self.instance.shell), DEFAULT)

    def test_unsupported_version_refused_before_changes(self):
        self.desktop.hyprland_version = "0.57.0"
        with self.assertRaisesRegex(RuntimeError, "allow-untested"):
            self.instance.install()
        self.assertFalse(self.instance.state_dir.exists())
        self.desktop.hyprland_version = "0.56.2"
        self.desktop.omarchy_version = "5.0.0"
        with self.assertRaisesRegex(RuntimeError, "allow-untested"):
            self.instance.install()

    def test_existing_border_plugin_skips_borders_only(self):
        self.desktop.plugins = [{"name": "borders-plus-plus"}]
        self.instance.install()
        self.assertFalse(self.instance.borders)
        self.assertTrue(self.instance.focus)
        self.assertTrue(self.instance.state["enabled"])

    def test_custom_bar_kept_without_a_replacement_prompt(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["id"] = "custom.bar"
        installer.write_json(self.instance.shell, config)
        self.instance.confirm = lambda message: self.fail("The installer must not ask to replace the bar")
        self.instance.install()
        self.assertEqual(self.desktop.config()["bar"]["id"], "custom.bar")
        self.assertNotIn("turbo-pascal.bar", self.instance.state["enabled"])
        self.assertIn("turbo-pascal.power", self.instance.state["enabled"])

    def test_install_keeps_stock_bar_and_third_party_service_widgets(self):
        for explicit_bar in (False, True):
            with self.subTest(explicit_bar=explicit_bar):
                config = copy.deepcopy(DEFAULT)
                if explicit_bar:
                    config["bar"]["id"] = "omarchy.bar"
                third_party = [
                    {"id": "lgse.sandman", "option": "keep"},
                    {"id": "io.github.twiking.omasettings"},
                ]
                config["bar"]["layout"]["right"].extend(third_party)
                config["plugins"].extend(copy.deepcopy(third_party))
                installer.write_json(self.instance.shell, config)
                self.instance.install()
                result = self.desktop.config()
                self.assertEqual(result["bar"].get("id"), config["bar"].get("id"))
                self.assertEqual(result["bar"]["layout"]["right"][-2:], third_party)
                self.assertEqual(result["plugins"], config["plugins"])
                self.assertNotIn("turbo-pascal.bar", self.instance.state["enabled"])
                self.assertFalse(any(call[:3] in (
                    ("omarchy", "plugin", "enable"), ("omarchy", "plugin", "disable"))
                    and call[3].endswith(".bar") for call in self.desktop.calls))
                library = self.instance.config / "plugins/turbo-pascal.bar"
                self.assertEqual([path.name for path in library.iterdir()], ["DosUi"])
                self.assertEqual(installer.fingerprint(library / "DosUi"),
                                 installer.fingerprint(ROOT / "extras/plugins/turbo-pascal.bar/DosUi"))
                self.instance.uninstall()
                self.assertEqual(self.desktop.config(), config)
                self.assertFalse(library.exists())
                self.desktop.calls.clear()

    def test_active_custom_widget_clone_kept_without_permission(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["layout"]["right"][0]["id"] = "custom.power"
        installer.write_json(self.instance.shell, config)
        installer.write_json(self.instance.config / "plugins/custom.power/manifest.json", {
            "id": "custom.power", "omarchy": {"clonedFrom": "omarchy.power"},
        })
        self.instance.confirm = lambda message: False
        self.instance.install()
        self.assertEqual(self.desktop.config()["bar"]["layout"]["right"][0]["id"], "custom.power")
        self.assertNotIn("turbo-pascal.power", self.instance.state["enabled"])

    def test_symlinked_target_refused(self):
        target = self.instance.config / "plugins/turbo-pascal.power"
        target.parent.mkdir(parents=True)
        other = self.home / "do-not-overwrite"
        other.mkdir()
        target.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.instance.install()
        self.assertTrue(target.is_symlink())

    def test_enable_failure_keeps_native_effects_and_restores_widget_settings(self):
        self.desktop.fail_enable = True
        self.instance.install()
        self.assertEqual(installer.read_json(self.instance.shell), DEFAULT)
        self.assertTrue(self.instance.data.exists())
        self.assertTrue(self.instance.theme.exists())
        self.assertEqual(self.instance.state["status"], "installed")
        self.assertEqual(self.instance.state["enabled"], [])

    def test_build_failure_skips_borders_not_other_extras(self):
        self.desktop.fail_build = True
        self.instance.install()
        self.assertTrue(self.instance.data.exists())
        self.assertFalse(self.instance.borders)
        self.assertTrue(self.instance.state["enabled"])

    def test_local_plugin_edits_block_uninstall_without_removing_anything(self):
        self.instance.install()
        target = self.instance.config / "plugins/turbo-pascal.power/Panel.qml"
        target.write_text(target.read_text() + "\n// Local customization\n")
        with self.assertRaisesRegex(RuntimeError, "Local edits detected"):
            self.instance.uninstall()
        self.assertTrue(self.instance.data.exists())
        self.assertTrue(target.is_file())
        self.assertEqual((self.instance.current / "theme.name").read_text(), "turbo-pascal")

    def test_runtime_build_artifacts_do_not_block_uninstall(self):
        self.instance.install()
        (self.instance.data / "plugin-session").write_text("new-session")
        for name in ("build-hash", "runtime-status.json", "client-hash"):
            (self.instance.data / name).write_text("generated artifact")
        (self.instance.data / "hyprland-plugins/borders-plus-plus/borders-plus-plus.so").write_bytes(
            b"rebuilt binary")
        self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())

    def test_custom_widget_restores_after_layout_edits_and_interrupted_restore(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["layout"]["right"][0]["id"] = "custom.power"
        installer.write_json(self.instance.shell, config)
        installer.write_json(self.instance.config / "plugins/custom.power/manifest.json",
                             {"id": "custom.power", "omarchy": {"clonedFrom": "omarchy.power"}})
        self.instance.confirm = lambda message: True
        self.instance.install()
        config = self.desktop.config()
        config["idle"]["lock"] = 999
        installer.write_json(self.instance.shell, config)
        original = self.desktop.run

        def fail_restore(*args, **kwargs):
            if args == ("omarchy", "plugin", "enable", "custom.power"):
                raise subprocess.CalledProcessError(1, args)
            return original(*args, **kwargs)

        with patch.object(installer, "run", fail_restore):
            with self.assertRaises(subprocess.CalledProcessError):
                self.instance.uninstall()
        self.instance.uninstall()
        result = self.desktop.config()
        self.assertEqual(result["idle"]["lock"], 999)
        self.assertEqual(result["bar"]["layout"]["right"][0]["id"], "custom.power")
        self.assertEqual(result["bar"]["centerAnchor"], "omarchy.clock")
        self.assertNotIn("id", result["bar"])

    def test_rollback_unload_failure_restores_independent_files_then_retries(self):
        original_shell = self.instance.shell.read_bytes()
        original = self.desktop.run

        def fail_hooks_and_unload(*args, **kwargs):
            if args[:3] == ("omarchy", "hook", "install") or (
                    args[0] == "bash" and args[-1] == "--unload"):
                raise subprocess.CalledProcessError(1, args)
            return original(*args, **kwargs)

        with patch.object(installer, "run", fail_hooks_and_unload):
            with self.assertRaisesRegex(RuntimeError, "retry ./uninstall.sh"):
                self.instance.install()
        self.assertEqual(self.instance.shell.read_bytes(), original_shell)
        self.assertFalse((self.instance.config / "plugins/turbo-pascal.power").exists())
        self.assertTrue(self.instance.data.exists())
        self.assertEqual(self.instance.state["status"], "rolling-back")
        self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())
        self.assertEqual(self.instance.state["status"], "rolled-back")

    def test_reinstall_archives_previous_backups(self):
        self.instance.install()
        self.instance.uninstall()
        self.instance.install()
        archives = list(self.instance.state_dir.parent.glob("turbo-pascal-install-backup-*"))
        self.assertEqual(len(archives), 1)
        self.assertTrue((archives[0] / "state.json").is_file())

    def test_package_manifests_and_relative_imports(self):
        for module in installer.MODULES:
            path = ROOT / "extras/plugins" / f"turbo-pascal.{module}"
            manifest = installer.read_json(path / "manifest.json")
            self.assertEqual(manifest["id"], path.name)
            self.assertEqual(manifest["omarchy"]["clonedFrom"], f"omarchy.{module}")
            for entry in manifest["entryPoints"].values():
                self.assertTrue((path / entry).is_file())
            for qml in path.rglob("*.qml"):
                text = qml.read_text()
                self.assertNotIn("ric.bar/DosUi", text)
                if 'import "../turbo-pascal.bar/DosUi" as DosUi' in text:
                    self.assertTrue((path / "../turbo-pascal.bar/DosUi").is_dir())
        self.assertFalse(list(ROOT.rglob("*.so")))

    def test_missing_base_theme_instructs_standard_install(self):
        (self.instance.theme / "colors.toml").unlink()
        with self.assertRaisesRegex(RuntimeError, "omarchy theme install"):
            self.instance.install()
        self.assertFalse(self.instance.state_dir.exists())

    def test_extension_does_not_modify_or_remove_base_clone(self):
        (self.instance.theme / ".git").mkdir()
        (self.instance.theme / ".git/config").write_text("base clone sentinel")
        before = installer.fingerprint(self.instance.theme)
        self.instance.install()
        self.assertEqual(installer.fingerprint(self.instance.theme), before)
        self.instance.uninstall()
        self.assertEqual(installer.fingerprint(self.instance.theme), before)

    def test_already_active_base_is_not_reapplied_during_install(self):
        (self.instance.current / "theme.name").write_text("turbo-pascal")
        self.instance.install()
        self.assertFalse(any(call[:3] == ("omarchy", "theme", "set")
                             for call in self.desktop.calls))

    def test_uninstall_can_retry_after_restart_failure(self):
        self.instance.install()
        original = self.desktop.run

        def fail_restart(*args, **kwargs):
            if args == ("omarchy", "restart", "shell"):
                raise subprocess.CalledProcessError(1, args)
            return original(*args, **kwargs)

        with patch.object(installer, "run", fail_restart):
            with self.assertRaises(subprocess.CalledProcessError):
                self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())
        self.assertTrue(self.instance.theme.exists())
        self.assertEqual(self.instance.state["status"], "uninstalling")
        theme_calls = sum(call[:3] == ("omarchy", "theme", "set")
                          for call in self.desktop.calls)
        config = installer.read_json(self.instance.shell)
        config["idle"]["lock"] = 999
        installer.write_json(self.instance.shell, config)
        self.instance.uninstall()
        self.assertEqual(installer.read_json(self.instance.shell)["idle"]["lock"], 999)
        self.assertEqual(self.instance.state["status"], "uninstalled")
        self.assertEqual(sum(call[:3] == ("omarchy", "theme", "set")
                             for call in self.desktop.calls), theme_calls)

    def test_uninstall_can_retry_after_theme_refresh_failure(self):
        self.instance.install()
        original = self.desktop.run

        def fail_refresh(*args, **kwargs):
            if args[:3] == ("omarchy", "theme", "set"):
                raise subprocess.CalledProcessError(1, args)
            return original(*args, **kwargs)

        with patch.object(installer, "run", fail_refresh):
            with self.assertRaises(subprocess.CalledProcessError):
                self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())
        self.instance.uninstall()
        self.assertEqual(self.instance.state["status"], "uninstalled")
        self.assertTrue(self.instance.theme.exists())

    def test_unload_failure_keeps_files_and_allows_retry(self):
        self.instance.install()
        original = self.desktop.run

        def fail_unload(*args, **kwargs):
            if args[0] == "bash" and args[-1] == "--unload":
                raise subprocess.CalledProcessError(1, args)
            return original(*args, **kwargs)

        with patch.object(installer, "run", fail_unload):
            with self.assertRaises(subprocess.CalledProcessError):
                self.instance.uninstall()
        self.assertTrue(self.instance.data.exists())
        self.assertTrue((self.instance.config / "plugins/turbo-pascal.power").exists())
        self.instance.uninstall()
        self.assertEqual(self.instance.state["status"], "uninstalled")

    def test_legacy_uninstall_keeps_previous_theme_behavior(self):
        self.instance.install()
        self.instance.state["version"] = 1
        self.instance.save()
        self.instance.uninstall()
        self.assertEqual((self.instance.current / "theme.name").read_text(), "tokyo-night")

    def test_allow_untested_is_explicit_and_selects_matching_source(self):
        self.desktop.hyprland_version = "0.57.0"
        self.instance.allow_untested = True
        self.instance.install()
        self.assertEqual(self.instance.state["border_source"]["tag"], "v0.57.0")

    def test_missing_compiler_does_not_block_focus_or_widgets(self):
        with patch.object(installer.shutil, "which",
                          side_effect=lambda name: None if name == "g++" else "/bin/fixture"):
            self.instance.install()
        self.assertFalse(self.instance.borders)
        self.assertTrue(self.instance.focus)
        self.assertTrue(self.instance.state["enabled"])

    def test_native_only_install_and_uninstall_needs_no_shell(self):
        self.instance.skip_widgets = True
        self.instance.skip_borders = True
        self.instance.install()
        self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())
        self.assertFalse(any(call[:3] == ("omarchy", "restart", "shell")
                             for call in self.desktop.calls))

    def test_custom_widget_replacement_is_prompted_and_preserves_files(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["layout"]["right"][0]["id"] = "custom.power"
        installer.write_json(self.instance.shell, config)
        path = self.instance.config / "plugins/custom.power/manifest.json"
        installer.write_json(path, {"id": "custom.power",
                                   "omarchy": {"clonedFrom": "omarchy.power"}})
        original = self.instance.shell.read_bytes()
        prompts = []
        self.instance.confirm = lambda message: prompts.append(message) or True
        self.instance.install()
        self.assertTrue(any("custom.power" in message for message in prompts))
        self.assertTrue(path.exists())
        self.instance.uninstall()
        self.assertEqual(self.instance.shell.read_bytes(), original)

    def test_custom_bar_is_kept_even_when_widget_replacements_are_allowed(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["id"] = "custom.bar"
        installer.write_json(self.instance.shell, config)
        self.instance.confirm = lambda message: True
        self.instance.install()
        self.assertEqual(self.desktop.config()["bar"]["id"], "custom.bar")
        self.assertNotIn("bar", self.instance.modules)
        self.assertNotIn(("omarchy", "plugin", "disable", "custom.bar"), self.desktop.calls)
        self.instance.uninstall()
        self.assertEqual(self.desktop.config()["bar"]["id"], "custom.bar")

    def test_legacy_replacement_bar_is_restored_by_updated_uninstaller(self):
        self.instance.install()
        library = self.instance.config / "plugins/turbo-pascal.bar"
        shutil.copy2(ROOT / "extras/plugins/turbo-pascal.bar/manifest.json", library)
        shutil.copy2(ROOT / "extras/plugins/turbo-pascal.bar/Bar.qml", library)
        record = next(record for record in self.instance.state["records"]
                      if record["path"].endswith("plugins/turbo-pascal.bar"))
        self.instance.finish_record(record)
        self.instance.state["enabled"].append("turbo-pascal.bar")
        self.instance.state["replacements"]["turbo-pascal.bar"] = []
        config = self.desktop.config()
        config["bar"]["id"] = "turbo-pascal.bar"
        installer.write_json(self.instance.shell, config)
        shell_record = next(record for record in self.instance.state["records"]
                            if record["path"].endswith("shell.json"))
        self.instance.finish_record(shell_record)
        config["idle"]["lock"] = 999
        installer.write_json(self.instance.shell, config)
        self.instance.uninstall()
        self.assertEqual(self.desktop.config()["bar"]["id"], "omarchy.bar")
        self.assertEqual(self.desktop.config()["idle"]["lock"], 999)
        self.assertFalse(library.exists())

    def test_hidden_menu_gets_styling_without_adding_an_icon(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["layout"]["left"].pop(0)
        installer.write_json(self.instance.shell, config)
        self.instance.install()
        result = self.desktop.config()
        self.assertIn("turbo-pascal.menu", installer.active_ids(result))
        self.assertNotIn("turbo-pascal.menu", installer.layout_ids(result))
        result["idle"]["lock"] = 999
        installer.write_json(self.instance.shell, result)
        self.instance.uninstall()
        result = self.desktop.config()
        self.assertEqual(result["idle"]["lock"], 999)
        self.assertEqual(result["plugins"], DEFAULT["plugins"])
        self.assertNotIn("omarchy.menu", installer.layout_ids(result))

    def test_no_op_theme_activation_is_not_reported_as_success(self):
        original = self.desktop.run

        def no_op_activation(*args, **kwargs):
            if args[:3] == ("omarchy", "theme", "set"):
                return ""
            return original(*args, **kwargs)

        with patch.object(installer, "run", no_op_activation):
            with self.assertRaisesRegex(RuntimeError, "did not activate"):
                self.instance.install()
        self.assertFalse(self.instance.data.exists())
        self.assertEqual(self.desktop.config(), DEFAULT)
        self.assertTrue(self.instance.theme.exists())

    def test_keyboard_interrupt_rolls_back_partial_runtime(self):
        original = self.desktop.run

        def interrupt(*args, **kwargs):
            if args[:2] == ("git", "clone"):
                raise KeyboardInterrupt()
            return original(*args, **kwargs)

        with patch.object(installer, "run", interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.instance.install()
        self.assertFalse(self.instance.data.exists())
        self.assertTrue(self.instance.theme.exists())
        self.assertEqual(self.instance.state["status"], "rolled-back")


if __name__ == "__main__":
    unittest.main()
