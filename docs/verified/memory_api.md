# H1 Heap Memory API

Environment: BBK H1 / Y100 V1.41 running in the ARM64-hosted H1 emulator.

The public heap API uses the H1 normal-BDA `MEM` service table:

| Public function | H1 table entry | Behavior verified |
| --- | ---: | --- |
| `h1_alloc(size)` | `MEM+0x008` | nonzero allocation returns writable memory |
| `h1_free(pointer)` | `MEM+0x00C` | releases allocations and returns safely |
| `h1_calloc(count, size)` | `MEM+0x010` | returns zero-filled storage |
| `h1_realloc(pointer, size)` | `MEM+0x014` | growth preserves existing bytes |

Static implementation addresses and original-application call counts are in
`reverse/docs/memory_api.md`. The independent probe is
`reverse/probes/memory_probe.c`.

## Dynamic verification

- BDA: `build/H1MemoryProbe.bda`
- size: 31,428 bytes
- SHA-256: `7D6FC88C765E53BFD35E80785CF6C17913B48AF4C14CA0A46B8758CC49F7A4BE`
- NAND replacement: `/应用/程序/计算器.bda`
- FTL generation: 5 for logical units 2438, 2606, and 2607
- FAT/FTL byte-for-byte readback: passed
- observed result: all four checks displayed `PASS`; closing the dialog returned
  to the desktop without a hang, panic, or reset

Screenshot: `docs/verified/assets/h1_memory_probe_pass.png`.

`h1_memset` and `h1_memcpy` are freestanding SDK helpers, not firmware calls.
The probe did not characterize exhaustion, invalid pointers, double-free, or
allocation limits. Applications must treat those operations as invalid.
