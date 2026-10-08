import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gtk", ROOT / "extras/gtk/gtk.py")
gtk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtk)


class Gtk4ThemeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.data = self.home / ".local/share/omarchy-turbo-pascal"
        self.data.mkdir(parents=True)
        (self.data / "gtk4.css").write_text((ROOT / "extras/gtk/gtk4.css").read_text())
        self.theme = gtk.Gtk4Theme(self.home)

    def tearDown(self):
        self.directory.cleanup()

    def styles(self, contents):
        self.theme.styles.parent.mkdir(parents=True, exist_ok=True)
        self.theme.styles.write_bytes(contents)

    def test_existing_css_restored_byte_for_byte_and_mode_preserved(self):
        original = b"/* user CSS */\r\nlabel { color: purple; }\r\n"
        self.styles(original)
        self.theme.styles.chmod(0o640)
        self.theme.apply()
        self.assertTrue(self.theme.styles.read_bytes().startswith(original))
        self.assertEqual(self.theme.styles.stat().st_mode & 0o777, 0o640)
        self.assertEqual(json.loads(self.theme.previous.read_text())["css"],
                         original.decode("utf-8"))
        self.theme.remove()
        self.assertEqual(self.theme.styles.read_bytes(), original)
        self.assertFalse(self.theme.previous.exists())

    def test_new_stylesheet_and_owned_empty_directory_removed(self):
        self.theme.apply()
        self.assertIn(self.theme.source.as_uri(), self.theme.styles.read_text())
        self.theme.remove()
        self.assertFalse(self.theme.styles.exists())
        self.assertFalse(self.theme.styles.parent.exists())

    def test_existing_empty_stylesheet_is_retained(self):
        self.styles(b"")
        self.theme.apply()
        self.theme.remove()
        self.assertTrue(self.theme.styles.is_file())
        self.assertEqual(self.theme.styles.read_bytes(), b"")

    def test_later_user_edits_survive_removal(self):
        self.styles(b"/* original */")
        self.theme.apply()
        self.theme.styles.write_text("/* later prefix */" + self.theme.styles.read_text()
                                     + "\nlabel { color: orange; }\n")
        self.theme.remove()
        self.assertEqual(self.theme.styles.read_text(),
                         "/* later prefix *//* original */\nlabel { color: orange; }\n")

    def test_later_edits_to_created_stylesheet_are_not_deleted(self):
        self.theme.apply()
        with self.theme.styles.open("a") as output:
            output.write("/* keep my new CSS */")
        self.theme.remove()
        self.assertEqual(self.theme.styles.read_text(), "/* keep my new CSS */")

    def test_repeated_activation_is_idempotent(self):
        self.theme.apply()
        original = self.theme.previous.read_bytes()
        self.theme.apply()
        self.assertEqual(self.theme.styles.read_text().count(self.theme.BEGIN), 1)
        self.assertEqual(self.theme.previous.read_bytes(), original)

    def test_switching_away_and_back_reestablishes_import(self):
        self.styles(b"/* personal */")
        self.theme.apply()
        self.theme.remove()
        self.theme.apply()
        self.theme.remove()
        self.assertEqual(self.theme.styles.read_bytes(), b"/* personal */")

    def test_unowned_import_is_not_adopted(self):
        self.styles(self.theme.block.encode())
        with self.assertRaisesRegex(RuntimeError, "unrecognized"):
            self.theme.apply()
        self.assertFalse(self.theme.previous.exists())

    def test_edited_owned_import_is_preserved_and_restore_can_retry(self):
        self.theme.apply()
        original = self.theme.styles.read_text()
        edited = original.replace("gtk4.css", "personal.css")
        self.theme.styles.write_text(edited)
        with self.assertRaisesRegex(RuntimeError, "edited"):
            self.theme.remove()
        self.assertEqual(self.theme.styles.read_text(), edited)
        self.assertTrue(self.theme.previous.exists())
        self.theme.styles.write_text(original)
        self.theme.remove()
        self.assertFalse(self.theme.previous.exists())

    def test_user_removed_import_is_preserved(self):
        self.theme.apply()
        self.theme.styles.write_text("/* replaced by user */")
        self.theme.remove()
        self.assertEqual(self.theme.styles.read_text(), "/* replaced by user */")

    def test_duplicate_import_is_reported(self):
        self.theme.apply()
        self.theme.styles.write_text(self.theme.styles.read_text() + self.theme.block)
        with self.assertRaisesRegex(RuntimeError, "edited"):
            self.theme.remove()
        self.assertTrue(self.theme.previous.exists())

    def test_symlinked_stylesheet_is_not_modified(self):
        target = self.home / "personal.css"
        target.write_text("/* keep */")
        self.theme.styles.parent.mkdir(parents=True)
        self.theme.styles.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            self.theme.apply()
        self.assertEqual(target.read_text(), "/* keep */")

    def test_symlinked_directory_is_not_followed(self):
        target = self.home / "styles"
        target.mkdir()
        self.theme.styles.parent.parent.mkdir()
        self.theme.styles.parent.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            self.theme.apply()
        self.assertEqual(list(target.iterdir()), [])

    def test_failed_atomic_write_preserves_original_css(self):
        self.styles(b"/* original */")
        with patch.object(gtk.os, "replace", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                self.theme.apply()
        self.assertEqual(self.theme.styles.read_bytes(), b"/* original */")
        self.assertEqual(list(self.theme.styles.parent.iterdir()), [self.theme.styles])
        self.theme.remove()
        self.assertFalse(self.theme.previous.exists())

    def test_missing_payload_does_not_modify_user_css(self):
        self.styles(b"/* original */")
        self.theme.source.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.theme.apply()
        self.assertEqual(self.theme.styles.read_bytes(), b"/* original */")
        self.assertFalse(self.theme.previous.exists())

    def test_paths_with_spaces_produce_an_encoded_import_uri(self):
        data = self.home / "theme files"
        data.mkdir()
        (data / "gtk4.css").write_bytes(self.theme.source.read_bytes())
        theme = gtk.Gtk4Theme(self.home, data)
        theme.apply()
        self.assertIn("theme%20files", theme.styles.read_text())
        theme.remove()

    def test_invalid_restoration_record_is_reported_without_editing_css(self):
        self.theme.apply()
        original = self.theme.styles.read_bytes()
        self.theme.previous.write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "Invalid GTK4 restoration record"):
            self.theme.remove()
        self.assertEqual(self.theme.styles.read_bytes(), original)
        with self.assertRaisesRegex(RuntimeError, "Invalid GTK4 restoration record"):
            self.theme.apply()


class GtkThemeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.theme = gtk.GtkTheme(self.home)
        self.theme.previous.parent.mkdir(parents=True)
        path = self.home / ".local/share/themes" / gtk.THEME / "gtk-3.0/gtk.css"
        path.parent.mkdir(parents=True)
        path.write_text((ROOT / "extras/gtk/gtk.css").read_text())
        self.selected = "'My original GTK theme'"
        self.calls = []
        self.runner = patch.object(gtk, "run", self.run_command)
        self.runner.start()

    def tearDown(self):
        self.runner.stop()
        self.directory.cleanup()

    def run_command(self, *args):
        self.calls.append(args)
        if args[:2] == ("gsettings", "get"):
            return self.selected
        if args[:2] == ("gsettings", "set"):
            self.selected = args[-1]
            return ""
        self.fail(f"Unexpected command: {args}")

    def test_selects_theme_and_restores_exact_previous_value(self):
        self.theme.apply()
        self.assertEqual(self.selected, repr(gtk.THEME))
        self.assertEqual(json.loads(self.theme.previous.read_text())["theme"],
                         "'My original GTK theme'")
        self.theme.remove()
        self.assertEqual(self.selected, "'My original GTK theme'")
        self.assertFalse(self.theme.previous.exists())

    def test_repeated_activation_does_not_lose_previous_theme(self):
        self.theme.apply()
        self.theme.apply()
        self.theme.remove()
        self.assertEqual(self.selected, "'My original GTK theme'")

    def test_switching_theme_does_not_overwrite_new_themes_gtk_selection(self):
        self.theme.apply()
        self.selected = "'Adwaita'"
        self.theme.remove()
        self.assertEqual(self.selected, "'Adwaita'")
        self.assertFalse(self.theme.previous.exists())

    def test_later_manual_gtk_selection_is_preserved(self):
        self.theme.apply()
        self.selected = "'Another custom theme'"
        self.theme.remove()
        self.assertEqual(self.selected, "'Another custom theme'")

    def test_missing_theme_does_not_change_settings(self):
        (self.home / ".local/share/themes" / gtk.THEME / "gtk-3.0/gtk.css").unlink()
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.theme.apply()
        self.assertEqual(self.selected, "'My original GTK theme'")

    def test_preexisting_selection_without_record_is_not_adopted(self):
        self.selected = repr(gtk.THEME)
        with self.assertRaisesRegex(RuntimeError, "restoration record"):
            self.theme.apply()
        self.assertFalse(self.theme.previous.exists())

    def test_failed_restoration_retains_record_for_retry(self):
        self.theme.apply()
        with patch.object(gtk, "run", side_effect=subprocess.CalledProcessError(1, "gsettings")):
            with self.assertRaises(subprocess.CalledProcessError):
                self.theme.remove()
        self.assertTrue(self.theme.previous.exists())
        self.theme.remove()
        self.assertEqual(self.selected, "'My original GTK theme'")

    def test_no_op_setting_write_is_reported(self):
        def no_op(*args):
            return self.selected if args[1] == "get" else ""
        with patch.object(gtk, "run", side_effect=no_op):
            with self.assertRaisesRegex(RuntimeError, "did not take effect"):
                self.theme.apply()

    def test_only_gtk_theme_setting_is_written_not_browser_or_system_mode(self):
        self.theme.apply()
        self.theme.remove()
        self.assertTrue(all(call[:4] in (
            ("gsettings", "get", gtk.SCHEMA, "gtk-theme"),
            ("gsettings", "set", gtk.SCHEMA, "gtk-theme")) for call in self.calls))


