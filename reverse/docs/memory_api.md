# H1 Native BDA Memory API

Target: BBK H1 / Y100 V1.41 normal BDA ABI.

## Static evidence

The H1 runtime seed at `0x83C00010` points to the table at `0x802AAC4C`.
The 72 normal H1 applications call four untracked heap entries:

| Entry | H1 implementation | Calls | Contract from H1 implementation |
| ---: | ---: | ---: | --- |
| `MEM+0x008` | `0x800DC998` | 5232 | allocate one byte count; returns pointer or null |
| `MEM+0x00C` | `0x800DBB54` | 4363 | free one pointer |
| `MEM+0x010` | `0x800DB91C` | 14 | `calloc(count, size)`; aligns each element size and clears the allocation |
| `MEM+0x014` | `0x800DCB00` | 15 | `realloc(pointer, new_size)`; supports null and zero-size cases |

`MEM+0x000/+0x004` are separate debug-tracked wrappers. They are not used by
the normal application inventory and are not candidates for the public SDK.

The independent probe is `reverse/probes/memory_probe.c`. It checks null
handling, calloc zero-fill, preservation of the first 32 bytes across growth,
and one alloc/free pair. `build/H1MemoryProbe.bda` produced PASS in the ARM64
H1 emulator and returned normally, so these four entries are now public in
`sdk/include/h1_memory.h`. Dynamic evidence is in
`docs/verified/memory_api.md`.
