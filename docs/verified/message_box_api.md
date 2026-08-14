# Verified H1 Message Box API

Public header: `sdk/include/h1_dialogs.h`.

```c
int h1_message_box(
    h1_u32 parent,
    const char *message,
    const char *title,
    h1_u32 flags
);
```

The function is H1 GUI service-table entry `+0x2B8`. It is synchronous: the
call returns after the modal dialog is dismissed. The caller does not own a
window or allocation and therefore has no separate cleanup operation.

## Verification

- H1 firmware implementation: `0x800FD204`, named
  `h1_gui_message_box` in `project-h1.elf.i64`.
- Representative H1 firmware callers establish argument order as
  `(parent, body, title, flags)`.
- Independent source: `examples/basic/hello_dialog/hello_dialog.c`.
- Standalone BDA: `build/H1SDKTest.bda`, linked at `0x83C00020` and loaded
  through the ordinary H1 BDA loader.
- ARM64-hosted H1 emulator result on 2026-07-24: title and multiline body both
  rendered, the confirm button dismissed the dialog, and execution returned to
  the same mathematics-category desktop without a panic, hang, or reset.

Only `flags == 0` and `parent == 0` are dynamically verified. Other flag bits,
non-null parent ownership, exact result values, and true H1 hardware behavior
remain unverified and are not claimed by this document.
