# H1 normal-BDA input and time services

Status: dynamically measured by `H1InputTimeProbe.bda` in the H1 emulator.
Public wrappers are in `sdk/include/h1_input.h` and `sdk/include/h1_time.h`.

## Service tables and offsets

The GUI service-table pointer is stored at `0x83C00004`; the system table is
stored at `0x83C0000C`.

| Table | Offset | Wrapper | Observed behavior |
| --- | ---: | --- | --- |
| GUI | `0x6D8` | `h1_raw_tick_80hz` | free-running monotonic 80 Hz tick |
| GUI | `0x714` | `h1_timer_start` | reset/start private 1 ms timer |
| GUI | `0x718` | `h1_timer_stop` | stop private timer |
| GUI | `0x71C` | `h1_timer_read_ms` | read elapsed milliseconds |
| GUI | `0x750` | `h1_event_fetch` | fetch one queued event |
| SYS | `0x080` | probe-only busy delay | yield/delay used during capture |

## Event queue

`h1_event_fetch(int *code, int *value)` stores `-1, -1` when no event is
available. The full H1 keyboard uses:

```c
#define H1_EVENT_TIMER    3
#define H1_EVENT_KEY_DOWN 9
#define H1_EVENT_KEY_UP   10
```

For key transitions, `value` is an H1 matrix identifier from
`sdk/include/h1_input.h`. H1 has a full keyboard and its matrix values must not
be replaced with the BBK 9588 layout. `h1_input_poll_key` filters timer and
other events and returns at most one press/release transition per call.

While the private 1 ms timer is active, the same queue receives housekeeping
events with `(code, value) == (3, 0)`. Game loops must drain or filter them;
otherwise the queue can appear to contain continuous user input.

## Timing measurement

The probe drains old events, starts the private timer, records the raw tick and
millisecond counter, captures for 12,000 ms, then stops the timer. Each retained
event stores both clocks, code, and value in `A:\\H1INPT.BIN`.

The observed raw clock advances at 80 Hz and wraps naturally as an unsigned
32-bit counter. Time differences must therefore use unsigned subtraction. The
private millisecond timer must be paired with start/stop; it is not a global
wall clock and starting it changes the event queue through housekeeping events.

## Input injection requirements

The emulator must send a real key-down followed by key-up. Touch input likewise
needs calibrated SADC coordinates and an approximately 180 ms press interval;
a browser click without guest press/release timing is insufficient. Fixed
navigation scripts should verify the current screen before emitting matrix
events so that a stale boot state cannot launch the wrong application.
