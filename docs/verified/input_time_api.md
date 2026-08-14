# Verified input and time APIs

H1 native BDA applications can use:

```c
#include "h1_input.h"
#include "h1_time.h"
```

## Keyboard events

`h1_event_fetch(&code, &value)` reads the H1 full-keyboard queue. A physical key
transition uses:

- `H1_EVENT_KEY_DOWN` (`9`)
- `H1_EVENT_KEY_UP` (`10`)
- `value`: one of the `H1_KEY_*` matrix identifiers in `h1_input.h`

`h1_input_poll_key()` filters non-key events and returns at most one transition.
This is the recommended interface for game loops.

## Clocks

- `h1_raw_tick_80hz()` is a continuously running 80 Hz monotonic tick.
- `h1_timer_start()` clears and starts a private 1 ms counter.
- `h1_timer_read_ms()` reads the current counter.
- `h1_timer_stop()` stops it and must be paired with `h1_timer_start()`.

The 1 ms timer generates `H1_EVENT_TIMER` housekeeping events in the same queue;
`h1_input_poll_key()` filters them.

These semantics were measured by `H1InputTimeProbe.bda` in the ARM64-hosted H1
emulator over a 12,000 ms capture.
