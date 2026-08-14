# Reference SDK Methodology Review

Reference studied: `HelloClyde/bbk9588-bda-sdk`, revision `5ab2b4e`.

## Methods Applicable To H1

The useful part of the 9588 project is its evidence workflow rather than its
addresses or headers:

1. Separate static candidates from dynamically verified public APIs.
2. Generate a BDA from source instead of patching an original application.
3. Reproduce the firmware header checks in a standalone validator.
4. Keep compilation freestanding and link the flat image to the loader's fixed
   runtime address.
5. Recover table calls by table identity plus byte offset, then validate each
   proposed signature with a minimal program and an observable result.
6. Record lifecycle and teardown behavior, especially for windows, timers,
   drawing contexts, files, and audio.
7. Deploy only to a disposable emulator storage copy and preserve the source
   firmware image.
8. Keep a source example, a built BDA, verification instructions, and a clear
   environment label for every public capability.

## 9588 Assumptions That Must Not Be Reused

The following are device-specific and are not inputs to the H1 SDK:

- runtime base `0x81C00020`;
- 9588 runtime seed addresses and service-table contents;
- 9588 category labels, capacities, or menu indexing;
- 9588 entry offset `0x95F8` and its four icon dimensions;
- C200 firmware addresses and table offsets;
- 9588 input key codes, screen geometry assumptions, timer periods, audio
  profiles, object layouts, and teardown sequences.

H1 currently establishes a normal application runtime base of `0x83C00020`, a
common original-application payload offset of `0x785C`, and H1-owned table seeds.
All remaining values must be recovered from H1 firmware and H1 BDA samples.

## Public API Admission Rule

An interface can move from `reverse/` to `sdk/include/` only after all of these
are available:

- an H1 static call site or firmware implementation identifying the table entry;
- a proposed parameter and return-value contract;
- an independently built H1 BDA that invokes it;
- a repeatable observable result in the H1 emulator;
- a documented cleanup path and known limitations.

Successful compilation, a valid header, or the absence of a crash is not enough
on its own.
