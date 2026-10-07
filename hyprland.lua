hl.config({
  decoration = {
    inactive_opacity = 0.97,
    dim_inactive = true,
    dim_strength = 0.17,
  },
  general = {
    border_size = 1,
    col = {
      active_border = "rgba(ffffffff)",
      inactive_border = "rgba(aaaaaaff)",
    },
  },
  group = {
    col = {
      border_active = "rgba(ffffffff)",
      border_inactive = "rgba(aaaaaaff)",
    },
  },
})

hl.curve("turboPascalSettle", { type = "bezier", points = { { 0.25, 0.75 }, { 0.5, 1 } } })
hl.animation({ leaf = "fadeSwitch", enabled = true, speed = 2.75, bezier = "turboPascalSettle" })
hl.animation({ leaf = "fadeDim", enabled = true, speed = 2.75, bezier = "turboPascalSettle" })

for _, plugin in ipairs(hl.get_loaded_plugins()) do
  if plugin.name == "borders-plus-plus" then
    hl.config({
      plugin = {
        borders_plus_plus = {
          add_borders = 2,
          active_only = true,
          natural_rounding = false,
          border_size_1 = 1,
          border_size_2 = 1,
          col = {
            border_1 = "rgb(0000aa)",
            border_2 = "rgb(ffffff)",
          },
        },
      },
    })
  end
end
