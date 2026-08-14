# H1 RGB565 Graphics API

Environment: BBK H1 / Y100 V1.41 running in the ARM64-hosted H1 emulator.

The verified software-framebuffer path uses the normal-BDA `GUI` service table:

| Public function | H1 table entry | Verified behavior |
| --- | ---: | --- |
| `h1_blit_rgb565` | `GUI+0x400` | writes a 160x112 RGB565 test image at an explicit `x,y` |
| `h1_read_rgb565` | `GUI+0x3F8` | reads the same rectangle back with exact pixel identity |
| `h1_present_region` | `GUI+0x070` | presents an inclusive region to the 480x272 display output |
| `h1_present_full_screen` | `GUI+0x070` | all-zero arguments request a full display refresh |

`h1_blit_rgb565` and `h1_read_rgb565` use `x, y, width, height, pixels`.
The pixel buffer is tightly packed, row-major RGB565 with two bytes per pixel.

`h1_present_region` differs: its four coordinates are inclusive endpoints. For
example, a 160x112 image written at `(160,72)` is presented as
`(160,72,319,183)`.

## Dynamic verification

- BDA: `build/H1GraphicsProbe.bda`
- size: 102,996 bytes
- SHA-256: `5EB9FA322F1B535EEC21D1CA5F4ED705406487D79C1291079C50E4060F45AC27`
- NAND replacement: `/应用/程序/计算器.bda`
- FTL generation: 8 for logical units 2438, 2606, and 2607
- FAT/FTL byte-for-byte readback: passed
- observed result: the BDA wrote red, green, blue, and checkerboard regions,
  presented them, read all 17,920 pixels back, and displayed PASS after exact
  comparison
- clean return: closing the PASS dialog restored the desktop without residual
  test pixels or corruption

Screenshot: `docs/verified/assets/h1_graphics_probe_pass.png`.

The allocating screenshot helper and drawing-context begin/end functions remain
under `reverse/` because this probe did not exercise them directly.
