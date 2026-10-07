import importlib.util
from pathlib import Path
import struct
import tomllib
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("wallpapers", ROOT / "artwork/generate.py")
wallpapers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wallpapers)
SVG = "{http://www.w3.org/2000/svg}"


class WallpaperTests(unittest.TestCase):
    def test_all_requested_categories_exist(self):
        self.assertEqual(set(wallpapers.DESIGNS), {
            "2-empty-ide", "3-pascal-source", "4-dos-prompt",
            "5-text-landscape", "6-wireframe-torus", "7-faceted-geometry",
            "8-ascii-harbor", "9-ascii-orbit", "10-dot-sphere", "11-wireframe-cube",
            "12-ascii-city", "13-ascii-citadel",
            "14-bbs-planet", "15-bbs-bat",
            "16-bbs-pipe-portrait",
        })
        self.assertTrue((ROOT / "backgrounds/1-omarchy.png").is_file())

    def test_sources_are_deterministic_valid_static_svg(self):
        for name, design in wallpapers.DESIGNS.items():
            with self.subTest(name=name):
                source = design()
                self.assertEqual(source, design())
                self.assertEqual((ROOT / "artwork" / f"{name}.svg").read_text(), source)
                root = ET.fromstring(source)
                self.assertEqual(root.attrib["viewBox"], "0 0 960 540")
                self.assertEqual(root.find(f"{SVG}rect").attrib["fill"], wallpapers.BLUE)
                for element in root.iter():
                    self.assertNotIn(element.tag, (
                        f"{SVG}script", f"{SVG}image", f"{SVG}animate",
                        f"{SVG}linearGradient", f"{SVG}radialGradient", f"{SVG}filter",
                    ))

    def test_all_backgrounds_are_4k_pngs(self):
        files = sorted((ROOT / "backgrounds").glob("*.png"))
        self.assertEqual(len(files), 17)
        for path in files:
            with self.subTest(name=path.name):
                header = path.read_bytes()[:24]
                self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(header[12:16], b"IHDR")
                self.assertEqual(struct.unpack(">II", header[16:24]), (3840, 2160))

    def test_palette_matches_theme(self):
        palette = tomllib.loads((ROOT / "colors.toml").read_text())
        self.assertEqual(wallpapers.BLUE, palette["background"])
        self.assertEqual(wallpapers.WHITE, palette["foreground"])
        self.assertEqual(wallpapers.YELLOW, palette["yellow"])
        self.assertEqual(wallpapers.CYAN, palette["cyan"])
        self.assertEqual(wallpapers.GRAY, palette["muted"])
        self.assertEqual(wallpapers.GREEN, palette["bright_green"])

    def test_icosahedron_is_a_complete_regular_mesh(self):
        vertices, edges, faces = wallpapers.icosahedron_mesh()
        self.assertEqual((len(vertices), len(edges), len(faces)), (12, 30, 20))
        for index in range(12):
            self.assertEqual(sum(index in edge for edge in edges), 5)
        for edge in edges:
            self.assertEqual(sum(set(edge) <= set(face) for face in faces), 2)

    def test_projected_geometry_stays_inside_canvas(self):
        for design in (
            wallpapers.torus, wallpapers.faceted_geometry,
            wallpapers.dot_sphere, wallpapers.wireframe_cube,
        ):
            root = ET.fromstring(design())
            for element in root.iter():
                for point in element.attrib.get("points", "").split():
                    x, y = map(float, point.split(","))
                    self.assertGreater(x, 0)
                    self.assertLess(x, wallpapers.WIDTH)
                    self.assertGreater(y, 0)
                    self.assertLess(y, wallpapers.HEIGHT)
                if element.tag == f"{SVG}circle":
                    for axis, limit in (("cx", wallpapers.WIDTH), ("cy", wallpapers.HEIGHT)):
                        value = float(element.attrib[axis])
                        radius = float(element.attrib["r"])
                        self.assertGreater(value - radius, 0)
                        self.assertLess(value + radius, limit)

    def test_pascal_and_dos_text_are_preserved(self):
        root = ET.fromstring(wallpapers.pascal_source())
        lines = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
        for source in wallpapers.PASCAL_SOURCE:
            self.assertIn(source, lines)
        root = ET.fromstring(wallpapers.dos_prompt())
        lines = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
        self.assertIn("C:\\>CD OMARCHY", lines)
        self.assertIn("C:\\OMARCHY>", lines)

    def test_landscape_is_original_ascii(self):
        self.assertTrue(all(line.isascii() for line in wallpapers.LANDSCAPE))
        self.assertTrue(any("/\\" in line for line in wallpapers.LANDSCAPE))
        self.assertTrue(any("[]" in line for line in wallpapers.LANDSCAPE))
        self.assertTrue(any("~~~" in line for line in wallpapers.LANDSCAPE))

    def test_additional_scenes_preserve_original_ascii(self):
        for lines, design in (
            (wallpapers.HARBOR, wallpapers.ascii_harbor),
            (wallpapers.ORBIT, wallpapers.ascii_orbit),
        ):
            self.assertTrue(all(line.isascii() for line in lines))
            root = ET.fromstring(design())
            rendered = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
            for line in lines:
                self.assertIn(line, rendered)
        self.assertTrue(any("~~~" in line for line in wallpapers.HARBOR))
        self.assertTrue(any("<===" in line for line in wallpapers.ORBIT))

    def test_demo_geometry_has_complete_point_and_edge_counts(self):
        sphere = ET.fromstring(wallpapers.dot_sphere())
        self.assertEqual(len(sphere.findall(f"{SVG}circle")), 19 * 36)
        cube = ET.fromstring(wallpapers.wireframe_cube())
        self.assertEqual(len(cube.findall(f"{SVG}polyline")), 12)
        self.assertTrue(any(
            line.attrib["stroke"] == wallpapers.GREEN
            for line in cube.findall(f"{SVG}polyline")
        ))

    def test_dense_scenes_are_ascii_and_measurably_dense(self):
        for canvas, design in (
            (wallpapers.city_canvas(), wallpapers.ascii_city),
            (wallpapers.citadel_canvas(), wallpapers.ascii_citadel),
        ):
            self.assertEqual(len(canvas), wallpapers.ASCII_ROWS)
            self.assertTrue(all(len(row) == wallpapers.ASCII_COLUMNS for row in canvas))
            lines = ["".join(character for character, _ in row) for row in canvas]
            self.assertTrue(all(line.isascii() for line in lines))
            occupied = sum(character != " " for line in lines for character in line)
            self.assertGreaterEqual(occupied, 1700)
            self.assertGreater(occupied / (wallpapers.ASCII_ROWS * wallpapers.ASCII_COLUMNS), 0.43)
            root = ET.fromstring(design())
            rendered = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
            self.assertEqual(rendered, lines)
            for row in canvas:
                for _, color in row:
                    self.assertIn(color, (
                        wallpapers.WHITE, wallpapers.GRAY, wallpapers.TEAL,
                        wallpapers.CYAN, wallpapers.YELLOW,
                    ))

    def test_dense_text_fits_the_canvas(self):
        for design in (wallpapers.ascii_city, wallpapers.ascii_citadel):
            root = ET.fromstring(design())
            for element in root.findall(f"{SVG}text"):
                x, y = float(element.attrib["x"]), float(element.attrib["y"])
                size = float(element.attrib["font-size"])
                self.assertGreater(x, 0)
                self.assertLess(x + wallpapers.ASCII_COLUMNS * size * 0.6, wallpapers.WIDTH)
                self.assertGreater(y - size, 0)
                self.assertLess(y, wallpapers.HEIGHT)

    def test_archive_art_is_preserved_with_credits_and_notice(self):
        for stem, design, credit in (
            ("14-bbs-planet", wallpapers.bbs_planet, "JAY THALER"),
            ("15-bbs-bat", wallpapers.bbs_bat, "HERMAN STEVENS"),
            ("16-bbs-pipe-portrait", wallpapers.bbs_pipe_portrait, "BRANDON THOMAS MULLINS"),
        ):
            lines = (ROOT / "artwork" / f"{stem}.txt").read_text(encoding="ascii").splitlines()
            root = ET.fromstring(design())
            rendered = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
            self.assertEqual(rendered[:-1], lines)
            self.assertIn(credit, rendered[-1])
            for element in root.findall(f"{SVG}text")[:-1]:
                x, y = float(element.attrib["x"]), float(element.attrib["y"])
                size = float(element.attrib["font-size"])
                columns = len("".join(element.itertext()))
                self.assertGreater(x, 0)
                self.assertLess(x + columns * size * 0.6, wallpapers.WIDTH)
                self.assertGreater(y - size, 0)
                self.assertLess(y, wallpapers.HEIGHT)
        self.assertIn("-JT", (ROOT / "artwork/14-bbs-planet.txt").read_text())
        notice = (ROOT / "licenses/scarecrow-bbs-NOTICE.txt").read_text()
        self.assertIn("c1994 Glen Robbins", notice)
        self.assertIn("distributed non-commercially at no charge", notice)
        self.assertIn("NOT covered by this repository's MIT license", notice)


if __name__ == "__main__":
    unittest.main()
