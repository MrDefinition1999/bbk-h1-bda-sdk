# Custom H1 BDA Menu Icons

Target: BBK H1 / Y100 V1.41 normal BDA files.

## Research Boundary

The 9588 SDK was used as a methodology reference: decode a source PNG, generate
every menu size, validate the packed ranges, and extract the result for a
round-trip check. Its VX header, dimensions, entry offset, and transparency
rules are not used by this implementation.

H1-specific evidence comes from the firmware renderer and the original H1
`使命.bda` and `雷霆战机.bda` samples. Both game files use category `0x48`,
payload offset `0x785C`, and the same four resources as the other normal H1
applications:

| Index | Size | Image |
| ---: | ---: | --- |
| 0 | `0x17C8` | 45 x 45, RGB565 little-endian plus 8-bit alpha |
| 1 | `0x2620` | 57 x 57, RGB565 little-endian plus 8-bit alpha |
| 2 | `0x1704` | 49 x 60, RGB565 little-endian |
| 3 | `0x22E8` | 49 x 60, RGB565 little-endian plus unused padded tail |

No resource bytes or artwork from either original game are copied into SDK
applications.

## Builder Behavior

`h1_bda.resources.build_icon_resources()` converts one RGBA PNG to the four
fixed H1 images. It preserves the source aspect ratio, centers it in each
destination, retains alpha in resources 0 and 1, composites alpha against
black in resources 2 and 3, and zero-fills each declared resource tail.

`h1-bda-build` exposes this as `--icon-png`. Game-specific builders pass the
same argument to `build_bda()`.

## Verification

The SDK regression creates a known RGBA image, generates all four resources,
and verifies every image header, segment size, center RGB565 value, and alpha
byte. The full suite passed 20 tests on 2026-07-25.

The Doom build embeds the original source
`ports/doom/assets/h1-doom-icon.png`. `scripts/extract_bda_icons.py` then
decoded all four images from `build/H1Doom.bda`; the 45 x 45 result retained
the expected transparent perimeter and palette. The complete BDA passed the
header and resource validator with title `DOOM` and category `0x48`.
