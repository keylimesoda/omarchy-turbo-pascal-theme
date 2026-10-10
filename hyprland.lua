-- TURBO PASCAL AUTOMATIC EXTRAS
-- Omarchy stages this entry point only after the theme's .git directory is removed.
local home = os.getenv("HOME")
local theme = home .. "/.local/state/omarchy/current/theme"
local disabled = io.open(home .. "/.local/state/omarchy/turbo-pascal-disabled", "r")

hl.config({
  general = { col = { active_border = "rgba(ffffffff)", inactive_border = "rgba(aaaaaaff)" } },
  group = { col = { border_active = "rgba(ffffffff)", border_inactive = "rgba(aaaaaaff)" } },
})

if disabled then
  disabled:close()
else
  dofile(theme .. "/extras/borders/focus.lua")
  -- Build and shell setup run outside the compositor's configuration parser.
  hl.exec_cmd('mkdir -p "$HOME/.local/state/omarchy"; python3 -B "$HOME/.local/state/omarchy/current/theme/extras/activate.py" >> "$HOME/.local/state/omarchy/turbo-pascal-extras.log" 2>&1')
end
