# H1 normal-BDA filesystem service table

Status: dynamically verified in the H1 emulator unless an entry is explicitly
marked as a candidate. Public wrappers are in `sdk/include/h1_filesystem.h` and
the probe implementation is in `reverse/probes/filesystem_probe.c`.

## Table location

Normal H1 BDA modules receive a filesystem service-table pointer through the
word at `0x83C00008`. Calls load a function pointer from that table and invoke
it with the standard little-endian MIPS o32 calling convention.

| Offset | Public wrapper | Observed signature | Status |
| ---: | --- | --- | --- |
| `0x000` | `h1_fopen` | `file *(const char *, const char *)` | verified |
| `0x004` | `h1_fclose` | `int(file *)` | verified |
| `0x008` | `h1_fread` | `u32(void *, u32, u32, file *)` | verified |
| `0x00C` | `h1_fwrite` | `u32(const void *, u32, u32, file *)` | verified |
| `0x010` | `h1_fseek` | `int(file *, int, int)` | verified |
| `0x014` | `h1_ftell` | `int(file *)` | verified |
| `0x024` | `h1_remove` | `int(const char *)` | verified |
| `0x030` | research only | likely `mkdir(const char *)` | candidate |

The unused gaps are not evidence that the table ends. Do not publish wrappers
for unverified slots merely because a reference H2 or 9588 table uses them.

## Semantics confirmed by the probe

`H1FilesystemProbe.bda` creates `A:\\H1SDK.TMP` with `wb`, writes a 16-byte
binary pattern, seeks on the writer, closes it, reopens it with `rb`, reads the
same bytes, seeks four bytes back from the end, reads the tail, closes it, and
removes the file. Reopening the removed path fails as expected.

Unlike ISO C `fseek`, the H1 service returns the resulting absolute byte
offset on success and `-1` on failure. The verified calls returned `4` for
`SEEK_SET, 4` and `12` for `SEEK_END, -4`; `h1_ftell` returned the same values.

Observed seek constants are:

```c
#define H1_SEEK_SET 0
#define H1_SEEK_CUR 1
#define H1_SEEK_END 2
```

`fread` and `fwrite` use C-like `(buffer, size, count, file)` arguments and
return the transferred byte/item count used by the firmware. Existing probes
use `size=1`, making the return value an unambiguous byte count.

## Persistence follow-up

The KOV performance journal exercised update-open and append behavior against
an isolated writable NAND. It first tries `r+b`, then the firmware-compatible
`rb+`, seeks to `H1_SEEK_END`, writes one complete record, and closes the file.
One-second records survived terminating QEMU without running the BDA exit
handler. This validates close-based incremental persistence; it does not make
per-frame filesystem writes safe or cheap.

## Open work

- Dynamically verify `FS+0x030` before adding `h1_mkdir` to the public SDK.
- Probe directory enumeration, rename, stat and free-space services by tracing
  an original H1 BDA rather than importing offsets from another BBK model.
- Keep paths in device form (`A:\\...`) inside the guest and keep host paths
  out of release binaries.
