.set noreorder
.set noat
.section .text.h1_bda_entry,"ax",@progbits
.globl h1_bda_main
.ent h1_bda_main
h1_bda_main:
    lui     $t0, 0x83f0
    ori     $t0, $t0, 0
    lui     $t1, %hi(stage_blob_start)
    addiu   $t1, $t1, %lo(stage_blob_start)
    lui     $t2, %hi(stage_blob_end)
    addiu   $t2, $t2, %lo(stage_blob_end)
1:
    sltu    $t3, $t1, $t2
    beq     $t3, $zero, 2f
    nop
    lw      $t4, 0($t1)
    sw      $t4, 0($t0)
    addiu   $t1, $t1, 4
    b       1b
    addiu   $t0, $t0, 4
2:
    sync
    lui     $t5, 0x83f0
    ori     $t5, $t5, 0
3:
    sltu    $t6, $t5, $t0
    beq     $t6, $zero, 4f
    nop
    cache   0x15, 0($t5)
    cache   0x10, 0($t5)
    addiu   $t5, $t5, 16
    b       3b
    nop
4:
    sync
    lui     $a0, %hi(path_blob_start)
    addiu   $a0, $a0, %lo(path_blob_start)
    move    $a1, $zero
    lui     $t9, 0x83f0
    ori     $t9, $t9, 0
    jr      $t9
    nop
.end h1_bda_main

.section .rodata.h1_v2_blobs,"a",@progbits
.align 2
stage_blob_start:
    .incbin "stage.bin"
.align 2
stage_blob_end:
path_blob_start:
    .incbin "mission-path.bin"
.align 2
path_blob_end:
