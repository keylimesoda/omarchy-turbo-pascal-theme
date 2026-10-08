import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
BASE = "-- generated base theme stays\n"


class BorderHookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.data = self.home / ".local/share/omarchy-turbo-pascal"
        self.data.mkdir(parents=True)
        for name in ("runtime.py", "focus.conf", "client-hash.cpp"):
            shutil.copy2(ROOT / "extras/borders" / name, self.data)
        shutil.copy2(ROOT / "extras/gtk/gtk.py", self.data)
        shutil.copy2(ROOT / "hyprland.lua", self.data)
        self.features()
        self.current = self.home / ".local/state/omarchy/current"
        (self.current / "theme").mkdir(parents=True)
        (self.current / "theme.name").write_text("turbo-pascal")
        self.native = self.current / "theme/hyprland.lua"
        self.native.write_text(BASE)
        self.loaded = self.home / "loaded.json"
        self.loaded.write_text("[]")
        self.log = self.home / "commands.log"
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.gtk_value = self.home / "gtk-value"
        self.gtk_value.write_text("'Adwaita-dark'")
        self.command("gsettings", r'''
printf 'gsettings %s\n' "$*" >> "$FAKE_LOG"
if [ "$1" = get ]; then
  cat "$FAKE_GTK"
elif [ "${FAKE_GTK_ERROR:-0}" != 1 ]; then
  printf '%s' "$4" > "$FAKE_GTK"
fi
''')
        self.command("hyprctl", r'''
printf 'hyprctl %s\n' "$*" >> "$FAKE_LOG"
case "$1 ${2:-}" in
  "version -j")
    printf '{"version":"%s","commit":"%s","abiHash":"%s"}\n' "$FAKE_VERSION" "$FAKE_COMMIT" "$FAKE_ABI" ;;
  "plugins list") cat "$FAKE_LOADED" ;;
  "plugin load")
    if [ "${FAKE_LOAD_ERROR:-0}" = 1 ]; then
      printf 'error: failed to load plugin\n'
    else
      printf '[{"name":"borders-plus-plus"}]' > "$FAKE_LOADED"
    fi ;;
  "plugin unload")
    if [ "${FAKE_UNLOAD_ERROR:-0}" = 1 ]; then
      printf 'error: failed to unload plugin\n'
    else
      printf '[]' > "$FAKE_LOADED"
    fi ;;
  "configerrors ")
    if [ "${FAKE_PARSE_ERROR:-}" = border ] && grep -q active_only "$FAKE_NATIVE"; then
      printf 'unknown plugin setting\n'
    elif [ "${FAKE_PARSE_ERROR:-}" = focus ] && grep -q dim_inactive "$FAKE_NATIVE"; then
      printf 'unsupported focus setting\n'
    fi ;;
  "reload ") printf 'ok\n' ;;
esac
''')
        self.command("pkg-config", r'''
if [ "$1" = --modversion ]; then printf '%s\n' "$FAKE_DEPS"; fi
''')
        self.command("g++", r'''
while [ "$1" != -o ]; do shift; done
shift
printf '#!/bin/bash\nprintf "%%s\\n" "$FAKE_HEADERS"\n' > "$1"
chmod +x "$1"
''')
        self.command("make", r'''
printf 'make\n' >> "$FAKE_LOG"
mkdir -p "$FAKE_PLUGIN_DIR"
printf 'fixture binary\n' > "$FAKE_PLUGIN_DIR/borders-plus-plus.so"
''')
        self.command("omarchy-notification-send", 'printf "notification\\n" >> "$FAKE_LOG"')
        self.env = {
            **os.environ, "HOME": str(self.home),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HYPRLAND_INSTANCE_SIGNATURE": "fixture-session",
            "FAKE_VERSION": "0.56.2", "FAKE_COMMIT": "fixture",
            "FAKE_ABI": "fixture_aq_0.15_hu_0.14_hg_0.5_hc_0.1_hlg_0.6",
            "FAKE_HEADERS": "fixture_aq_0.15_hu_0.14_hg_0.5_hc_0.1_hlg_0.6",
            "FAKE_DEPS": "0.15.0\n0.14.1\n0.5.1\n0.1.13\n0.6.8",
            "FAKE_LOADED": str(self.loaded), "FAKE_LOG": str(self.log),
            "FAKE_NATIVE": str(self.native),
            "FAKE_PLUGIN_DIR": str(self.data / "hyprland-plugins/borders-plus-plus"),
            "FAKE_GTK": str(self.gtk_value),
        }

    def tearDown(self):
        self.directory.cleanup()

    def features(self, focus=True, borders=True, gtk=False):
        (self.data / "features.json").write_text(json.dumps({
            "focus": focus, "borders": borders, "gtk": gtk}))
        if gtk:
            path = self.home / ".local/share/themes/omarchy-turbo-pascal/gtk-3.0"
            path.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "extras/gtk/gtk.css", path)

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

    def status(self):
        return json.loads((self.data / "runtime-status.json").read_text())

    def set_loaded(self, own=False):
        self.loaded.write_text(json.dumps([{"name": "borders-plus-plus"}]))
        if own:
            (self.data / "plugin-session").write_text("fixture-session\n")

    def test_activation_preserves_base_and_applies_independent_effects(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        native = self.native.read_text()
        self.assertTrue(native.startswith(BASE))
        self.assertIn('opacity = "0.97 override"', native)
        self.assertIn('focus = false, fullscreen = false', native)
        self.assertNotIn("inactive_opacity", native)
        self.assertIn("active_only = true", native)
        self.assertEqual(self.status()["active"], ["focus effects", "double borders"])
        self.assertIn("make\n", self.commands())
        self.assertIn("hyprctl plugin load", self.commands())
        self.assertEqual((self.data / "plugin-session").read_text(), "fixture-session\n")

    def test_repeated_overlay_is_idempotent_and_does_not_rebuild(self):
        self.assertEqual(self.invoke().returncode, 0)
        first = self.native.read_text()
        self.log.write_text("")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.native.read_text(), first)
        self.assertEqual(first.count("BEGIN TURBO PASCAL EXTRAS"), 1)
        self.assertNotIn("make\n", self.commands())
        self.assertNotIn("plugin load", self.commands())

    def test_theme_switch_removes_overlay_and_unloads_owned_plugin_only(self):
        self.assertEqual(self.invoke().returncode, 0)
        (self.current / "theme.name").write_text("catppuccin")
        result = self.invoke("catppuccin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.native.read_text(), BASE)
        self.assertIn("plugin unload", self.commands())
        self.assertFalse((self.data / "plugin-session").exists())

    def test_other_theme_does_not_unload_someone_elses_plugin(self):
        self.set_loaded()
        (self.current / "theme.name").write_text("catppuccin")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("plugin unload", self.commands())
        self.assertEqual(self.native.read_text(), BASE)

    def test_foreign_loaded_plugin_skipped_but_focus_still_applied(self):
        self.set_loaded()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preserving it", result.stderr)
        self.assertNotIn("plugin load", self.commands())
        self.assertNotIn("plugin unload", self.commands())
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertNotIn("active_only", self.native.read_text())

    def test_previous_session_marker_does_not_claim_foreign_plugin(self):
        self.set_loaded()
        (self.data / "plugin-session").write_text("old-session\n")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertNotIn("plugin unload", self.commands())
        self.assertTrue(self.status()["skipped"])

    def test_commit_mismatch_skips_borders_not_focus(self):
        self.env["FAKE_HEADERS"] = "different_dependencies"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("compositor commit", result.stderr)
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertNotIn("plugin load", self.commands())

    def test_dependency_abi_mismatch_is_not_bypassed(self):
        self.env["FAKE_HEADERS"] = "fixture_different"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("compositor ABI", result.stderr)
        self.assertNotIn("plugin load", self.commands())

    def test_updated_dependencies_cannot_hide_behind_matching_hyprland_headers(self):
        self.env["FAKE_DEPS"] = "0.16.0\n0.14.1\n0.5.1\n0.1.13\n0.6.8"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Installed dependency versions", result.stderr)
        self.assertNotIn("plugin load", self.commands())

    def test_build_only_does_not_load_or_change_generated_theme(self):
        result = self.invoke("--build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("make\n", self.commands())
        self.assertNotIn("plugin load", self.commands())
        self.assertEqual(self.native.read_text(), BASE)

    def test_explicit_unload_works_after_upgrade(self):
        self.set_loaded(own=True)
        self.env["FAKE_VERSION"] = "0.57.0"
        result = self.invoke("--unload")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plugin unload", self.commands())

    def test_zero_exit_textual_load_error_is_reported(self):
        self.env["FAKE_LOAD_ERROR"] = "1"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("failed to load plugin", result.stderr)
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertFalse((self.data / "plugin-session").exists())
        self.assertIn("notification", self.commands())

    def test_zero_exit_textual_unload_error_retains_ownership_for_retry(self):
        self.set_loaded(own=True)
        self.env["FAKE_UNLOAD_ERROR"] = "1"
        result = self.invoke("--unload")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not unload", result.stderr)
        self.assertTrue((self.data / "plugin-session").exists())

    def test_border_parser_failure_rolls_back_only_border_overlay(self):
        self.env["FAKE_PARSE_ERROR"] = "border"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertNotIn("active_only", self.native.read_text())
        self.assertEqual(json.loads(self.loaded.read_text()), [])

    def test_focus_parser_failure_does_not_block_borders(self):
        self.env["FAKE_PARSE_ERROR"] = "focus"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["active"], ["double borders"])
        self.assertNotIn("dim_inactive", self.native.read_text())

    def test_focus_without_plugin_requires_no_build_tools(self):
        self.features(borders=False)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertNotIn("make\n", self.commands())
        self.assertNotIn("plugins list", self.commands())

    def test_legacy_052_uses_v2_rule_and_preserves_native_base(self):
        self.features(borders=False)
        self.native.unlink()
        self.native = self.current / "theme/hyprland.conf"
        self.native.write_text("# generated base stays\n")
        self.env["FAKE_NATIVE"] = str(self.native)
        self.env["FAKE_VERSION"] = "0.52.2"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.native.read_text()
        self.assertTrue(content.startswith("# generated base stays\n"))
        self.assertIn("windowrulev2 = opacity 0.97 override,tag:default-opacity,focus:0,fullscreen:0", content)
        self.assertNotIn("windowrule {", content)

    def test_legacy_053_uses_named_rule(self):
        self.features(borders=False)
        self.native.unlink()
        self.native = self.current / "theme/hyprland.conf"
        self.native.write_text("# base\n")
        self.env["FAKE_NATIVE"] = str(self.native)
        self.env["FAKE_VERSION"] = "0.53.0"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("windowrule {", self.native.read_text())
        self.assertIn("match:focus = false", self.native.read_text())

    def test_missing_generated_theme_reports_skip(self):
        self.native.unlink()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No generated Hyprland theme", result.stderr)
        self.assertEqual(self.status()["active"], [])

    def test_gtk_only_activation_switching_and_reactivation(self):
        self.features(focus=False, borders=False, gtk=True)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["active"], ["GTK3 styling"])
        self.assertEqual(self.gtk_value.read_text(), "'omarchy-turbo-pascal'")
        self.assertNotIn("plugin load", self.commands())
        self.assertNotIn("color-scheme", self.commands())
        (self.current / "theme.name").write_text("haven")
        self.gtk_value.write_text("'Adwaita'")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.gtk_value.read_text(), "'Adwaita'")
        (self.current / "theme.name").write_text("turbo-pascal")
        self.gtk_value.write_text("'Adwaita-dark'")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.gtk_value.read_text(), "'omarchy-turbo-pascal'")
        self.assertEqual(self.invoke("--unload").returncode, 0)
        self.assertEqual(self.gtk_value.read_text(), "'Adwaita-dark'")

    def test_gtk_setting_failure_keeps_focus_effects_and_reports_skip(self):
        self.features(borders=False, gtk=True)
        self.env["FAKE_GTK_ERROR"] = "1"
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["active"], ["focus effects"])
        self.assertIn("GTK theme selection did not take effect", result.stderr)
        self.assertEqual(self.gtk_value.read_text(), "'Adwaita-dark'")

    def test_failed_gtk_restore_still_removes_native_effects(self):
        self.features(gtk=True)
        self.assertEqual(self.invoke().returncode, 0)
        self.env["FAKE_GTK_ERROR"] = "1"
        result = self.invoke("--unload")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GTK theme selection did not take effect", result.stderr)
        self.assertNotIn("BEGIN TURBO PASCAL", (self.current / "theme/hyprland.lua").read_text())
        self.assertIn("plugin unload", self.commands())
        self.assertTrue((self.data / "gtk-previous.json").exists())


if __name__ == "__main__":
    unittest.main()
