#ifndef H1_RUNTIME_H
#define H1_RUNTIME_H

#include "h1_types.h"

#define H1_RUNTIME_GUI_TABLE_SLOT 0x83C00004u
#define H1_RUNTIME_FS_TABLE_SLOT  0x83C00008u
#define H1_RUNTIME_SYS_TABLE_SLOT 0x83C0000Cu
#define H1_RUNTIME_MEM_TABLE_SLOT 0x83C00010u
#define H1_RUNTIME_RES_TABLE_SLOT 0x83C00014u

static inline void *h1_runtime_table(h1_u32 slot)
{
    return *(void * volatile *)slot;
}

static inline void *h1_runtime_entry(void *table, h1_u32 offset)
{
    return *(void **)((h1_u8 *)table + offset);
}

#endif
