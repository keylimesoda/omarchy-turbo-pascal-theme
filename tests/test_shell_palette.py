"""VGA-gray bar chrome must survive Omarchy theme refresh."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


def parse_toml_tables(path):
    tables = {}
    section = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            tables[section] = {}
            continue
        if section is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        tables[section][key.strip()] = value.strip().strip('"')
    return tables


class ShellPaletteTests(unittest.TestCase):
    def test_bar_is_black_on_vga_gray(self):
        shipped = parse_toml_tables(ROOT / "shell.toml")["bar"]
        overlay = parse_toml_tables(ROOT / "shell.bar.toml")["bar"]
        for table in (shipped, overlay):
            self.assertEqual(table["background"], "#AAAAAA")
            self.assertEqual(table["text"], "#000000")
            self.assertEqual(table["background-alpha"], "1.0")
            self.assertEqual(table["active"], "#AA0000")
