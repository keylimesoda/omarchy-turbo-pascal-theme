#!/usr/bin/env python3
"""Generate static DOS-palette wallpapers and their editable SVGs."""

from html import escape
from itertools import combinations, groupby
import math
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 960, 540
BLUE = "#0000AA"
WHITE = "#FFFFFF"
GRAY = "#AAAAAA"
CYAN = "#55FFFF"
TEAL = "#00AAAA"
YELLOW = "#FFFF55"
GREEN = "#55FF55"
FONT = "JetBrainsMono Nerd Font, monospace"


def text(x, y, value, color=WHITE, size=10, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{FONT}" '
        f'font-size="{size}" text-anchor="{anchor}" xml:space="preserve">'
        f'{escape(value)}</text>'
    )


def document(title, contents):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" '
        'viewBox="0 0 960 540">\n'
        f'  <title>{escape(title)}</title>\n'
        f'  <rect width="960" height="540" fill="{BLUE}"/>\n'
        + "\n".join(contents) + "\n</svg>\n"
    )


def editor_frame(filename):
    return [
        '<g fill="none" stroke="#FFFFFF" stroke-width="0.75" '
        'shape-rendering="crispEdges">'
        '<rect x="64.5" y="64.5" width="831" height="411"/>'
        '<rect x="67.5" y="67.5" width="825" height="405"/></g>',
        f'<rect x="395" y="58" width="170" height="16" fill="{BLUE}"/>',
        text(480, 67, filename, size=10, anchor="middle"),
        f'<rect x="748" y="465" width="130" height="17" fill="{BLUE}"/>',
        text(867, 475, "Ln 1  Col 1  INS", GRAY, 8, "end"),
    ]


def empty_ide():
    contents = editor_frame("UNTITLED.PAS")
    contents += [
        text(88, 106, "1", GRAY, 9),
        f'<rect x="107" y="105" width="6" height="1.5" fill="{WHITE}"/>',
    ]
    return document("Empty IDE", contents)


PASCAL_SOURCE = (
    "program HelloOmarchy;",
    "",
    "{ A little nostalgia. A little less noise. }",
    "",
    "begin",
    "  WriteLn('Welcome home.');",
    "  WriteLn('Blue skies. Clear lines.');",
    "end.",
)


def pascal_source():
    contents = editor_frame("HELLO.PAS")
    token = re.compile(r"\{[^}]*\}|'[^']*'|\b(?:program|begin|end)\b")
    for row, line in enumerate(PASCAL_SOURCE):
        parts = []
        previous = 0
        for match in token.finditer(line):
            parts.append(escape(line[previous:match.start()]))
            value = match.group()
            color = CYAN if value.startswith("{") else YELLOW
            parts.append(f'<tspan fill="{color}">{escape(value)}</tspan>')
            previous = match.end()
        parts.append(escape(line[previous:]))
        contents.append(
            f'<text x="294" y="{208 + row * 18}" fill="{WHITE}" '
            f'font-family="{FONT}" font-size="12" xml:space="preserve">'
            + "".join(parts) + "</text>"
        )
    return document("Pascal source", contents)


def dos_prompt():
    contents = [
        text(264, 205, "Omarchy Desktop [Turbo Pascal Edition]", WHITE, 11),
        text(264, 229, "A quiet place to think.", GRAY, 10),
        text(264, 275, "C:\\>CD OMARCHY", CYAN, 12),
        text(264, 304, "C:\\OMARCHY>", WHITE, 12),
        f'<rect x="344" y="295" width="7" height="12" fill="{YELLOW}"/>',
    ]
    return document("DOS prompt", contents)


LANDSCAPE = (
    "       .                       *                            .",
    "                                                     .--.",
    "                   *                                (    )",
    "      .                                  .           '--'",
    "",
    "                              /\\",
    "             /\\              /  \\              /\\",
    "      /\\    /  \\       /\\   /    \\       /\\    /  \\",
    "     /  \\__/    \\_____/  \\_/      \\_____/  \\__/    \\",
    " ___/                                               \\___",
    "",
    "          /|\\                 ______",
    "         / | \\               /______\\            /|\\",
    "        /__|__\\              |  []  |           / | \\",
    "           |                 |__[]__|          /__|__\\",
    "    _______|____________________||_______________|_____",
    "",
    "       ~~~       ~~~~~     ~~~       ~~~~~      ~~~",
    "   ~~~~~     ~~~       ~~~~~    ~~~        ~~~~~",
)


