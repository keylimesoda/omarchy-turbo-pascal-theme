# Changes

## 2.0.0

Full styling now starts automatically after you remove the installed theme's
`.git` directory and reapply Turbo Pascal. The standard Git installation still
provides colors and wallpapers without running companion setup.

- Keep the existing widget frames, green buttons, GTK3/GTK4 styles, focus fades
  and locally built double window borders.
- Preserve the selected bar, custom widgets, positions, options and unrelated
  shell settings.
- Migrate previous extras-only installations and update owned companion files
  when the theme sources change. Preserve backups and stop on local edits.
- Serialize setup and theme-change hooks, avoid repeated installation on
  compositor reload, and build from a private source snapshot.
- Restore GTK styles and unload owned borders when switching away. Removal
  also disables automatic setup until explicitly enabled again.
- Rewrite installation, update, removal and troubleshooting instructions.

Validation: 132 tests passed in an omabox desktop on Omarchy 4.0.4-1 and
Hyprland 0.56.2, x86_64. Live checks covered Git/base installation, trusted
activation, ten styled widgets, native border compilation/loading, repeated
activation, theme switches, re-enabling and removal. All eleven bundled plugin
manifests passed the portable and installed Omarchy validators. Migration and
source-update behavior were also checked with temporary-home fixtures.
Physical hardware, older desktops and an actual machine reboot were not tested.
