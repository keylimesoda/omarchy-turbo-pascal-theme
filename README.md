# Turbo Pascal for Omarchy

DOS-blue workspaces, gray dialogs, green buttons, and **double-white borders**.
An Omarchy theme inspired by Turbo Pascal's DOS IDE, with an optional companion
installer that brings the window and widget frames along for the ride.

![Turbo Pascal theme with double-white borders](docs/preview.png)

## What's included

- A deep DOS-blue terminal, white text, yellow emphasis, and readable cyan
  directory names. ANSI blue is intentionally mapped to cyan.
- Gray widget panels with black text, double-white frames, and crisp black
  drop-shadows.
- Green buttons with white labels. Selected buttons are darker and recessed;
  unselected buttons have a small offset shadow.
- Gray menus with green selections and a green open-widget indicator.
- **Focused windows framed by white / blue / white lines.** Inactive windows
  retain a single gray border.
- Original static wallpaper: no animations or additional wallpaper renderer.

The frame styling and widget enhancements require the companion installer.
The palette works on its own.

## Full experience

**Supported baseline: Omarchy 4.0.4 (tested with package 4.0.4-1), its Lua
Hyprland configuration, and Hyprland 0.56.2 with matching development headers.**
Other versions are deliberately rejected until the code has been checked
against them. This is a first release, not a universal Hyprland plugin bundle.

Review the scripts, then run these commands as your desktop user inside your
running Hyprland session:

```bash
git clone https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git
cd omarchy-turbo-pascal-theme
./install.sh --check
./install.sh
```

The installer activates the theme and restarts the shell. Do **not** use sudo.
It needs Python 3, Git, GNU make, g++, pkg-config, jq, and the development
packages reported by its prerequisite check. It never installs system packages
or changes `/usr/share/omarchy`.

The double border uses a small patch to the official
[`borders-plus-plus`](https://github.com/hyprwm/hyprland-plugins/tree/v0.56.0/borders-plus-plus)
plugin, pinned to upstream commit
`7644cecdb947060682891a0db2a0cdc5c0b9e704`. It is built locally against your
installed headers; no precompiled plugin binary is distributed.

### What the installer changes

| Location | Purpose |
|---|---|
| `~/.config/omarchy/themes/turbo-pascal/` | Theme palette and wallpaper |
| `~/.config/omarchy/plugins/turbo-pascal.*/` | User-owned shell clones |
| `~/.config/omarchy/shell.json` | Switch the built-in bar and existing supported widgets to those clones |
| `~/.config/omarchy/hooks/{theme-set,post-boot}.d/turbo-pascal-borders` | Theme-aware border loading |
| `~/.local/share/omarchy-turbo-pascal/` | Border source, locally built plugin, and runtime script |
| `~/.local/state/omarchy/turbo-pascal-install/` | Installation record and backups |

Existing widget positions, options, unrelated plugins, and idle settings are
preserved. Missing widgets are not added. Active custom bars or custom clones
of affected widgets are rejected rather than overwritten. Existing
`borders-plus-plus` installations, conflicting hooks, and symlinked installation
targets are also rejected.

Omarchy intentionally omits executable Lua from themes installed through Git.
The explicitly authorized companion hook supplies this theme's border Lua to
the generated theme at activation. Switching away unloads this installation's
border plugin; the shell clones remain installed and fall back to the next
theme's normal palette.

### Uninstall and updates

```bash
./uninstall.sh
```

Uninstall restores backed-up theme files and shell settings, removes the owned
plugins and hooks, and restores the previous theme if Turbo Pascal is still
active. If you changed the bar layout after installation, the clones are
swapped back without discarding your new layout or widget options.

Edited theme/plugin/runtime files stop uninstall **before anything is removed**;
back up your edits and restore the installed files first. Backups are retained.
For an update, uninstall, pull the repository, then install again; the previous
backup record is archived automatically.

On unsupported Hyprland upgrades the border hook reports an error instead of
loading an incompatible binary. Rebuilding is automatic only on the supported
baseline. Shell clones are snapshots, so upstream shell changes do not
automatically update them. Installer/hook lifecycle checks use isolated
fixtures; a clean-machine installation and actual reboot persistence have not
yet been verified.

## Palette only

For the colors and wallpaper without installing executable companion code:

```bash
omarchy theme install https://github.com/keylimesoda/omarchy-turbo-pascal-theme.git
```

This does **not** install the double-line window/widget frames, inset button
styling, or custom shadows. It also does not configure Copilot CLI, change your
font, or modify your terminal command.

## Development

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh extras/borders/apply-borders \
  extras/borders/turbo-pascal-borders
```

Installer tests use a temporary home and simulated desktop commands; they do
not alter a running desktop. The plugin patch must also be built against the
supported Hyprland headers before releasing changes.

## Credits and license

Original theme artwork and adaptations: [keylimesoda](https://github.com/keylimesoda),
MIT licensed. Shell clones are adapted from Omarchy 4.0.4 and retain Omarchy's
MIT license in [`licenses/omarchy-MIT.txt`](licenses/omarchy-MIT.txt).
The Hyprland plugin is BSD-3-Clause; its notice is included in
[`licenses/hyprland-plugins-BSD-3-Clause.txt`](licenses/hyprland-plugins-BSD-3-Clause.txt).

Turbo Pascal is referenced as visual inspiration. This project is not
affiliated with or endorsed by Borland, Embarcadero, Omarchy, or Hyprland.
The wallpaper is original artwork, not a copy of a historical screenshot.
