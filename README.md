# BBK H1 Native BDA SDK

This project is an independent native BDA SDK for the BBK H1 (`Y100`) firmware.
It builds freestanding MIPS little-endian applications for the H1 BDA loader and
tracks every public API back to H1-specific static and dynamic evidence.

The project is under active reverse engineering. Firmware addresses, candidate
APIs, probes, and uncertain structure layouts remain under `reverse/`; only APIs
that complete an observable test in the H1 emulator are promoted to
`sdk/include/`.

## Confirmed H1 Runtime Model

- CPU code is MIPS32 little-endian and is loaded as a flat image, not ELF.
- A normal application payload is loaded at `0x83C00020` and called there.
- `0x83C00000..0x83C0001F` is initialized by the H1 firmware before the call.
- Five H1 service-table pointers are available at `0x83C00004..0x83C00014`.
- The BDA header selects the file payload offset but does not contain a runtime
  load address.
- The first standalone probe has executed in the ARM64-hosted H1 emulator,
  displayed the firmware modal dialog, and returned cleanly to the desktop.
  The verified message-box subset is public in `sdk/include/h1_dialogs.h`.
- The H1 heap `alloc/free/calloc/realloc` entries have passed an independent
  zero-fill and resize-preservation probe and are public in
  `sdk/include/h1_memory.h`.
- Seven stdio-like filesystem entries passed a bounded binary round-trip,
  seek/tell, removal, and clean-return probe and are public in
  `sdk/include/h1_filesystem.h`.
- The H1 RGB565 rectangle blit, readback, and display-present entries passed an
  exact 17,920-pixel round-trip probe and are public in
  `sdk/include/h1_graphics.h`.
- The H1 full-keyboard queue, 80 Hz monotonic tick, and paired 1 ms timer passed
  a 12-second event/timing probe and are public in `sdk/include/h1_input.h` and
  `sdk/include/h1_time.h`.

See [reverse/docs/bda_header_and_loader.md](reverse/docs/bda_header_and_loader.md)
for the current evidence and unresolved fields.

The H1 menu bitmap header and its nonstandard RGB565-plus-alpha encoding are
documented in
[reverse/docs/menu_icon_resources.md](reverse/docs/menu_icon_resources.md).

The factory PCM descriptor lifecycle and `SYS+0x50..0x68` service family are
documented in [reverse/docs/audio_api.md](reverse/docs/audio_api.md). Static
structure recovery is complete; physical-H1 validation is still required
before this candidate API is promoted into `sdk/include/`.

The structure-aware emulator deployment flow is documented in
[docs/emulator_deployment.md](docs/emulator_deployment.md). It preserves the
retained NAND baseline and verifies modified FAT/FTL data before QEMU restarts.

The compiler/packer supports both single-source probes and multi-source native
applications. This is the build path used by larger game ports.

One RGBA PNG can be converted into all four H1-specific menu resources during
the same build:

```powershell
h1-bda-build app.c --title App --category 0x48 `
  --icon-png icon.png -o build\App.bda
```

The source image is contained without aspect-ratio distortion. See
[docs/verified/custom_icon_build.md](docs/verified/custom_icon_build.md) for
the exact H1 encodings and round-trip checks.

## Intended Layout

```text
sdk/include/       Dynamically verified public H1 API
h1_bda/            Compiler, packer, icon, and validator implementation
examples/          Source and built BDA programs that passed emulator tests
docs/              Developer documentation for verified behavior
reverse/           H1-only probes, scanners, candidates, and evidence notes
scripts/           Toolchain setup, verification, and emulator deployment
tests/             Static format and build regression tests
```

The repository does not copy a 9588 BDA template or reuse 9588 firmware ABI
constants. The 9588 SDK is used only as a reference for research discipline,
verification levels, and project organization.

## License

Original source code and documentation are licensed under the
[Apache License 2.0](LICENSE). Verification screenshots and depicted
third-party interfaces are excluded from that license as described in
[NOTICE](NOTICE).
