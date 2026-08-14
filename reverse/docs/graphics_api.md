# H1 Graphics API Research

Status: RGB565 read, blit, and present entries dynamically verified. Drawing
contexts and allocating capture remain research-only.

The H1 GUI service table is supplied to a normal BDA through runtime slot
`0x83C00004`. The following H1 entries are now understood well enough to probe:

| GUI offset | Firmware address | Research name | Behavior |
| --- | --- | --- | --- |
| `+0x070` | `0x80166654` | `h1_display_present_region` | Presents an inclusive `x1,y1,x2,y2` region. All-zero arguments select the full 480x272 display. |
| `+0x308` | `0x800F4420` | `h1_gui_begin_draw` | Allocates one of six 0xD4-byte drawing contexts and binds it to a target. |
| `+0x30C` | `0x800F46E4` | `h1_gui_end_draw` | Finalizes/releases a drawing context. |
| `+0x3F8` | `0x800F7778` | `h1_gui_read_pixels_rgb565` | Reads `width * height` RGB565 pixels from `x,y` into a caller buffer. |
| `+0x3FC` | `0x800F77C0` | `h1_gui_capture_pixels_alloc` | Allocates `width * height * bytes_per_pixel` and reads the rectangle into it. |
| `+0x400` | `0x800F7860` | `h1_gui_blit_rgb565` | Sets a full-screen clip and writes `width * height` RGB565 pixels at `x,y`. |

## Static evidence

- `GUI+0x3FC` multiplies its third and fourth arguments and then multiplies by
  the display backend's bytes-per-pixel field. The H1 backend reports two bytes
  per pixel.
- Several firmware call sites allocate exactly `2 * width * height`, call
  `GUI+0x3F8`, modify every byte, then call `GUI+0x400` with the same
  `x,y,width,height`. Examples include `0x8002651C`, `0x8002E368`, and
  `0x800887A0`.
- `GUI+0x070` clamps the region to `0..479` and `0..271`, then converts the
  firmware framebuffer at `0x80D55AA0` from RGB565 into the active display
  output buffer. Its region coordinates are inclusive.
- The normal BDA loader uses `GUI+0x3FC`, `GUI+0x400`, and `GUI+0x070` to save,
  restore, and present a loading-animation area. These entries therefore belong
  to the same service table exposed to applications.

## Dynamic probe

`reverse/probes/graphics_probe.c` writes a 160x112 RGB565 diagnostic pattern,
presents the exact region, reads it back with `GUI+0x3F8`, compares every pixel,
and reports PASS or FAIL using the already verified message-box API.

The ARM64-hosted H1 emulator reported PASS on 2026-07-25. Closing the dialog
returned cleanly to the desktop without leaving the test pixels behind.

Promoted to `sdk/include/h1_graphics.h`:

- `GUI+0x070` region/full-screen present
- `GUI+0x3F8` RGB565 readback
- `GUI+0x400` RGB565 blit

Still research-only because the probe did not call them directly:

- `GUI+0x308` begin drawing context
- `GUI+0x30C` end drawing context
- `GUI+0x3FC` allocating capture helper
