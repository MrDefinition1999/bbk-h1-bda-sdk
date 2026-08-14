# H1 Modal Message Dialog

Firmware wrapper: `0x800FD204` (`GUI` service table offset `0x2B8`).

Current H1-specific prototype:

```c
int h1_gui_message_box(
    unsigned int parent,
    const char *message,
    const char *title,
    unsigned int flags
);
```

## Static evidence

The wrapper forwards its four arguments to `0x801188AC`, which adds default
geometry before entering the modal dialog implementation at `0x80117FE0`.
H1 firmware has 292 direct code references to the wrapper. Representative
call sites use:

```c
h1_gui_message_box(parent, generated_message, "温馨提示", 0);
```

Examples include `0x8001B750`, `0x8001BE70`, `0x80036170`, and `0x80044C0C`.
This establishes that the second parameter is the body and the third is the
title; the order is not inferred from the 9588 SDK.

## Dynamic evidence

The first independently built probe was loaded by the H1 menu on 2026-07-24.
It called GUI table `+0x2B8`, displayed a modal dialog, accepted touch input,
and did not crash or reset. That build intentionally exposed a prototype bug:
the probe passed `title` before `message`, and only `H1 SDK Test` appeared as
the body.

The corrected second build used `(parent, message, title, 0)`, appeared under
the mathematics category with header category `0x1E`, rendered both the title
and multiline body, and returned to the same desktop after confirmation. The
QEMU PID and uptime remained continuous. The verified subset has therefore
been promoted to `sdk/include/h1_dialogs.h`; untested flags and result values
remain research-only.

Environment status: emulator-confirmed only. No true-H1 hardware execution has
been performed.