@unittest.skipUnless(importlib.util.find_spec("gi"), "Native GTK4 checks need PyGObject")
class Gtk4CssTests(unittest.TestCase):
    def test_native_gtk4_and_libadwaita_rendered_colors_through_user_import(self):
        libraries = subprocess.run(
            [sys.executable, "-c",
             "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')"],
            text=True, capture_output=True)
        if libraries.returncode:
            self.skipTest("Native GTK4 checks need GTK4 and libadwaita introspection")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            data = home / ".local/share/omarchy-turbo-pascal"
            data.mkdir(parents=True)
            css = data / "gtk4.css"
            css.write_bytes((ROOT / "extras/gtk/gtk4.css").read_bytes())
            helper = gtk.Gtk4Theme(home)
            helper.apply()
            env = {**os.environ, "XDG_CONFIG_HOME": str(home / ".config")}
            env.pop("GTK_THEME", None)
            for flags in ([], ["--adwaita"]):
                with self.subTest(toolkit="libadwaita" if flags else "GTK4"):
                    result = subprocess.run(
                        [sys.executable, "-B", str(ROOT / "tests/gtk4_probe.py"),
                         str(css), *flags], env=env, capture_output=True, text=True,
                        timeout=20)
                    if result.returncode == 77:
                        self.skipTest("Native GTK4 checks need GTK4 4.16+ and a display")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    colors = json.loads(result.stdout)
                    for widget, pixel in (
                            ("window", [170, 170, 170, 255]),
                            ("normal", [0, 136, 0, 255]),
                            ("destructive", [170, 0, 0, 255]),
                            ("entry", [0, 0, 170, 255]),
                            ("editor", [0, 0, 170, 255])):
                        self.assertEqual(colors[widget]["pixel"], pixel)
                        self.assertEqual(colors[widget]["foreground"],
                                         "rgb(0,0,0)" if widget == "window"
                                         else "rgb(255,255,255)")
            helper.remove()
            self.assertFalse(helper.styles.exists())


