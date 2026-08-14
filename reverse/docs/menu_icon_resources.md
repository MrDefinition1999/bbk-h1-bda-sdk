# H1 BDA Menu Icon Resources

Target firmware: BBK H1 / Y100 V1.41.

## Verified Container Layout

Normal H1 BDA files contain four menu resources between file offsets `0x88`
and `0x785C`:

| Index | Declared bytes | Image header | Observed menu role |
| ---: | ---: | --- | --- |
| 0 | `0x17C8` | 45 x 45 x 24 | normal application-grid icon |
| 1 | `0x2620` | 57 x 57 x 24 | alternate/selected menu icon; exact views pending |
| 2 | `0x1704` | 49 x 60 x 16 | alternate menu icon; exact views pending |
| 3 | `0x22E8` | 49 x 60 x 16 | alternate menu icon; exact views pending |

The 12-byte image header is six little-endian 16-bit words:

```text
u16 nominal_width
u16 nominal_height
u16 bits_per_pixel
u16 planes
u16 draw_width
u16 draw_height
```

Firmware function `0x8008463C` reads the bit depth from byte `+4`, the draw
width and height from `+8` and `+0xA`, and passes pixel data at `+0xC` to the
renderer.

## H1 24-Bit Pixel Encoding

H1's value `24` does not mean BGR888. Each three-byte pixel is:

```text
u16 rgb565_le
u8  alpha
```

Firmware function `0x800713A0` reads the first two bytes as RGB565 and the
third byte as alpha, then blends it into the 16-bit framebuffer. An alpha of
zero leaves the destination unchanged; 255 replaces it with the source color.

This was dynamically confirmed after the first independent SDK icon used
BGR888: its red component became a very low alpha and the icon appeared almost
fully transparent. Encoding the same source colors as RGB565 plus alpha fixes
the failure without changing the BDA loader or NAND deployment path.

## Resource Padding

Resources 0 and 1 have one alignment byte after their pixel arrays. Resource 2
ends exactly after its RGB565 array. Resource 3 has an additional `0xBE4` bytes
after its 49 x 60 RGB565 array. The normal draw wrapper uses the declared image
dimensions and does not consume that tail while drawing the image itself.

The semantic purpose of the resource-3 tail remains unverified. The standalone
builder currently zero-fills it and must not expose it as a stable public SDK
format until a separate consumer is found or every menu view has been tested.

## SDK Image Conversion

The packer accepts one RGBA PNG and generates each H1 resource independently.
It contains the source image at the destination aspect ratio rather than
cropping or stretching it. The 24-bit resources retain source alpha; the
16-bit resources composite alpha against black because those formats have no
alpha byte. Every output is padded to the size declared in the BDA header.

This conversion was checked by extracting the generated Doom BDA resources
back to PNG. The normal 45 x 45 result retained its transparent perimeter and
RGB565 artwork, and the BDA validator confirmed the original H1 resource
offsets and sizes. See
[../../docs/verified/custom_icon_build.md](../../docs/verified/custom_icon_build.md).
