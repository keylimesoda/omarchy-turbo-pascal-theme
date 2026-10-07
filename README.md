# Turbo Pascal Theme for Omarchy

An Omarchy theme inspired by Turbo Pascal's DOS IDE.

DOS-blue workspaces, gray dialogs, green buttons, and **double-white borders**.  Base colors in the theme, with a companion installer that brings the window and widget frames along for the ride.

![Turbo Pascal Theme for Omarchy running on a real desktop with terminals, a browser, a gray status bar, and the battery panel](docs/in-use.png)

An actual desktop in everyday use: DOS-blue terminals, the gray status bar and
battery panel, green power-profile buttons, double-white focused-window borders,
and dimmed, slightly transparent inactive windows.

## Install

**Theme:** colors, gray panels and seventeen wallpapers.

```bash
omarchy theme install https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git
```

**Optional extras:** double borders, styled buttons and focus fades.

```bash
cd ~/.config/omarchy/themes/turbo-pascal
./install.sh
```

**Remove extras:** run `./uninstall.sh` from the same folder. The theme stays.

Extras include hyprland config settings for window attention behavior, double-white borders, and custom base system widgets. Strives for easy compatibility, and will ask permission if install encounters potential incompatibilities.

### Theme or extras?

| Base theme: standard Omarchy install | Optional extension: separate script |
|---|---|
| Terminal and application palettes | Double-line focused-window borders |
| Gray bar, popup and menu colors | Double-white widget frames and black shadows |
| Supported shell control colors/states | Raised/recessed green buttons with white labels |
| Ordinary white/gray window border colors | 17% inactive dimming and 275 ms focus fades |
| All seventeen static wallpapers | 97% target opacity for ordinary inactive windows |

The base uses `colors.toml` and `shell.*.toml`; Omarchy generates the application
configs. Custom widgets receive the colors they support, not an automatic
redesign. The extension replaces supported stock components with styled clones.

## What's included

- A deep DOS-blue terminal, white text, yellow emphasis, and readable cyan
  directory names. ANSI blue is mapped to dark cyan (`#00AAAA`), while bright
  blue stays bright cyan (`#55FFFF`). ANSI green
  becomes bright yellow (`#FFFF55`) for the Omarchy terminal logo and update
  headings, while bright green stays green (`#55FF55`). ANSI yellow remains
  yellow, and bright yellow becomes bright orange (`#FFAA55`). Other normal
  green-coded terminal output also shifts to yellow; widget buttons keep their
  independently configured green fills.
- Gray widget panels with black text, double-white frames, and crisp black
  drop-shadows.
- Green buttons with white labels. Selected buttons are darker and recessed;
  unselected buttons have a small offset shadow.
- Gray menus with green selections and a green open-widget indicator.
- **Focused windows framed by white / blue / white lines.** Inactive windows
  retain a single gray border.
- A subtle fade and 17% dimming for unfocused windows. Ordinary inactive windows
  target 97% compositor opacity rather than adding another opacity multiplier.
  Application opt-outs, fullscreen windows, intrinsic transparency and later
  user rules are preserved. Focused windows keep their normal appearance.
  This uses transparency and dimming, not a desaturation filter.
- Gentle 275 ms ease-out focus transitions for both opacity and dimming:
  an immediate response followed by soft, analog-inspired settling, without bounce.
  Other window and workspace animations retain Omarchy's defaults.
- Seventeen static 4K wallpapers: IDE workspaces, Pascal source, a DOS prompt,
  text-mode scenery, mathematical geometry, and a DOS-colored Omarchy logo.
  No animations or additional wallpaper renderer.

The frame styling, inactive-window fade, and widget enhancements require the
companion installer. The palette works on its own.

