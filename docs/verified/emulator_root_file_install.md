# H1 Emulator Root File Installation

Target: the private ARM64-host emulator NAND copy only.

`scripts/install_emulator_file.py` adds one new conservative ASCII 8.3 file to
the H1 FAT16 volume. It exists for runtime data such as
`应用/数据/DOOM1.WAD`; game BDA
programs still use the fixed final entry under `/应用/程序`.

The installer refuses empty input, invalid names, duplicate paths, insufficient
FAT space, a full root directory, missing ECC support, ambiguous read-back, or
any bad/invalid/torn FTL record. It performs these mutations on a temporary
full NAND copy:

1. reserve clusters that are free in every FAT copy;
2. link the new chain in every FAT;
3. write an archive-type 8.3 root entry with first cluster and exact file size;
4. update existing FTL generations and allocate backing records for new logical
   units;
5. rescan FAT/FTL and compare the installed file byte-for-byte;
6. replace the emulator NAND only after every check passes.

The first verified installation created `/应用/数据/DOOM1.WAD` from the
4,196,020-byte
Doom v1.9 shareware IWAD. It used 257 clusters, allocated 16 new FTL records,
reported zero invalid/torn records, and matched SHA-256
`1D7D43BE501E67D927E415E0B8F3E29C3BF33075E859721816F652A526CAC771`.
