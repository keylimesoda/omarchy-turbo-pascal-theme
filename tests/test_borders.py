import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("jq"), "Runtime hook tests need jq")
class BorderHookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.data = self.home / ".local/share/omarchy-turbo-pascal"
        self.data.mkdir(parents=True)
        (self.data / "hyprland.lua").write_text("-- authorized border Lua\n")
        self.current = self.home / ".local/state/omarchy/current"
        (self.current / "theme").mkdir(parents=True)
        (self.current / "theme.name").write_text("turbo-pascal")
        self.loaded = self.home / "loaded.json"
        self.loaded.write_text("[]")
        self.log = self.home / "commands.log"
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.command("hyprctl", r'''
printf 'hyprctl %s\n' "$*" >> "$FAKE_LOG"
case "$1 ${2:-}" in
  "version -j") printf '{"version":"%s"}\n' "$FAKE_VERSION" ;;
  "plugins list") cat "$FAKE_LOADED" ;;
  "plugin load") printf '[{"name":"borders-plus-plus"}]' > "$FAKE_LOADED" ;;
  "plugin unload") printf '[]' > "$FAKE_LOADED" ;;
  *) ;;
esac
''')
        self.command("pkg-config", 'printf "%s\\n" "$FAKE_HEADERS"')
        self.command("make", 'printf "make\\n" >> "$FAKE_LOG"')
        self.command("omarchy-notification-send", 'printf "notification\\n" >> "$FAKE_LOG"')
        self.env = {
            **os.environ, "HOME": str(self.home),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HYPRLAND_INSTANCE_SIGNATURE": "fixture-session",
            "FAKE_VERSION": "0.56.2", "FAKE_HEADERS": "0.56.2",
            "FAKE_LOADED": str(self.loaded), "FAKE_LOG": str(self.log),
        }

    def tearDown(self):
        self.directory.cleanup()

    def command(self, name, text):
        path = self.bin / name
        path.write_text("#!/bin/bash\nset -eu\n" + text)
        path.chmod(0o755)

    def invoke(self, *args):
        return subprocess.run(
            ["bash", str(ROOT / "extras/borders/apply-borders"), *args],
            env=self.env, text=True, capture_output=True,
        )

    def commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def set_loaded(self, own=False):
        self.loaded.write_text(json.dumps([{"name": "borders-plus-plus"}]))
        if own:
            (self.data / "plugin-session").write_text("fixture-session\n")

    def test_activation_builds_loads_and_authorizes_lua(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.current / "theme/hyprland.lua").read_text(),
                         "-- authorized border Lua\n")
        self.assertIn("make\n", self.commands())
        self.assertIn("hyprctl plugin load", self.commands())
        self.assertIn("hyprctl reload", self.commands())
        self.assertEqual((self.data / "plugin-session").read_text(), "fixture-session\n")

    def test_owned_loaded_plugin_is_not_rebuilt(self):
        self.set_loaded(own=True)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("make\n", self.commands())
        self.assertNotIn("plugin load", self.commands())

    def test_theme_switch_unloads_owned_plugin_only(self):
        self.set_loaded(own=True)
        (self.current / "theme.name").write_text("catppuccin")
        result = self.invoke("catppuccin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plugin unload", self.commands())
        self.assertFalse((self.data / "plugin-session").exists())
        self.assertFalse((self.current / "theme/hyprland.lua").exists())

    def test_other_theme_does_not_unload_someone_elses_plugin(self):
        self.set_loaded()
        (self.current / "theme.name").write_text("catppuccin")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("plugin unload", self.commands())

    def test_foreign_loaded_plugin_rejected(self):
        self.set_loaded()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to replace", result.stderr)
        self.assertNotIn("plugin load", self.commands())
        self.assertFalse((self.current / "theme/hyprland.lua").exists())

    def test_previous_session_marker_does_not_claim_foreign_plugin(self):
        self.set_loaded()
        (self.data / "plugin-session").write_text("old-session\n")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("plugin unload", self.commands())

    def test_unsupported_upgrade_reports_error_without_loading(self):
        self.env["FAKE_VERSION"] = "0.57.0"
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Supported Hyprland", result.stderr)
        self.assertIn("notification", self.commands())
        self.assertNotIn("plugin load", self.commands())

    def test_headers_must_match_compositor(self):
        self.env["FAKE_HEADERS"] = "0.56.1"
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.current / "theme/hyprland.lua").exists())

    def test_build_only_does_not_load_or_write_generated_theme(self):
        result = self.invoke("--build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("make\n", self.commands())
        self.assertNotIn("plugin load", self.commands())
        self.assertFalse((self.current / "theme/hyprland.lua").exists())

    def test_explicit_unload_works_after_upgrade(self):
        self.set_loaded(own=True)
        self.env["FAKE_VERSION"] = "0.57.0"
        result = self.invoke("--unload")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plugin unload", self.commands())


if __name__ == "__main__":
    unittest.main()
