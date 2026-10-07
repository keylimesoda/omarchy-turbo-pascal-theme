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
        if args[:3] == ("omarchy", "plugin", "enable"):
            if self.fail_enable:
                raise subprocess.CalledProcessError(1, args)
            config = self.instance.effective_config()
            name = args[3]
            source = "omarchy." + name.split(".", 1)[1]
            if name == "turbo-pascal.bar":
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
            config = self.instance.effective_config()
            name = args[3]
            source = "omarchy." + name.split(".", 1)[1]
            if config["bar"].get("id") == name:
                del config["bar"]["id"]
            for entries in config["bar"]["layout"].values():
                for entry in entries:
                    if entry["id"] == name:
                        entry["id"] = source
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
        self.assertEqual(config["bar"]["centerAnchor"], "omarchy.clock")
        self.assertEqual(config["bar"]["layout"]["center"],
                         [{"id": "turbo-pascal.clock", "format": "HH:mm"}])
        self.assertEqual(config["bar"]["layout"]["right"][1],
                         {"id": "custom.example", "option": 42})
        self.assertNotIn("turbo-pascal.audio", installer.layout_ids(config))
        self.assertEqual(self.instance.state["status"], "installed")
        for event in ("theme-set", "post-boot"):
            self.assertTrue((self.instance.config / "hooks" /
                            f"{event}.d/turbo-pascal-borders").is_file())

    def test_uninstall_restores_exact_original_files(self):
        original = self.instance.shell.read_bytes()
        self.instance.install()
        self.instance.uninstall()
        self.assertEqual(self.instance.shell.read_bytes(), original)
        self.assertFalse(self.instance.theme.exists())
        self.assertFalse(self.instance.data.exists())
        self.assertEqual((self.instance.current / "theme.name").read_text(), "tokyo-night")
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

    def test_existing_theme_is_backed_up_and_restored(self):
        self.instance.theme.mkdir(parents=True)
        (self.instance.theme / "colors.toml").write_text("original palette")
        (self.instance.theme / "personal.txt").write_text("keep")
        self.instance.install()
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
        with self.assertRaisesRegex(RuntimeError, "matching headers"):
            self.instance.install()
        self.assertFalse(self.instance.state_dir.exists())
        self.desktop.hyprland_version = "0.56.2"
        self.desktop.omarchy_version = "4.1.0"
        with self.assertRaisesRegex(RuntimeError, "Supported Omarchy"):
            self.instance.install()

    def test_existing_border_plugin_refused(self):
        self.desktop.plugins = [{"name": "borders-plus-plus"}]
        with self.assertRaisesRegex(RuntimeError, "already loaded"):
            self.instance.install()
        self.assertFalse(self.instance.state_dir.exists())

    def test_custom_bar_refused(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["id"] = "custom.bar"
        installer.write_json(self.instance.shell, config)
        with self.assertRaisesRegex(RuntimeError, "custom bar"):
            self.instance.install()

    def test_active_custom_widget_clone_refused(self):
        config = copy.deepcopy(DEFAULT)
        config["bar"]["layout"]["right"][0]["id"] = "custom.power"
        installer.write_json(self.instance.shell, config)
        installer.write_json(self.instance.config / "plugins/custom.power/manifest.json", {
            "id": "custom.power", "omarchy": {"clonedFrom": "omarchy.power"},
        })
        with self.assertRaisesRegex(RuntimeError, "custom clone"):
            self.instance.install()

    def test_symlinked_target_refused(self):
        self.instance.theme.parent.mkdir(parents=True)
        other = self.home / "do-not-overwrite"
        other.mkdir()
        self.instance.theme.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.instance.install()
        self.assertTrue(self.instance.theme.is_symlink())

    def test_enable_failure_rolls_back(self):
        self.desktop.fail_enable = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.instance.install()
        self.assertEqual(installer.read_json(self.instance.shell), DEFAULT)
        self.assertFalse(self.instance.data.exists())
        self.assertFalse(self.instance.theme.exists())
        self.assertEqual(self.instance.state["status"], "rolled-back")

    def test_build_failure_rolls_back(self):
        self.desktop.fail_build = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.instance.install()
        self.assertFalse(self.instance.data.exists())
        self.assertEqual(installer.read_json(self.instance.shell), DEFAULT)

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
        (self.instance.data / "hyprland-plugins/borders-plus-plus/borders-plus-plus.so").write_bytes(
            b"rebuilt binary")
        self.instance.uninstall()
        self.assertFalse(self.instance.data.exists())

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


if __name__ == "__main__":
    unittest.main()
