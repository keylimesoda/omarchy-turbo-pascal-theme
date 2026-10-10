hl.config({
  decoration = {
    dim_inactive = true,
    dim_strength = 0.17,
  },
})

-- Only ordinary inactive windows get an absolute target; app opt-outs remain intact.
hl.window_rule({
  name = "turbo-pascal-inactive-opacity",
  match = { tag = "default-opacity", focus = false, fullscreen = false },
  opacity = "0.97 override",
})

hl.window_rule({
  name = "turbo-pascal-pop-square",
  match = { tag = "pop" },
  rounding = 0,
})

hl.curve("turboPascalSettle", { type = "bezier", points = { { 0.25, 0.75 }, { 0.5, 1 } } })
hl.animation({ leaf = "fadeSwitch", enabled = true, speed = 2.75, bezier = "turboPascalSettle" })
hl.animation({ leaf = "fadeDim", enabled = true, speed = 2.75, bezier = "turboPascalSettle" })