![Illustrative Pascal terminal showing the theme's DOS-blue, yellow, and cyan palette alongside a gray widget panel](docs/preview.png)

This additional terminal preview uses illustrative Pascal text and the theme's
actual ANSI palette.

![Dot-sphere wallpaper with a double-white widget frame, gray panel, and raised and recessed green buttons](docs/desktop.png)

## Optional extension

<details>
<summary>Extension details: requirements, files and removal</summary>

Install the theme first. The commands above add the optional extension.

**Tested baseline: Omarchy 4.0.4-1 and Hyprland 0.56.2.**
The installer also attempts compatible extras on Omarchy 4.x with Hyprland
0.52–0.56, using native Lua or legacy `.conf` output. Earlier-version syntax has
been checked against upstream source, not tested on those desktops. Double
borders have narrower compatibility than native focus effects.

| Option | Meaning |
|---|---|
| `--check` | Read-only prerequisite check; does not build or ask to replace widgets |
| `--allow-untested` | Try other versions; never bypass compositor/header ABI checks |
| `--skip-widgets` | Keep your existing widgets |
| `--skip-borders` | Omit the compiled window-border plugin |
| `--skip-focus` | Keep existing opacity, dimming and focus animations |

Pass options to `./install.sh`; they can be combined.

The extension activates the theme if necessary and restarts the shell.
It does not copy, overwrite or own the installed base theme. Do **not** use sudo.
It needs Python 3. Only double borders need Git, GNU make, g++, pkg-config and
matching development packages. A missing tool or failed border build does not
block widgets or focus effects. It never installs system packages or changes
`/usr/share/omarchy`.

The double border uses a small patch to the official
[`borders-plus-plus`](https://github.com/hyprwm/hyprland-plugins/tree/v0.56.0/borders-plus-plus)
plugin. The 0.56 source is pinned to upstream commit
`7644cecdb947060682891a0db2a0cdc5c0b9e704`; other versions attempt a matching
upstream tag. A patch/build failure skips double borders. The running
compositor commit and available ABI hash must match the installed headers and
dependencies; no precompiled plugin binary is distributed.

### What the installer changes

| Location | Purpose |
|---|---|
| `~/.config/omarchy/plugins/turbo-pascal.*/` | User-owned shell clones |
| `~/.config/omarchy/shell.json` | Switch the built-in bar and existing supported widgets to those clones |
| `~/.config/omarchy/hooks/{theme-set,post-boot}.d/turbo-pascal-borders` | Theme-aware native effects and border loading |
| `~/.local/share/omarchy-turbo-pascal/` | Focus settings, border source, locally built plugin and runtime status |
| `~/.local/state/omarchy/turbo-pascal-install/` | Installation record and backups |

Existing widget positions, options, unrelated plugins, and idle settings are
preserved. Missing widget icons are not added; the menu service can still be
styled without an icon. Custom components are kept unless you approve replacing
them with stock-based styled clones. Their original files stay; their custom
behavior does not transfer. Existing target files require permission and are
backed up. Your transparent-bar setting is left alone.

An existing `borders-plus-plus` installation skips our window borders, not the
other extras. Conflicting hooks/runtime files and symlinked installation targets
stop installation rather than being overwritten.

Omarchy intentionally omits executable Lua from themes installed through Git.
The explicitly authorized companion hook appends only enabled native effects
to the generated theme; it preserves Omarchy's base output. Focus effects do not
need the compiled border plugin. Switching away removes the native overlay and
unloads only this installation's border plugin; shell clones remain installed
and fall back to the next theme's normal palette.

### Removal and updates

Uninstall restores shell settings and removes the owned plugins, hooks and
border runtime. The base theme stays installed; if it is active, Omarchy
reapplies its standard appearance. Later bar-layout and widget-option edits are
kept. Previously selected custom components are restored when still applicable.

Edited extension/plugin files stop removal before more files are removed;
back up your edits and restore the installed files first. Backups are retained.
If removal fails, fix the reported problem and run `./uninstall.sh` again.
For an update, uninstall, pull the repository, then install again; the previous
backup record is archived automatically.

Older companion installations also managed base-theme files; their saved
installation records retain the original restore behavior. Uninstall those
before installing the base theme through the standard Omarchy command.

After compositor upgrades, borders rebuild only when headers/dependencies
match; build/load failures are reported and skipped. See
`~/.local/share/omarchy-turbo-pascal/runtime-status.json` for native-effect
status. Shell clones are snapshots and do not automatically track upstream
changes. Tests use isolated fixtures; a clean-machine installation and actual
reboot persistence have not yet been verified.

The 97% target applies only to inactive, non-fullscreen windows carrying
Omarchy's `default-opacity` tag. It preserves application opt-outs and does not
eliminate transparency drawn inside an application. Excessive transparency on
the other machine remains undiagnosed. Neither installation configures Copilot
CLI, changes your font, or modifies your terminal command.

</details>

## Development

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh extras/borders/apply-borders \
  extras/borders/turbo-pascal-borders
```

Installer tests use a temporary home and simulated desktop commands; they do
not alter a running desktop. The plugin patch must also be built against the
supported Hyprland headers before releasing changes.

## Wallpapers

![Complete Turbo Pascal wallpaper collection](docs/wallpapers.png)

| File | Design |
|---|---|
| [0-dos-blue.png](backgrounds/0-dos-blue.png) | Original blue IDE workspace with a subtle frame and Pascal text |
| [1-omarchy.png](backgrounds/1-omarchy.png) | Official pixel-style Omarchy wordmark in yellow on DOS blue |
| [2-empty-ide.png](backgrounds/2-empty-ide.png) | Empty editor, double-white frame, and a tiny waiting cursor |
| [3-pascal-source.png](backgrounds/3-pascal-source.png) | Original Pascal program with yellow syntax and cyan comments |
| [4-dos-prompt.png](backgrounds/4-dos-prompt.png) | Quiet DOS prompt with a static yellow block cursor |
| [5-text-landscape.png](backgrounds/5-text-landscape.png) | Original ASCII mountains, moon, cabin, trees, and water |
| [6-wireframe-torus.png](backgrounds/6-wireframe-torus.png) | Cyan mathematical wireframe with a tiny yellow marker |
| [7-faceted-geometry.png](backgrounds/7-faceted-geometry.png) | Flat-shaded icosahedron with cyan edges and a yellow accent |
| [8-ascii-harbor.png](backgrounds/8-ascii-harbor.png) | Original moonlit ASCII harbor, lighthouse, and sailboat |
| [9-ascii-orbit.png](backgrounds/9-ascii-orbit.png) | Original ASCII ringed planet and starship with yellow windows |
| [10-dot-sphere.png](backgrounds/10-dot-sphere.png) | Depth-colored dotted sphere inspired by Pascal graphics demos |
| [11-wireframe-cube.png](backgrounds/11-wireframe-cube.png) | Green-and-teal perspective cube with a yellow corner marker |
| [12-ascii-city.png](backgrounds/12-ascii-city.png) | Dense ASCII waterfront skyline, textured buildings, and yellow window reflections |
| [13-ascii-citadel.png](backgrounds/13-ascii-citadel.png) | Dense ASCII mountain citadel with shaded peaks, brick towers, and a winding approach |
| [14-bbs-planet.png](backgrounds/14-bbs-planet.png) | Jay Thaler's signed planet illustration from Scarecrow's 1994 BBS archive |
| [15-bbs-bat.png](backgrounds/15-bbs-bat.png) | NightBreed bat-wing artwork from the archive, contributed by Herman Stevens |
| [16-bbs-pipe-portrait.png](backgrounds/16-bbs-pipe-portrait.png) | User-supplied ASCII pipe portrait and original BBS panel, with archive contributor credit |

All backgrounds are 3840x2160 PNGs with a shared DOS-blue background. Cycle
through the installed collection with:

```bash
omarchy theme bg next
```

The geometry designs are original mathematical illustrations inspired by the
look of DOS graphics demos, not copied screenshots or official Borland artwork.
The landscape, harbor, orbital scene, city, and citadel are original ASCII art.
The city and citadel use filled 108-column, 36-row character scenes for a denser
BBS-style alternative to the quieter outline designs.
All designs are static: even the cursors are painted pixels, not blinking animations.
The dotted sphere and wireframe cube take visual inspiration from the modern
[Turbo Pascal demo collection](https://github.com/johangardhage/dos-tpdemos);
the wallpaper geometry is generated here rather than copied from its screenshots.

Editable SVG sources for the original designs live in `artwork/`.
Regenerate the twelve newer original designs and three archive selections with
Python 3 and `rsvg-convert`
(the librsvg rendering tool):

```bash
python3 artwork/generate.py
```

This rewrites their generated SVG and PNG files; make source changes in the
generator if you want them to survive regeneration. Rendering uses the
Omarchy-installed JetBrains Mono Nerd Font, with a monospace fallback. Exact
glyph appearance can differ on machines without that font. The three archive
designs use their preserved `.txt` sources rather than generated character art.

The logo wallpaper is recolored from Omarchy's
[`matte-black/backgrounds/omarchy.png`](https://github.com/basecamp/omarchy/blob/master/themes/matte-black/backgrounds/omarchy.png),
under the upstream MIT license included below. Its original 3840x2160 geometry
is unchanged. To reproduce it on the supported Omarchy baseline with ImageMagick:

```bash
magick /usr/share/omarchy/themes/matte-black/backgrounds/omarchy.png \
  -fill '#0000AA' -opaque '#121212' \
  -fill '#FFFF55' -opaque '#E68E0D' -strip backgrounds/1-omarchy.png
```

## Credits and license

Original theme artwork and adaptations: [keylimesoda](https://github.com/keylimesoda),
MIT licensed, **except for the three separately documented BBS archive wallpapers**.
The planet, NightBreed bat, and pipe portrait appear in
[Best of the Scarecrow's BBS Gallery 1.3](https://www.asciiart.eu/collections/best-of-the-scarecrows-bbs-gallery-1-3),
compiled by Glen Robbins in 1994. Their original text and available credits
are preserved; see [`licenses/scarecrow-bbs-NOTICE.txt`](licenses/scarecrow-bbs-NOTICE.txt)
for the archive's no-charge, non-commercial distribution notice. Do not assume
these assets have the commercial reuse permissions of MIT. The archive does
not establish the original artist of every piece.
The pipe portrait uses the exact text supplied by the user. The underlying
Dobbshead image has a [rights notice from the SubGenius Foundation](https://www.subgenius.com/trademark.htm);
the archive's general statement does not settle those rights.

Shell clones are adapted from Omarchy 4.0.4 and retain Omarchy's
MIT license in [`licenses/omarchy-MIT.txt`](licenses/omarchy-MIT.txt).
The Hyprland plugin is BSD-3-Clause; its notice is included in
[`licenses/hyprland-plugins-BSD-3-Clause.txt`](licenses/hyprland-plugins-BSD-3-Clause.txt).

Turbo Pascal is referenced as visual inspiration. This project is not
affiliated with or endorsed by Borland, Embarcadero, Omarchy, or Hyprland.
The IDE, source, prompt, landscape, and geometry wallpapers are original
artwork, not copies of historical screenshots. The three BBS archive selections
are credited third-party artwork under the separate notice above.
The Omarchy logo wallpaper adapts the upstream artwork as described above.
