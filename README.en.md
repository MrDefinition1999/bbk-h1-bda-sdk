# BBK H1 Native BDA SDK

This independent SDK builds freestanding MIPS little-endian applications for the
BBK H1 (`Y100`). Every public API is traced to H1-specific static evidence and an
observable test; candidates that still need physical-device validation remain in
`reverse/`.

## Confirmed runtime model

- CPU code is a flat MIPS32 little-endian image loaded at `0x83C00020`.
- H1 firmware initializes `0x83C00000..0x83C0001F` with five service-table pointers.
- The BDA header selects a file payload offset and does not declare a load address.
- Dialog, heap, filesystem, RGB565 graphics, and the 80 Hz monotonic clock passed
  independent emulator probes.
- Promoted public headers live in `sdk/include/`; probes and candidates live in
  `reverse/`.

The builder supports single-source probes and multi-source native applications,
including conversion of one RGBA PNG into all four H1 menu icon resources.

## Layout

```text
sdk/include/       verified public H1 APIs
h1_bda/            compiler, packer, icon, and validator
examples/          emulator-tested examples
docs/              verified behavior and development notes
reverse/           H1 probes, scanners, and evidence
scripts/           toolchain, verification, and deployment helpers
tests/             format and build regressions
```

The repository does not copy a 9588 BDA template or reuse 9588 firmware ABI
constants; that SDK is used only as a research-method reference.

中文入口: [README.md](README.md)

## License

Original source code and documentation are licensed under the [Apache License
2.0](LICENSE). Verification screenshots and depicted third-party interfaces are
covered by [NOTICE](NOTICE).
