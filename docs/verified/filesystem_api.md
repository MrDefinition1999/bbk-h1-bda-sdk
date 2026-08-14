# H1 Filesystem API

Environment: BBK H1 / Y100 V1.41 running in the ARM64-hosted H1 emulator.

The public filesystem API uses the H1 normal-BDA `FS` service table:

| Public function | H1 table entry | Behavior verified |
| --- | ---: | --- |
| `h1_fopen` | `FS+0x000` | create with `wb`, reopen with `rb`, and update-open an existing file |
| `h1_fclose` | `FS+0x004` | closes writer and reader safely |
| `h1_fread` | `FS+0x008` | returns byte count and preserves binary bytes |
| `h1_fwrite` | `FS+0x00C` | writes a 16-byte binary pattern |
| `h1_fseek` | `FS+0x010` | SET and negative END seek; returns new offset |
| `h1_ftell` | `FS+0x014` | reports offsets 16, 4, and 12 |
| `h1_remove` | `FS+0x024` | removes the temporary file |

`h1_fseek` differs from ISO C: successful calls return the resulting absolute
offset and failures return `-1`. The first probe revision exposed this behavior;
the final probe explicitly verifies returned offsets 4 and 12 against
`h1_ftell`.

## Dynamic verification

- BDA: `build/H1FilesystemProbe.bda`
- size: 32,708 bytes
- SHA-256: `1574AF457662B0AD7C048DA1B3DE63C268CC51461D07D3DD3ED2C072A2192B2B`
- temporary path: `A:\\H1SDK.TMP`
- NAND replacement: `/应用/程序/计算器.bda`
- FTL generation: 7 for logical units 2438, 2606, and 2607
- FAT/FTL byte-for-byte readback: passed
- observed result: create/write/seek/close/reopen/read/remove displayed `PASS`;
  closing the result dialog returned normally to the desktop

Screenshot: `docs/verified/assets/h1_filesystem_probe_pass.png`.

The KOV hardware profiler subsequently exercised the update-open path against
an isolated writable NAND. It creates `KOVPERF.TXT` with `wb`, then tries
`r+b` followed by the firmware-compatible `rb+` spelling, seeks to
`H1_SEEK_END`, writes one complete record, and closes the handle. Twenty
one-second checkpoints survived stopping QEMU without running the BDA exit
handler. The extracted file contained 20 consecutive `LIVE` records and no
`FINAL_REPORT`, demonstrating that the append-and-close path persists earlier
records independently of normal application teardown.

Static implementation addresses and the probe source are documented in
`reverse/docs/filesystem_api.md`. `FS+0x030` is a strong `mkdir` candidate but
was not exercised by this file-only probe, so it remains research-only.
