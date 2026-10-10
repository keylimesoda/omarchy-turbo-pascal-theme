# Turbo Pascal Theme for Omarchy

DOS-blue workspaces, gray dialogs, green buttons and double-white frames,
inspired by Turbo Pascal's DOS IDE.

![Turbo Pascal theme with terminals, a browser and a gray battery panel](docs/in-use.png)

Version **2.0.0** · [Changes](CHANGELOG.md)

## Install

Start with the colors and seventeen wallpapers:

```bash
omarchy theme install https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git
```

For the full styling, review the theme's code, then remove its Git metadata and
apply it again:

```bash
cd ~/.config/omarchy/themes/turbo-pascal
rm -rf .git
omarchy theme set turbo-pascal
```

That's it. The first application prepares the widgets, GTK styles and window
borders in the background. Border compilation may take a little time. Run these
commands as your desktop user, without sudo.

Omarchy skips executable theme files while `.git` is present. Removing it lets
Omarchy load our Lua entry point, which starts the extras setup. It also removes
this copy from `omarchy theme update`; use the update steps below.

**Full styling requires Omarchy's Lua configuration**, tested with Omarchy
4.0.4-1 and Hyprland 0.56.2 on x86_64 in an omabox desktop. Base colors remain
available without Lua. Python 3 is required for extras. Only double window
borders require Git, make, g++, pkg-config and matching Hyprland development
headers. Missing tools or an incompatible border build skip that feature.
No system packages are installed automatically.

## What's included

The standard installation provides DOS-blue terminals, white text, yellow
accents, cyan directory names, gray bar/menu/popup colors, browser tint where
supported, and seventeen static 4K wallpapers. Normal ANSI green appears yellow;
widget buttons have their own green colors.

The full styling adds:

- White / blue / white frames around focused windows; gray inactive borders.
- Double-white widget frames, black shadows, and raised green buttons with
  darker, recessed selections.
- Gray GTK3, GTK4 and libadwaita dialogs and toolbars, DOS-blue inputs, cyan
  lists, green buttons and red error accents.
- 17% inactive dimming, a 97% opacity target for ordinary inactive windows, and
  gentle 275 ms focus fades. Application opt-outs and fullscreen windows are
  preserved.
- Square corners for Super+O popped-out windows.

Your selected bar, widget positions, options and unrelated plugins are kept.
Existing custom widgets are kept too; the automatic setup only styles supported
stock widgets. Missing widget icons aren't added. The menu can be styled without
adding its icon. The widget clones use the next theme's colors when you switch
away, while the GTK styles and our window-border plugin are deactivated.

![Microsoft Edge using gray GTK chrome and a green menu selection](docs/edge-gtk.png)

In Edge, choose **Settings → Appearance → Overall appearance → GTK** to use the
GTK3 colors. Reopen GTK4 apps after changing themes; they load user CSS at startup.

## Update

With `.git` still present, use `omarchy theme update`, then reapply the theme.

For a full installation, download a fresh copy and enable it again:

```bash
omarchy theme install https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git
cd ~/.config/omarchy/themes/turbo-pascal
rm -rf .git
omarchy theme set turbo-pascal
```

Back up any edits in the theme directory first: `omarchy theme install` replaces
that directory. Changed extras are migrated automatically, including installs
made with the previous extras-only `install.sh`. Previous backups are retained. Edited
managed widget or runtime files stop the migration so your changes can be saved.

## Remove extras

```bash
cd ~/.config/omarchy/themes/turbo-pascal
./uninstall.sh
```

This restores your shell and GTK settings, removes the companion files and
disables automatic setup. The base theme stays installed. Later widget positions
and options are preserved. Edited managed files stop removal before files are
removed; back up those edits and restore the installed versions, then retry.

To turn full styling back on, reapply Turbo Pascal and run:

```bash
python3 -B ~/.config/omarchy/themes/turbo-pascal/extras/activate.py --enable
```

Installations from the earliest installer also owned the base-theme directory.
Remove those extras with their original uninstaller before downloading an update.

## If setup needs attention

The setup log is `~/.local/state/omarchy/turbo-pascal-extras.log`. Border and GTK
status is in `~/.local/share/omarchy-turbo-pascal/runtime-status.json`.
A failed setup stops retrying on each reload. Fix the reported problem and use
the `--enable` command above to retry. It also retries previously skipped extras
when their missing prerequisites become available.

The border plugin is built locally from the official
[borders-plus-plus](https://github.com/hyprwm/hyprland-plugins/tree/v0.56.0/borders-plus-plus)
source, with our focused-window patch. The 0.56 source is pinned to commit
`7644cecdb947060682891a0db2a0cdc5c0b9e704`. Compositor and header/dependency ABI
checks stay enabled; no precompiled plugin is shipped. Unsupported upgrades can
skip borders while the other styling remains available.

## Files and backups

| Location | Purpose |
|---|---|
| `~/.config/omarchy/plugins/turbo-pascal.*/` | Styled widget clones and their shared QML library |
| `~/.config/omarchy/shell.json` | Enable the styled stock widgets |
| `~/.config/omarchy/hooks/{theme-set,post-boot}.d/turbo-pascal-borders` | Apply or restore extras on theme changes and login |
| `~/.local/share/omarchy-turbo-pascal/` | Runtime helpers, border source/build and status |
| `~/.local/share/themes/omarchy-turbo-pascal/` | GTK3 theme |
| `~/.config/gtk-4.0/gtk.css` | Reversible GTK4 import alongside existing CSS |
| `~/.local/state/omarchy/turbo-pascal-install/` | Installation records and backups |

Conflicting files and custom components are preserved. Nothing under
`/usr/share/omarchy` is changed. GTK light/dark mode, fonts and terminal launch
commands are left to your existing settings. Shell clones are snapshots of the
supported shell; they don't automatically absorb upstream widget changes.

## Development

```bash
omabox run -- python3 -B -m unittest discover -s tests -v
bash -n install.sh uninstall.sh extras/borders/apply-borders \
  extras/borders/turbo-pascal-borders
```

The suite includes temporary-home lifecycle fixtures and native GTK rendering
checks. Run it in a disposable desktop. Release checks cover Git installation,
trusted activation, repeated reloads, updates, theme switching and removal;
physical hardware, older desktops and an actual machine reboot aren't covered.

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
