# H1 BDA Header And Loader

Target firmware: BBK H1 / Y100 V1.41.

## Confirmed Header Envelope

The H1 loader reads a fixed `0x88`-byte header. The first eleven little-endian
words (`0x00..0x2B`) are stored XORed with `0x44525744` (ASCII bytes `DWRD`).
The checksum word at `0x84` is stored XORed with `0x322D464B` (ASCII bytes
`KF-2`).

Confirmed decoded fields:

| Offset | Meaning | Evidence |
| ---: | --- | --- |
| `0x00` | `BBK\0` magic | loader string comparison |
| `0x04` | marker `0x5D245562` | exact loader comparison |
| `0x08` | version-like word; original H1 value `0x01000102` | sample inventory |
| `0x0C` | application/menu classification word | varies by H1 application; exact mapping pending |
| `0x10` | declared file size minus four | original H1 BDA cross-check |
| `0x14` | executable payload file offset | loader seek and original BDA cross-check |
| `0x18` | first resource offset; original H1 value `0x88` | sample inventory |
| `0x1C..0x28` | four resource size fields | sample inventory; exact rendering roles pending |
| `0x2C` | GBK menu title, 16 bytes | sample inventory and menu display |
| `0x3C` | build-time text, 20 bytes in original files | sample inventory |
| `0x50` | description text, 20 bytes in original files | sample inventory |
| `0x84` | encoded sum of decoded bytes `0x00..0x83` | loader implementation |

Normal original H1 applications commonly use payload offset `0x785C`. This is
an H1 observation and is not the 9588 entry offset. The four-resource envelope
between `0x88` and `0x785C` and the H1-specific RGB565-plus-alpha pixel format
are now decoded. Resource roles outside the normal application grid and the
extra tail on resource 3 still require dynamic verification. See
[menu_icon_resources.md](menu_icon_resources.md).

Three classification values now have H1 runtime evidence: the original
`计算器.bda` uses `0x1E` and appears under mathematics, an independent probe
built with `0x47` appeared among the `其它` utilities, and the native games
`雷霆战机.bda` and `黑白子.bda` use `0x48` on the game pages inside `其它`.
New game ports use `0x48`. Remaining category values and any high-bit flags are
still pending a full H1 inventory.

## Loader Execution Path

H1 firmware function `0x80077A84` performs the normal application load:

1. open the selected BDA and read `0x88` bytes;
2. decode the first eleven words and checksum;
3. verify marker `0x5D245562`, `BBK` magic, and the byte-sum checksum;
4. seek to decoded header word `0x14`;
5. read the remainder of the file into `0x83C00020` (including a chunked path
   for larger files);
6. close the file and call `0x83C00020` using `jalr`.

The header does not supply the runtime address and the loader performs no ELF
relocation. SDK output must therefore be linked for `0x83C00020`, and zeroed
storage required by the program must be represented in the flat image unless a
verified runtime initializer handles it.

## Runtime Prefix And Service Seeds

Before applications run, H1 firmware function `0x80076E20` copies eight words
from `0x802AAC30` to `0x83C00000..0x83C0001F`:

| Runtime address | H1 seed value | Current interpretation |
| ---: | ---: | --- |
| `0x83C00000` | `0x00000000` | reserved |
| `0x83C00004` | `0x802AA110` | service table 0 |
| `0x83C00008` | `0x802AA080` | service table 1 |
| `0x83C0000C` | `0x802A9EF0` | service table 2 |
| `0x83C00010` | `0x802AAC4C` | service table 3 |
| `0x83C00014` | `0x802A9FD0` | service table 4 |
| `0x83C00018` | `0x00000000` | reserved |
| `0x83C0001C` | `0x80028804` | runtime function; contract pending |

The table identities, sizes, and entries are H1-specific and are being derived
from H1 application call sites. They are intentionally numbered until function
groups are supported by evidence.

## Separate Recovery ABI

`系统恢复.bda` uses a different 64-byte runtime prefix and executes its payload
at `0x83C00040`. It is not a valid template for normal H1 applications. The SDK
targets the normal `project.bin` loader path at `0x83C00020`.
