"""Render native GTK4 controls using the user CSS installed by the test fixture."""

import json
from pathlib import Path
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Graphene


if Gtk.get_minor_version() < 16 or not Gtk.init_check():
    sys.exit(77)
if "--adwaita" in sys.argv:
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    Adw.init()
    window = Adw.Window(title="Turbo Pascal GTK4 preview")
else:
    window = Gtk.Window(title="Turbo Pascal GTK4 preview")
Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
provider = Gtk.CssProvider()
errors = []
provider.connect("parsing-error", lambda p, s, e: errors.append(str(e)))
provider.load_from_path(str(Path(sys.argv[1])))
assert not errors, errors

window.set_default_size(640, 480)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
for name in ("top", "bottom", "start", "end"):
    getattr(box, "set_margin_" + name)(20)
if "--adwaita" in sys.argv:
    window.set_content(box)
else:
    window.set_child(box)
widgets = {}
for name in ("normal", "destructive"):
    button = Gtk.Button(label="Open" if name == "normal" else "Reset")
    button.set_size_request(-1, 48)
    if name == "destructive":
        button.add_css_class("destructive-action")
    box.append(button)
    widgets[name] = button
entry = Gtk.Entry(text="HELLO.PAS")
entry.set_size_request(-1, 48)
box.append(entry)
widgets["entry"] = entry
editor = Gtk.TextView()
editor.set_vexpand(True)
editor.set_monospace(True)
editor.get_buffer().set_text("program Hello;\n\nbegin\n  WriteLn('Hello, world!');\nend.")
box.append(editor)
widgets["editor"] = editor
window.present()
loop = GLib.MainLoop()
results = {}


def sample(widget):
    width, height = widget.get_width(), widget.get_height()
    snapshot = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(widget).snapshot(snapshot, width, height)
    node = snapshot.to_node()
    assert node is not None
    rect = Graphene.Rect()
    rect.init(0, 0, width, height)
    texture = window.get_renderer().render_texture(node, rect)
    downloader = Gdk.TextureDownloader.new(texture)
    downloader.set_format(Gdk.MemoryFormat.R8G8B8A8)
    data, stride = downloader.download_bytes()
    pixel = tuple(data.get_data()[stride * 8 + 8 * 4:stride * 8 + 8 * 4 + 4])
    return {"pixel": pixel, "foreground": widget.get_color().to_string()}


def capture():
    try:
        for name, widget in widgets.items():
            results[name] = sample(widget)
        results["window"] = sample(window)
        print(json.dumps(results))
    finally:
        window.destroy()
        loop.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(400, capture)
loop.run()