def text_landscape():
    contents = []
    cell, line_height = 7.2, 12
    x = (WIDTH - max(map(len, LANDSCAPE)) * cell) / 2
    for row, line in enumerate(LANDSCAPE):
        y = 166 + row * line_height
        color = CYAN if row >= 17 else GRAY if row >= 10 else WHITE
        contents.append(text(round(x, 2), y, line, color, 12))
        if row in (13, 14):
            column = line.index("[]")
            contents.append(text(round(x + column * cell, 2), y, "[]", YELLOW, 12))
    return document("Text-mode landscape", contents)


HARBOR = (
    "      .                 *                           .",
    "                                                .--.",
    "                    .                          (    )",
    "       *                                        '--'",
    "",
    "          /\\",
    "         /__\\                              |",
    "         |[]|                             /|",
    "      ---|[]|---                         /  |",
    "         |  |                         /    |",
    "         |  |                       /______|",
    "         |[]|                              |\\",
    "         |  |                        ______|_\\___",
    "        /|__|\\                       \\__________/",
    "    ___/______\\___",
    " __/              \\___",
    "",
    " ~~~~    ~~~     ~~~~~      ~~~     ~~~~~    ~~~~",
    "     ~~~~~     ~~~     ~~~~~     ~~~     ~~~~~",
    " ~~~      ~~~~~     ~~~      ~~~~~     ~~~",
)


def ascii_harbor():
    cell, line_height = 7.2, 12
    x = (WIDTH - max(map(len, HARBOR)) * cell) / 2
    contents = []
    for row, line in enumerate(HARBOR):
        y = 154 + row * line_height
        color = CYAN if row >= 17 else GRAY if row >= 14 else WHITE
        contents.append(text(round(x, 2), y, line, color, 12))
        if "[]" in line:
            column = line.index("[]")
            contents.append(text(round(x + column * cell, 2), y, "[]", YELLOW, 12))
    return document("ASCII moonlit harbor", contents)


ORBIT = (
    "       .                                      *",
    "                            .",
    "                 .-''''-.",
    "          ______/        \\______",
    "       .-'     /          \\     '-.",
    "      (_______|            |_______)",
    "              \\          /                 .",
    "               '-.____.-'",
    "",
    "                                               /\\",
    "     *                                        /  \\",
    "                                __           / [] \\",
    "                         ______/  \\_________/______\\",
    "                    <===|  []  []  []  |      ____   >",
    "                         '-----\\__/----'----\\______/",
    "                                             \\  /",
    "                                              \\/",
    "",
    "              .                    *",
    "    .                                             .",
)


def ascii_orbit():
    cell, line_height = 7.2, 12
    x = (WIDTH - max(map(len, ORBIT)) * cell) / 2
    contents = []
    for row, line in enumerate(ORBIT):
        y = 150 + row * line_height
        color = CYAN if 2 <= row <= 7 else WHITE
        contents.append(text(round(x, 2), y, line, color, 12))
        for match in re.finditer(r"\[\]", line):
            contents.append(text(round(x + match.start() * cell, 2), y, "[]", YELLOW, 12))
        if "<===" in line:
            contents.append(text(round(x + line.index("<===") * cell, 2), y, "<===", YELLOW, 12))
    return document("ASCII orbital voyage", contents)


ASCII_COLUMNS, ASCII_ROWS = 108, 36


def ascii_canvas():
    return [[(" ", WHITE) for _ in range(ASCII_COLUMNS)] for _ in range(ASCII_ROWS)]


def paint_ascii(canvas, x, y, value, color=WHITE):
    if not (0 <= y < ASCII_ROWS and 0 <= x and x + len(value) <= ASCII_COLUMNS):
        raise ValueError(f"ASCII drawing exceeds the canvas at ({x}, {y}): {value!r}")
    canvas[y][x:x + len(value)] = [(character, color) for character in value]


def dense_ascii(title, canvas):
    size, line_height = 12, 12
    x = (WIDTH - ASCII_COLUMNS * size * 0.6) / 2
    top = (HEIGHT - ASCII_ROWS * line_height) / 2 + size
    contents = []
    for row, cells in enumerate(canvas):
        spans = []
        for color, run in groupby(cells, key=lambda cell: cell[1]):
            value = "".join(character for character, _ in run)
            spans.append(f'<tspan fill="{color}">{escape(value)}</tspan>')
        contents.append(
            f'<text x="{x:.2f}" y="{top + row * line_height:.2f}" '
            f'font-family="{FONT}" font-size="{size}" xml:space="preserve">'
            + "".join(spans) + "</text>"
        )
    return document(title, contents)


