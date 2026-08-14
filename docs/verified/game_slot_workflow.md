# Fixed H1 Game Slot Workflow

Runtime target: BBK H1 V1.41 on the ARM64-host QEMU build.

## Confirmed Menu Placement

The desktop category selector groups both Other utilities and games under the
visible `其它` choice. Utility applications use BDA classification `0x47`.
Native games including `雷霆战机` and `黑白子` use `0x48` and occupy the later
game pages.

`/应用/程序/黑白子.bda` is the final native game entry. Its original file is
preserved as `build/original-black-white.bda`:

```text
size: 72608 bytes
SHA-256: 46294AD652D8CDCDAD01CBE3F05FC135DC85CF52F9D75B5A4F00E6B1311BAC9A
```

All new game ports are built with category `0x48` and deployed over this entry.

## Confirmed FAT/FTL Growth

The original entry owned five 16 KiB clusters. The Doom deployment required 41
clusters. Transactional deployment extended both FAT16 copies by 36 clusters
and allocated two previously erased FTL physical slots:

```text
logical 3613 -> physical block 3673
logical 3614 -> physical block 3674
```

The initial growth allocated those two physical slots once; later Doom builds
reused the same 41-cluster chain. That first stable post-write FTL scan reported
no invalid or torn records and read the 666,484-byte BDA back byte-for-byte. Its
historical SHA-256 is
`26345130C390D0FBB2C8EC5950B6DA06BB0C31210055801EC6C7BC6DD8AB4752`,
and the deployment report is `build/doom-final-deployment.json`.

## Deterministic Navigation

`scripts/navigate_emulator_game_slot.py` performs no image recognition before
reaching the target page. After reset it:

1. waits for automatic touch calibration to reach `complete 4/4`;
2. waits for at least six frames and 15 seconds of guest uptime, then sends
   `Esc`, `Enter`, `Esc` to cancel the stable time-changed prompt and leave any
   Time application fallback;
3. taps the desktop category selector at `(360, 10)`;
4. taps `其它` at `(350, 166)`;
5. performs two fixed left swipes at `y=150`.

Image inspection begins only after the script reports
`other-game-page-3`. The expanded `DOOM` entry occupies the only position on
that page at `(42, 51)`. Runtime entry probes confirmed that the launcher must
wait five seconds after this touch selection and then send the H1 permanent
Confirm code `39`; full-keyboard Enter code `25` does not start the selected
desktop item. The H1 application loader and Doom IWAD scan are
slow enough that launch verification uses a 30-second stabilization wait by
default. `--launch-wait` can override that interval.

The script names the two H1 key groups separately to prevent accidental
substitution: full-keyboard Enter/Esc are `25/24`, while the permanent action
Confirm/Back keys are `39/41`.

## Restored Debug Data Slot

During Doom bring-up, the user-supplied IWAD was temporarily stored over
`/应用/程序/图形计算.bda` because its existing 571-cluster chain had enough
capacity. After final verification, the slot read back as a 4,196,020-byte
`IWAD` file with SHA-256
`1D7D43BE501E67D927E415E0B8F3E29C3BF33075E859721816F652A526CAC771`.
It was transactionally restored from `build/original-graphics-calculator.bda`:

```text
size: 9,353,804 bytes
SHA-256: B21A8D517885F15729E255DFFFAE2695162A8A39D1790E13592F82F5A2B2119E
read-back match: true
invalid/torn FTL records: 0
```

The restore evidence is `build/restore-graphics-calculator.json`; the temporary
IWAD extraction was deleted after the matching read-back check.

## Persistent Shareware Data File

The current Doom runtime no longer borrows an application slot. The v1.9
shareware IWAD is a FAT16 data file at `/应用/数据/DOOM1.WAD`, installed by
`scripts/install_emulator_file.py`. Its 4,196,020 bytes occupy 257 newly linked
clusters and read back with SHA-256
`1D7D43BE501E67D927E415E0B8F3E29C3BF33075E859721816F652A526CAC771`.
Both FAT copies agree, 16 formerly unmapped logical units received new FTL
records, and the final scan found zero bad, invalid, or torn records. The
transaction report is `build/doom1-wad-install.json`.

The final game entry now contains the 748,340-byte icon/fullscreen/audio/exit
Doom build with SHA-256
`5EAF1826002FBFC4E69B063D6C6E496B1F720452388A67FC88DAE5677091C039`.
It reuses the existing 89-cluster chain left by the larger GTA experiment; the
unused tail is zero-filled, and deployment read the declared file back exactly.
