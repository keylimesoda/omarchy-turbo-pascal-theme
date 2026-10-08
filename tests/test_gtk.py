import importlib.util
import json
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
