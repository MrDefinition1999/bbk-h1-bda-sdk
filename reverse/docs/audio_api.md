# H1 native PCM service family

Status: statically confirmed from the H1 V1.41 factory applications. The
descriptor lifecycle and initialization layout have two independent original
callers. Owner testing has confirmed normal physical-H1 playback for the SDK
DOOM port and the A320 Doudizhu and Zhao Yun ports. The remaining A320 titles
still require retesting after the common alignment and queue correction, so
these entries remain under `reverse/` rather than the public SDK headers.

## Service table

The service table is loaded from `0x83C0000C`. The following offsets form one
audio lifecycle:

| Offset | Observed operation | Confirmed arguments |
| ---: | --- | --- |
| `+0x50` | initialize one PCM descriptor | `a0 = descriptor` |
| `+0x54` | destroy one PCM descriptor | `a0 = descriptor` |
| `+0x58` | initialize the output device | `a0 = configuration` |
| `+0x5C` | submit/play a descriptor | `a0 = route`, `a1 = descriptor`, `a2/a3 = flags` |
| `+0x60` | start output | no observed arguments |
| `+0x64` | stop output | no observed arguments |
| `+0x68` | close output | no observed arguments |

The names are descriptive and are not recovered vendor symbols. Return-value
semantics and the exact meanings of the submit route/flags are not yet public
contracts.

## PCM descriptor

Factory applications allocate descriptors at a 32-byte stride. Before calling
`SYS+0x50`, they write:

```c
struct h1_pcm_descriptor_candidate {
    void *pcm;          /* +0x00 */
    uint32_t bytes;     /* +0x04, even byte count in the chess sample */
    uint32_t private_words[6];
};
```

The remaining 24 bytes are zero before initialization and belong to the H1
audio service. Applications preserve them between `SYS+0x50` and `SYS+0x54`.
They must therefore not be replaced by the eight-byte `{pcm, bytes}` structure
previously used by the A320 compatibility layer.

In the factory Chinese Chess BDA, a table of 20 descriptors begins at runtime
address `0x83C12EF8`. Each source record contributes a PCM pointer and
`(record_bytes - 12) & ~1`; `SYS+0x50` is called once per descriptor. Playback
uses `SYS+0x5C(0, descriptor, 0, 0)`. Shutdown calls `SYS+0x54` once per
initialized descriptor before releasing the source data.

The factory Mission BDA independently uses 32-byte descriptor arrays and calls
`SYS+0x50` only after both leading words are nonzero. Its mixer uses other
submit route/flag combinations, proving that those arguments select behavior
rather than descriptor size.

## Output configuration

Both factory samples pass a word array to `SYS+0x58`. Confirmed leading words
are:

```c
struct h1_pcm_config_candidate {
    uint32_t sample_rate;
    uint32_t mode;
    uint32_t buffer_bytes;
};
```

Mission clears a 36-byte backing object and writes `{11025, 1, 4096}` before
initialization. Chinese Chess writes `{caller_rate, caller_mode, 4096}`. This
confirms the sample-rate and buffer-size fields; `mode == 1` is consistent with
the factory mono path but its exact enum meaning remains provisional.

The observed startup order is descriptor initialization as needed,
`SYS+0x58(config)`, then `SYS+0x60()`. Shutdown is `SYS+0x64()`,
`SYS+0x68()`, followed by `SYS+0x54(descriptor)` for each live descriptor.

## Porting consequence

The old A320 bridge happened to produce audio in QEMU because the emulated
firmware consumed the two public words directly. Physical H1 hardware stayed
silent because the system-owned descriptor state was never initialized. A
hardware-capable bridge must retain a full descriptor, call `SYS+0x50` before
its first submission, and call `SYS+0x54` during teardown.