def city_canvas():
    canvas = ascii_canvas()
    for x, y in ((6, 2), (19, 5), (35, 1), (58, 3), (75, 6), (102, 2), (26, 8)):
        paint_ascii(canvas, x, y, "+" if x % 2 else ".", GRAY)
    for row, line in enumerate((" .---. ", "/.:.:.\\", "|:.:.:|", "\\.:.:./", " '---' ")):
        paint_ascii(canvas, 88, 2 + row, line)
    buildings = (
        (3, 12, 11), (17, 8, 12), (32, 14, 9), (45, 5, 13),
        (62, 12, 11), (76, 9, 10), (89, 14, 15),
    )
    for index, (x, roof, width) in enumerate(buildings):
        paint_ascii(canvas, x + width // 2, roof - 2, "|", GRAY)
        paint_ascii(canvas, x + width // 2, roof - 1, "|", GRAY)
        paint_ascii(canvas, x, roof, "." + "=" * (width - 2) + ".")
        for y in range(roof + 1, 25):
            interior = "".join(
                ":" if column % 3 == 0 else "#" if (column + y) % 2 else "."
                for column in range(width - 2)
            )
            paint_ascii(canvas, x, y, "|" + interior + "|", GRAY)
            paint_ascii(canvas, x + width - 2, y, ":|", TEAL)
            if (y - roof) % 3 == 2:
                for column in range(2, width - 3, 3):
                    color = YELLOW if (index + y + column) % 4 < 2 else TEAL
                    paint_ascii(canvas, x + column, y, "[]", color)
    paint_ascii(canvas, 0, 25, "=" * ASCII_COLUMNS, GRAY)
    paint_ascii(canvas, 0, 26, "_" * ASCII_COLUMNS, WHITE)
    for y in range(27, ASCII_ROWS):
        for x in range(ASCII_COLUMNS):
            phase = (x + y * 3) % 11
            character = "~" if phase < 6 else "." if phase < 8 else " "
            canvas[y][x] = (character, CYAN if y % 3 == 0 else TEAL)
        for index, (x, _, width) in enumerate(buildings):
            drift = (y + index) % 3 - 1
            for column in range(2, width - 3, 3):
                color = YELLOW if (y + column + index) % 7 == 0 else CYAN
                paint_ascii(canvas, x + column + drift, y, "~", color)
    return canvas


def ascii_city():
    return dense_ascii("ASCII midnight city", city_canvas())


def citadel_canvas():
    canvas = ascii_canvas()
    for x, y in ((4, 2), (27, 5), (42, 1), (73, 2), (99, 4), (88, 8)):
        paint_ascii(canvas, x, y, "+", GRAY)
    for row, line in enumerate((" .--. ", "/::::\\", "\\::::/", " '--' ")):
        paint_ascii(canvas, 10, 3 + row, line)
    peaks = ((24, 11), (64, 5), (93, 13))
    for x in range(ASCII_COLUMNS):
        peak, height = min(peaks, key=lambda item: item[1] + abs(x - item[0]) // 2)
        ridge = height + abs(x - peak) // 2
        for y in range(ridge, ASCII_ROWS):
            depth = y - ridge
            if depth == 0:
                character = "^" if x == peak else "/" if x < peak else "\\"
            else:
                texture = ".:;+x#"
                character = texture[min(depth // 3, len(texture) - 1)]
                if (x + y) % 5 == 0:
                    character = ":"
            color = WHITE if depth < 3 else GRAY if x < peak else TEAL
            canvas[y][x] = (character, color)
    for x, roof, width in ((35, 13, 11), (47, 18, 25), (73, 13, 11)):
        paint_ascii(canvas, x, roof, ("_|" * (width // 2)) + "_", WHITE)
        for y in range(roof + 1, 28):
            bricks = "".join("#" if (column + y) % 4 else ":" for column in range(width - 2))
            paint_ascii(canvas, x, y, "|" + bricks + "|", GRAY)
            paint_ascii(canvas, x, y, "|", WHITE)
            paint_ascii(canvas, x + width - 1, y, "|", WHITE)
            if (y - roof) % 4 == 3:
                for column in range(3, width - 3, 6):
                    paint_ascii(canvas, x + column, y, "[]", YELLOW)
    for row, line in enumerate((" /---\\ ", "|     |", "|     |", "|     |", "|_____|")):
        paint_ascii(canvas, 56, 23 + row, line)
    for y in range(28, ASCII_ROWS):
        for x in range(ASCII_COLUMNS):
            canvas[y][x] = (";" if (x + y) % 3 else "#", TEAL)
        width = 7 + (y - 28) * 4
        x = 59 - width // 2
        paint_ascii(canvas, x, y, "/" + ":" * width + "\\", GRAY)
    return canvas


def ascii_citadel():
    return dense_ascii("ASCII alpine citadel", citadel_canvas())


def archive_ascii(stem, title, credit):
    lines = (ROOT / "artwork" / f"{stem}.txt").read_text(encoding="ascii").splitlines()
    columns = max(map(len, lines))
    size = min(18, 760 / (columns * 0.6), 360 / len(lines))
    x = (WIDTH - columns * size * 0.6) / 2
    top = (HEIGHT - len(lines) * size) / 2 + size * 0.8
    contents = [
        text(round(x, 2), round(top + row * size, 2), line,
             YELLOW if line.strip() == "NightBreed BBS" else WHITE, round(size, 4))
        for row, line in enumerate(lines)
    ]
    contents.append(text(480, 484, credit, GRAY, 8, "middle"))
    return document(title, contents)


def bbs_planet():
    return archive_ascii(
        "14-bbs-planet", "Scarecrow archive: planet",
        "JAY THALER (-JT)  /  SCARECROW'S BBS GALLERY 1.3",
    )


def bbs_bat():
    return archive_ascii(
        "15-bbs-bat", "Scarecrow archive: NightBreed bat",
        "ARCHIVE CONTRIBUTOR: HERMAN STEVENS  /  SCARECROW'S BBS GALLERY 1.3",
    )


def bbs_pipe_portrait():
    return archive_ascii(
        "16-bbs-pipe-portrait", "BBS archive: pipe portrait",
        "ARCHIVE CONTRIBUTOR: BRANDON THOMAS MULLINS  /  SCARECROW'S BBS GALLERY 1.3",
    )


def rotate(point, angles):
    x, y, z = point
    a, b, c = angles
    y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
    x, y = x * math.cos(c) - y * math.sin(c), x * math.sin(c) + y * math.cos(c)
    return x, y, z


def project(point):
    x, y, z = point
    factor = 500 / (500 - z)
    return 480 + x * factor, 260 - y * factor


def points_attribute(points):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def torus_point(u, v):
    radius = 105 + 34 * math.cos(v)
    return rotate(
        (radius * math.cos(u), radius * math.sin(u), 34 * math.sin(v)),
        (math.radians(52), math.radians(18), math.radians(-12)),
    )


def torus():
    paths = []
    for axis, count in (("u", 16), ("v", 12)):
        for index in range(count):
            fixed = 2 * math.pi * index / count
            points = [
                torus_point(fixed, 2 * math.pi * step / 96) if axis == "u"
                else torus_point(2 * math.pi * step / 96, fixed)
                for step in range(96)
            ]
            depth = sum(point[2] for point in points) / len(points)
            paths.append((depth, points))
    contents = []
    for depth, points in sorted(paths, key=lambda path: path[0]):
        color = CYAN if depth >= 0 else TEAL
        contents.append(
            f'<polygon points="{points_attribute(map(project, points))}" '
            f'fill="none" stroke="{color}" stroke-width="0.65" stroke-linejoin="round"/>'
        )
    x, y = project(torus_point(0, 0))
    contents.append(f'<rect x="{x-1.5:.2f}" y="{y-1.5:.2f}" width="3" height="3" fill="{YELLOW}"/>')
    contents.append(text(480, 429, "TORUS  /  BGI STUDY 01", GRAY, 8, "middle"))
    return document("Wireframe torus", contents)


def icosahedron_mesh():
    phi = (1 + math.sqrt(5)) / 2
    vertices = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]
    edges = {
        (a, b) for a, b in combinations(range(12), 2)
        if math.isclose(sum((x - y) ** 2 for x, y in zip(vertices[a], vertices[b])), 4)
    }
    faces = [
        (a, b, c) for a, b, c in combinations(range(12), 3)
        if {(a, b), (a, c), (b, c)} <= edges
    ]
    return vertices, edges, faces


def faceted_geometry():
    vertices, _, faces = icosahedron_mesh()
    points = [
        rotate(tuple(value * 65 for value in vertex),
               (math.radians(24), math.radians(31), math.radians(12)))
        for vertex in vertices
    ]
    contents = []
    ordered_faces = sorted(faces, key=lambda face: sum(points[index][2] for index in face))
    for face in ordered_faces:
        a, b, c = (points[index] for index in face)
        ab = tuple(y - x for x, y in zip(a, b))
        ac = tuple(y - x for x, y in zip(a, c))
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        center = tuple(sum(point[axis] for point in (a, b, c)) / 3 for axis in range(3))
        if sum(x * y for x, y in zip(normal, center)) < 0:
            normal = tuple(-value for value in normal)
        light = (-0.4, 0.6, 1)
        brightness = sum(x * y for x, y in zip(normal, light)) / math.sqrt(
            sum(value ** 2 for value in normal) * sum(value ** 2 for value in light)
        )
        color = WHITE if brightness > 0.86 else GRAY if brightness > 0.65 else TEAL if brightness > 0.25 else "#000088"
        contents.append(
            f'<polygon points="{points_attribute(project(points[index]) for index in face)}" '
            f'fill="{color}" stroke="{CYAN}" stroke-width="0.7" stroke-linejoin="round"/>'
        )
    a, b = ordered_faces[-1][:2]
    contents.append(
        f'<polyline points="{points_attribute(project(points[index]) for index in (a, b))}" '
        f'fill="none" stroke="{YELLOW}" stroke-width="1.1"/>'
    )
    contents.append(text(480, 429, "ICOSAHEDRON  /  BGI STUDY 02", GRAY, 8, "middle"))
    return document("Faceted icosahedron", contents)


def dot_sphere():
    points = []
    for latitude in range(1, 20):
        angle = math.pi * latitude / 20
        for longitude in range(36):
            azimuth = 2 * math.pi * longitude / 36
            points.append(rotate(
                (116 * math.sin(angle) * math.cos(azimuth),
                 116 * math.cos(angle),
                 116 * math.sin(angle) * math.sin(azimuth)),
                (math.radians(18), math.radians(-24), math.radians(12)),
            ))
    contents = []
    for point in sorted(points, key=lambda point: point[2]):
        x, y = project(point)
        color = TEAL if point[2] < 0 else CYAN if point[2] < 75 else WHITE
        radius = 0.65 if point[2] < 0 else 1.05
        contents.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{color}"/>'
        )
    contents.append(text(480, 429, "DOT SPHERE  /  BGI STUDY 03", GRAY, 8, "middle"))
    return document("Pascal-demo dot sphere", contents)


def wireframe_cube():
    vertices = [
        (x, y, z)
        for x in (-94, 94) for y in (-94, 94) for z in (-94, 94)
    ]
    edges = [
        (a, b) for a, b in combinations(range(8), 2)
        if sum(x != y for x, y in zip(vertices[a], vertices[b])) == 1
    ]
    points = [
        rotate(vertex, (math.radians(24), math.radians(-32), math.radians(12)))
        for vertex in vertices
    ]
    contents = []
    for a, b in sorted(edges, key=lambda edge: sum(points[index][2] for index in edge)):
        color = GREEN if points[a][2] + points[b][2] >= 0 else TEAL
        contents.append(
            f'<polyline points="{points_attribute(project(points[index]) for index in (a, b))}" '
            f'fill="none" stroke="{color}" stroke-width="0.9" stroke-linejoin="round"/>'
        )
    x, y = project(max(points, key=lambda point: point[2]))
    contents.append(
        f'<rect x="{x-1.5:.2f}" y="{y-1.5:.2f}" width="3" height="3" fill="{YELLOW}"/>'
    )
    contents.append(text(480, 449, "WIREFRAME CUBE  /  BGI STUDY 04", GRAY, 8, "middle"))
    return document("Pascal-demo wireframe cube", contents)


DESIGNS = {
    "2-empty-ide": empty_ide,
    "3-pascal-source": pascal_source,
    "4-dos-prompt": dos_prompt,
    "5-text-landscape": text_landscape,
    "6-wireframe-torus": torus,
    "7-faceted-geometry": faceted_geometry,
    "8-ascii-harbor": ascii_harbor,
    "9-ascii-orbit": ascii_orbit,
    "10-dot-sphere": dot_sphere,
    "11-wireframe-cube": wireframe_cube,
    "12-ascii-city": ascii_city,
    "13-ascii-citadel": ascii_citadel,
    "14-bbs-planet": bbs_planet,
    "15-bbs-bat": bbs_bat,
    "16-bbs-pipe-portrait": bbs_pipe_portrait,
}


def main():
    renderer = shutil.which("rsvg-convert")
    if renderer is None:
        raise SystemExit("Missing rsvg-convert; install librsvg's rendering tool before regenerating.")
    for name, design in DESIGNS.items():
        source = ROOT / "artwork" / f"{name}.svg"
        output = ROOT / "backgrounds" / f"{name}.png"
        source.write_text(design(), encoding="ascii")
        subprocess.run(
            [renderer, "--width", "3840", "--height", "2160", "--output", str(output), str(source)],
            check=True,
        )
        print(output.name)


if __name__ == "__main__":
    main()
