-- Twilight of the Union: map style in the spirit of TNO (the shader half is gfx/FX/constants.fxh and pdxwater.shader,
-- the border line textures map/terrain/border_*.dds; all three are written by tools/build_map_style.py).
-- Country colour: strongest at the border, fading over this many pixels to the interior fill (vanilla 5 / 25).
-- The light rim along a border (gfx/FX/standardfuncsgfx.fxh) is a fixed fraction of this distance, so a thin rim
-- needs a short gradient: at 35 px the rim was a thick glowing band (user: "white borders much thinner").
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_COUNTRY_LOW = 3.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_COUNTRY_HIGH = 10.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_STATE = 3.0
-- border line meshes: thin lines (vanilla 1.5)
NDefines_Graphics.NGraphics.BORDER_WIDTH = 1.0
-- no weather on the map (user request): clouds, rain, sand storms and the snowfall post effect are never drawn
NDefines_Graphics.NGraphics.WEATHER_DISTANCE_CUTOFF = 0
NDefines_Graphics.NGraphics.WEATHER_DISTANCE_FADE_LENGTH = 1
NDefines_Graphics.NGraphics.POSTEFFECT_PER_PROVINCE_MIN_SNOW = 0.0
NDefines_Graphics.NGraphics.POSTEFFECT_PER_PROVINCE_MAX_SNOW = 0.0
NDefines_Graphics.NGraphics.POSTEFFECT_TOTAL_MIN_SNOW = 0.0
NDefines_Graphics.NGraphics.POSTEFFECT_TOTAL_MAX_SNOW = 0.0
