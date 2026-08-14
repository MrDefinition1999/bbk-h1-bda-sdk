# Multi-source BDA builds

The H1 builder compiles each C or assembly source into a separate MIPS32
little-endian object and links all objects into one flat BDA payload.

```powershell
python -m h1_bda.build entry.c renderer.c platform.c `
  -I include -D FEATURE_NAME=1 --cflag=-std=c99 `
  --title MyGame -o build\MyGame.bda
```

The linker keeps `h1_bda_main` as the entry point, places its dedicated section
first at `0x83C00020`, and removes unused function/data sections. Existing
single-source commands remain compatible.

The linker also exposes an H1 application-window `.h1_noinit` section. Objects
placed there reserve RAM after the file-backed image without expanding the BDA;
the linker rejects any allocation ending above the confirmed 64 MiB SDRAM
limit at `0x84000000`. `test_noinit_reserves_ram_without_expanding_payload`
uses a referenced 2 MiB arena and confirms that the emitted payload remains
smaller than 4 KiB.
