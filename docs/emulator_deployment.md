# H1 Emulator BDA Deployment

The emulator stores H1 files inside the original firmware's FAT16-over-FTL
volume. A BDA cannot be copied next to the NAND image and discovered by the H1
menu.

`scripts/deploy_emulator_bda.py` performs a structure-aware replacement:

1. stop the QEMU instance controlled by `http://127.0.0.1:8793`;
2. copy the active NAND to a private temporary image, leaving any retained
   hard-linked baseline untouched;
3. resolve the requested FAT16 long filename and existing cluster chain;
4. replace the file bytes and update only its directory size;
5. regenerate H1 JZ4740 ECC and FTL commit metadata for every changed 256 KiB
   logical unit;
6. rescan the FTL and read the replacement back through FAT;
7. atomically replace the active NAND only after every check passes, then
   restart QEMU.

The default remains conservative and refuses a replacement larger than the
target's current cluster chain. `--grow` explicitly extends that chain, updates
both FAT copies, allocates erased H1 FTL slots for newly touched logical units,
regenerates ECC and commit metadata, and verifies the complete file through a
fresh FAT/FTL scan before replacing the active NAND.

Game ports use the final native game slot under `其它`:

```powershell
python scripts/deploy_emulator_bda.py `
  --bda build/H1Doom.bda `
  --target 黑白子.bda `
  --grow

python scripts/navigate_emulator_game_slot.py `
  --capture build/game-slot.png
```

List candidates without writing:

```powershell
python scripts/deploy_emulator_bda.py --list
```

Deploy the SDK probe over the existing calculator entry:

```powershell
python scripts/deploy_emulator_bda.py `
  --bda build/H1SDKTest.bda `
  --target 计算器.bda
```

Static deployment success proves the H1 header, FAT, FTL, OOB, and ECC paths.
It does not prove the BDA runtime ABI. Runtime status is recorded separately
after launching the menu entry and observing its behavior.