@unittest.skipUnless(importlib.util.find_spec("gi") and importlib.util.find_spec("cairo"),
                     "Native GTK checks need PyGObject and Pycairo")
class GtkCssTests(unittest.TestCase):
    def test_native_parser_and_control_colors(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GObject
        import cairo
        if not Gtk.init_check([])[0]:
            self.skipTest("Native GTK checks need a display")
        provider = Gtk.CssProvider()
        errors = []
        provider.connect("parsing-error",
                         lambda provider, section, error: errors.append(str(error)))
        provider.load_from_path(str(ROOT / "extras/gtk/gtk.css"))
        self.assertEqual(errors, [])

        def context_for(nodes, state=Gtk.StateFlags.NORMAL):
            path = Gtk.WidgetPath()
            for node in nodes:
                index = path.append_type(GObject.TYPE_OBJECT)
                name, *classes = node if isinstance(node, tuple) else (node,)
                path.iter_set_object_name(index, name)
                for css_class in classes:
                    path.iter_add_class(index, css_class)
            context = Gtk.StyleContext()
            context.set_path(path)
            context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            context.set_state(state)
            return context

        def colors(nodes, state=Gtk.StateFlags.NORMAL):
            context = context_for(nodes, state)
            return (context.get_property("background-color", state).to_string(),
                    context.get_color(state).to_string())

        def painted_background(nodes, state=Gtk.StateFlags.NORMAL):
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 32, 32)
            Gtk.render_background(context_for(nodes, state), cairo.Context(surface),
                                  0, 0, 32, 32)
            surface.flush()
            offset = surface.get_stride() * 16 + 16 * 4
            pixel = int.from_bytes(surface.get_data()[offset:offset + 4],
                                   byteorder=sys.byteorder)
            return ((pixel >> 16) & 255, (pixel >> 8) & 255, pixel & 255, pixel >> 24)

        self.assertEqual(colors(["window"]), ("rgb(170,170,170)", "rgb(0,0,0)"))
        self.assertEqual(colors([("tooltip", "background")]),
                         ("rgb(170,170,170)", "rgb(0,0,0)"))
        self.assertEqual(colors([("tooltip", "background"), "label"])[1],
                         "rgb(0,0,0)")
        self.assertEqual(painted_background([("tooltip", "background")]),
                         (170, 170, 170, 255))
        self.assertEqual(context_for([("tooltip", "background")]).get_property(
            "border-top-color", Gtk.StateFlags.NORMAL).to_string(),
                         "rgb(255,255,255)")
        self.assertEqual(colors(["entry"]), ("rgb(0,0,170)", "rgb(255,255,255)"))
        self.assertEqual(colors(["button"]), ("rgb(0,136,0)", "rgb(255,255,255)"))
        self.assertEqual(colors(["button"], Gtk.StateFlags.ACTIVE)[0], "rgb(0,85,0)")
        self.assertEqual(colors(["menu", "menuitem"], Gtk.StateFlags.PRELIGHT),
                         ("rgb(0,136,0)", "rgb(0,0,0)"))
        self.assertEqual(colors(["menubar", "menuitem"], Gtk.StateFlags.PRELIGHT),
                         ("rgb(0,136,0)", "rgb(0,0,0)"))
        self.assertEqual(colors(["scrollbar", "trough"])[0], "rgb(0,170,170)")
        self.assertEqual(colors(["scrollbar", "trough", "slider"])[0], "rgb(0,0,170)")
        self.assertEqual(colors(["textview", "text"])[0], "rgb(0,0,170)")
        self.assertEqual(colors([("textview", "view"), "text"]),
                         ("rgb(0,0,170)", "rgb(255,255,255)"))
        self.assertEqual(painted_background([("textview", "view"), "text"]),
                         (0, 0, 170, 255))
        self.assertEqual(colors(["headerbar", ("label", "title")])[1],
                         "rgb(255,255,255)")
        self.assertEqual(colors(["dialog", "grid", "label"])[1],
                         "rgb(255,255,255)")
        self.assertEqual(colors(["dialog", "frame", "label"])[1],
                         "rgb(255,255,255)")
        self.assertEqual(colors([("button", "destructive-action")]),
                         ("rgb(170,0,0)", "rgb(255,255,255)"))
        self.assertEqual(colors([("button", "destructive-action")],
                                Gtk.StateFlags.PRELIGHT)[0], "rgb(136,0,0)")
        self.assertEqual(colors([("button", "destructive-action")],
                                Gtk.StateFlags.ACTIVE)[0], "rgb(102,0,0)")
        self.assertEqual(colors([("button", "destructive-action")],
                                Gtk.StateFlags.INSENSITIVE),
                         ("rgb(136,136,136)", "rgb(85,85,85)"))
        self.assertEqual(colors([("entry", "error")]),
                         ("rgb(0,0,170)", "rgb(255,255,255)"))
        self.assertEqual(context_for([("entry", "error")]).get_property(
            "border-top-color", Gtk.StateFlags.NORMAL).to_string(), "rgb(170,0,0)")
        self.assertEqual(colors([("label", "error")])[1], "rgb(170,0,0)")
        self.assertEqual(colors([("infobar", "error")]),
                         ("rgb(170,0,0)", "rgb(255,255,255)"))
        self.assertEqual(colors([("infobar", "error"), "label"])[1],
                         "rgb(255,255,255)")
        self.assertEqual(colors(["dialog", "grid", ("label", "error")])[1],
                         "rgb(170,0,0)")
        self.assertEqual(context_for([("entry", "error")], Gtk.StateFlags.FOCUSED).get_property(
            "border-top-color", Gtk.StateFlags.FOCUSED).to_string(), "rgb(170,0,0)")
        self.assertEqual(colors([("infobar", "error"), "revealer", "box", "label"])[1],
                         "rgb(255,255,255)")
        for state, rgb in (
                (Gtk.StateFlags.NORMAL, (170, 0, 0)),
                (Gtk.StateFlags.PRELIGHT, (136, 0, 0)),
                (Gtk.StateFlags.ACTIVE, (102, 0, 0)),
                (Gtk.StateFlags.INSENSITIVE, (136, 136, 136)),
                (Gtk.StateFlags.INSENSITIVE | Gtk.StateFlags.ACTIVE, (136, 136, 136))):
            self.assertEqual(painted_background([("button", "destructive-action")], state),
                             (*rgb, 255))
        self.assertEqual(painted_background([("infobar", "error"), "revealer", "box"]),
                         (170, 0, 0, 255))
        dialog = Gtk.Dialog()
        self.addCleanup(dialog.destroy)
        grid = Gtk.Grid()
        dialog.get_content_area().add(grid)
        field_label = Gtk.Label(label="Name")
        grid.attach(field_label, 0, 0, 1, 1)
        field_context = field_label.get_style_context()
        field_context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.assertEqual(field_context.get_color(Gtk.StateFlags.NORMAL).to_string(),
                         "rgb(255,255,255)")
        field_context.add_class("error")
        self.assertEqual(field_context.get_color(Gtk.StateFlags.NORMAL).to_string(),
                         "rgb(170,0,0)")


if __name__ == "__main__":
    unittest.main()
